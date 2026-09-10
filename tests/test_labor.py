"""Basic Labor System tests — Stage 3.

Covers:
1. Successful labor reward
2. Money increase after labor
3. Cooldown prevention
4. Cooldown expiration
5. Correct remaining cooldown calculation
6. Database persistence of labor time
7. Multiple labor attempts
8. Wallet service integration
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.core import constants
from app.database.repositories.player_repository import PlayerRepository
from app.game.shared.errors import PlayerNotFoundError


async def test_successful_labor_reward(services, register):
    player = await register(tg_id=7001)

    result = await services.labor.perform_labor(player.player_id)

    assert result.success is True
    assert result.reward == constants.LABOR_REWARD
    assert result.reward == 50_000
    assert result.remaining_seconds == 0
    assert result.last_labor_at is not None


async def test_money_increase_after_labor(services, register):
    player = await register(tg_id=7002)

    balance_before = await services.money.get_balance(player.player_id)
    assert balance_before == 0

    result = await services.labor.perform_labor(player.player_id)

    assert result.success is True
    balance_after = await services.money.get_balance(player.player_id)
    assert balance_after == constants.LABOR_REWARD
    assert balance_after == 50_000
    assert result.balance_after == balance_after


async def test_cooldown_prevention(services, register):
    player = await register(tg_id=7003)

    first = await services.labor.perform_labor(player.player_id)
    assert first.success is True

    second = await services.labor.perform_labor(player.player_id)
    assert second.success is False
    assert second.reward == 0
    assert second.remaining_seconds > 0
    assert second.remaining_seconds <= constants.LABOR_COOLDOWN_SECONDS

    # Money should not increase on second attempt
    balance = await services.money.get_balance(player.player_id)
    assert balance == constants.LABOR_REWARD


async def test_cooldown_expiration(services, register):
    player = await register(tg_id=7004)

    first = await services.labor.perform_labor(player.player_id)
    assert first.success is True

    # Manually set last_labor_at to past (simulate 5+ minutes ago)
    past = datetime.now(timezone.utc) - timedelta(
        seconds=constants.LABOR_COOLDOWN_SECONDS + 10
    )
    async with services.labor._session_factory() as session:
        repo = PlayerRepository(session)
        await repo.update_last_labor_at(player.player_id, past)
        await session.commit()

    second = await services.labor.perform_labor(player.player_id)
    assert second.success is True
    assert second.reward == constants.LABOR_REWARD

    balance = await services.money.get_balance(player.player_id)
    assert balance == constants.LABOR_REWARD * 2


async def test_correct_remaining_cooldown_calculation(services, register):
    player = await register(tg_id=7005)

    await services.labor.perform_labor(player.player_id)

    # Immediately check remaining
    remaining = await services.labor.get_remaining_cooldown(player.player_id)
    assert remaining > 0
    assert remaining <= constants.LABOR_COOLDOWN_SECONDS
    # Should be close to full cooldown (allow small drift)
    assert remaining >= constants.LABOR_COOLDOWN_SECONDS - 5

    # Check via can_work status
    status = await services.labor.can_work(player.player_id)
    assert status.can_work is False
    assert status.remaining_seconds == remaining
    assert status.reward == constants.LABOR_REWARD
    assert status.cooldown_seconds == constants.LABOR_COOLDOWN_SECONDS

    # Simulate half cooldown passed
    half_past = datetime.now(timezone.utc) - timedelta(
        seconds=constants.LABOR_COOLDOWN_SECONDS // 2
    )
    async with services.labor._session_factory() as session:
        repo = PlayerRepository(session)
        await repo.update_last_labor_at(player.player_id, half_past)
        await session.commit()

    remaining_half = await services.labor.get_remaining_cooldown(player.player_id)
    # Should be about half
    expected_half = constants.LABOR_COOLDOWN_SECONDS // 2
    assert abs(remaining_half - expected_half) <= 5

    # Simulate full cooldown passed
    full_past = datetime.now(timezone.utc) - timedelta(
        seconds=constants.LABOR_COOLDOWN_SECONDS + 1
    )
    async with services.labor._session_factory() as session:
        repo = PlayerRepository(session)
        await repo.update_last_labor_at(player.player_id, full_past)
        await session.commit()

    remaining_zero = await services.labor.get_remaining_cooldown(player.player_id)
    assert remaining_zero == 0

    status2 = await services.labor.can_work(player.player_id)
    assert status2.can_work is True
    assert status2.remaining_seconds == 0


async def test_database_persistence_of_labor_time(db, services, register):
    player = await register(tg_id=7006)

    result = await services.labor.perform_labor(player.player_id)
    assert result.success is True
    first_labor_time = result.last_labor_at

    # Simulate restart with new ServiceRegistry using same DB
    from app.services import ServiceRegistry

    new_services = ServiceRegistry(db.session_factory)

    # Labor time should persist
    status = await new_services.labor.can_work(player.player_id)
    assert status.last_labor_at is not None
    assert status.can_work is False
    assert status.remaining_seconds > 0

    # Balance should also persist
    balance = await new_services.money.get_balance(player.player_id)
    assert balance == constants.LABOR_REWARD

    # Direct DB check
    async with db.session_factory() as session:
        repo = PlayerRepository(session)
        player_obj = await repo.get_by_id(player.player_id)
        assert player_obj is not None
        assert player_obj.last_labor_at is not None
        # Compare timestamps (allow small difference)
        assert abs((player_obj.last_labor_at - first_labor_time).total_seconds()) < 5


async def test_multiple_labor_attempts(services, register):
    player = await register(tg_id=7007)

    # First success
    r1 = await services.labor.perform_labor(player.player_id)
    assert r1.success is True

    # 4 immediate failures
    for _ in range(4):
        r = await services.labor.perform_labor(player.player_id)
        assert r.success is False
        assert r.remaining_seconds > 0

    balance = await services.money.get_balance(player.player_id)
    assert balance == constants.LABOR_REWARD

    # After cooldown, success again
    past = datetime.now(timezone.utc) - timedelta(
        seconds=constants.LABOR_COOLDOWN_SECONDS + 1
    )
    async with services.labor._session_factory() as session:
        repo = PlayerRepository(session)
        await repo.update_last_labor_at(player.player_id, past)
        await session.commit()

    r2 = await services.labor.perform_labor(player.player_id)
    assert r2.success is True
    assert await services.money.get_balance(player.player_id) == constants.LABOR_REWARD * 2

    # And blocked again
    r3 = await services.labor.perform_labor(player.player_id)
    assert r3.success is False


async def test_wallet_service_integration(services, register):
    player = await register(tg_id=7008)

    # Labor should use money system — check via MoneyService
    await services.labor.perform_labor(player.player_id)
    balance = await services.money.get_balance(player.player_id)
    assert balance == 50_000

    # Add extra money via MoneyService, labor balance should stack
    await services.money.add_money(player.player_id, 10_000)
    assert await services.money.get_balance(player.player_id) == 60_000

    # After cooldown, labor adds again
    past = datetime.now(timezone.utc) - timedelta(
        seconds=constants.LABOR_COOLDOWN_SECONDS + 1
    )
    async with services.labor._session_factory() as session:
        repo = PlayerRepository(session)
        await repo.update_last_labor_at(player.player_id, past)
        await session.commit()

    await services.labor.perform_labor(player.player_id)
    assert await services.money.get_balance(player.player_id) == 110_000


async def test_concurrent_labor_attempts_do_not_bypass_cooldown(services, register):
    """Multiple simultaneous requests should not bypass cooldown."""
    player = await register(tg_id=7009)

    # Try 5 concurrent labor attempts
    results = await asyncio.gather(
        *[services.labor.perform_labor(player.player_id) for _ in range(5)]
    )

    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]

    # Only one should succeed
    assert len(successes) == 1
    assert len(failures) == 4

    balance = await services.money.get_balance(player.player_id)
    assert balance == constants.LABOR_REWARD


async def test_labor_for_missing_player_raises(services):
    with pytest.raises(PlayerNotFoundError):
        await services.labor.perform_labor(999999)

    with pytest.raises(PlayerNotFoundError):
        await services.labor.can_work(999999)


async def test_labor_status_for_new_player(services, register):
    player = await register(tg_id=7010)

    status = await services.labor.can_work(player.player_id)
    assert status.can_work is True
    assert status.remaining_seconds == 0
    assert status.last_labor_at is None
    assert status.reward == 50_000


async def test_labor_handler_messages():
    """Test message formatting — simple, no motivational."""
    from app.bot.messages.labor import labor_cooldown_text, labor_success_text

    success = labor_success_text(50_000, 50_000)
    assert "کارگری انجام شد" in success
    assert "۵۰٬۰۰۰" in success or "50000" in success or "۵۰،۰۰۰" in success or "تومان" in success

    cooldown = labor_cooldown_text(125)
    assert "هنوز زمان کارگری نرسیده" in cooldown
    assert "زمان باقی‌مانده" in cooldown

    cooldown2 = labor_cooldown_text(300)
    assert "۵" in cooldown2 or "5" in cooldown2  # 5 minutes
