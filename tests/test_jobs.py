"""Job and Income System tests — «خر حمالی», time-based salary.

The rename and the catalog swap must not change a single mechanic: every
existing flow (apply → timer → settlement with employer events → history →
leave) is re-tested here against the six canonical jobs, plus new tests for
the catalog itself and for the once-per-version seeding guard.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.core import constants
from app.database.models.job import Job
from app.database.models.player_job import PlayerJob
from app.database.repositories.job_repository import JobRepository
from app.services import ServiceRegistry
from app.services.job_service import (
    AlreadyHasJobError,
    JobNotFoundError,
    JobNotEnoughTimeError,
    JobRequirementError,
    JobService,
    NoJobError,
)

# The exact catalog the players get.
EXPECTED_CATALOG = {
    "بنایی": (1, 80_000),
    "رستوران": (1, 70_000),
    "فروشندگی": (2, 90_000),
    "پیک موتوری": (3, 120_000),
    "اسنپ": (5, 160_000),
    "کارمند بانک": (8, 220_000),
}


async def _set_started_at(services, player_id: int, minutes_ago: int) -> None:
    """Rewind the work-start clock so elapsed time is deterministic."""
    past = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    async with services.jobs._session_factory() as session:
        stmt = (
            update(PlayerJob)
            .where(PlayerJob.player_id == player_id)
            .values(started_at=past)
        )
        await session.execute(stmt, execution_options={"synchronize_session": False})
        await session.commit()


def _by_name(jobs, name):
    return next(j for j in jobs if j.name == name)


# --- The «خر حمالی» catalog --------------------------------------------------


async def test_catalog_is_exactly_the_six_named_jobs(services, db):
    jobs = await services.jobs.ensure_initial_jobs()
    assert len(jobs) == 6

    async with db.session_factory() as session:
        all_jobs = (await session.execute(select(Job))).scalars().all()
    assert len(all_jobs) == 6
    assert {j.name for j in all_jobs} == set(EXPECTED_CATALOG)

    for job in jobs:
        level, hourly = EXPECTED_CATALOG[job.name]
        assert job.required_level == level, job.name
        assert job.hourly_salary == hourly, job.name
        assert job.description.strip() != ""
        assert job.employer.strip() != ""
        # legacy columns stay consistent with the hourly rate
        assert job.salary == hourly
        assert job.is_active is True


async def test_legacy_jobs_are_no_longer_selectable(services):
    jobs = await services.jobs.get_available_jobs()
    names = {j.name for j in jobs}
    assert names.isdisjoint(constants.JOB_RETIRED_NAMES)


async def test_each_job_has_hourly_salary_and_employer(services):
    jobs = await services.jobs.get_available_jobs()
    assert len(jobs) >= 6
    for job in jobs:
        assert job.hourly_salary > 0
        assert job.employer.strip() != ""


async def test_catalog_seeding_is_version_guarded_and_preserves_admin_edits(
    services, db
):
    """Second boot is a no-op: tuned admin values and custom jobs survive."""
    await services.jobs.ensure_initial_jobs()
    async with db.session_factory() as session:
        repo = JobRepository(session)
        banaei = await repo.get_by_name("بنایی")
        await repo.update_fields(banaei.id, hourly_salary=123_456)
        await repo.create_job(
            name="آشپزی", description="test", salary=1, cooldown=0, required_level=1,
            hourly_salary=500_000, employer="test",
        )
        await session.commit()

    jobs = await services.jobs.ensure_initial_jobs()  # "restart"
    by_name = {j.name: j for j in jobs}
    assert by_name["بنایی"].hourly_salary == 123_456  # admin edit kept
    assert "آشپزی" in by_name and by_name["آشپزی"].is_active


async def test_applying_for_a_job_saves_start_time(services, register):
    player = await register(tg_id=8002)

    jobs = await services.jobs.get_available_jobs()
    job = _by_name(jobs, "بنایی")

    result = await services.jobs.apply_job(player.player_id, job.id)

    assert result.success is True
    assert result.job_id == job.id
    assert result.job_name == job.name
    assert result.employer == job.employer
    assert result.hourly_salary == job.hourly_salary

    # Check player job exists with a saved work start time
    player_job = await services.jobs.get_player_job(player.player_id)
    assert player_job is not None
    assert player_job.job_id == job.id
    assert player_job.job_name == job.name
    assert player_job.employer == job.employer
    assert player_job.hourly_salary == job.hourly_salary
    assert player_job.started_at is not None
    assert player_job.total_earnings == 0
    # Just started — no meaningful accrued salary yet.
    assert player_job.worked_minutes == 0
    assert player_job.accrued_salary == 0


async def test_preventing_multiple_active_jobs(services, register):
    player = await register(tg_id=8003)

    jobs = await services.jobs.get_available_jobs()
    first = _by_name(jobs, "بنایی")
    second = _by_name(jobs, "فروشندگی")

    await services.levels.set_level(player.player_id, 2)  # for فروشندگی
    await services.jobs.apply_job(player.player_id, first.id)

    # Try to apply for another job — should fail
    with pytest.raises(AlreadyHasJobError):
        await services.jobs.apply_job(player.player_id, second.id)

    # Still has first job
    pj = await services.jobs.get_player_job(player.player_id)
    assert pj is not None
    assert pj.job_id == first.id


async def test_checking_job_requirements(services, register):
    player = await register(tg_id=8004)  # level 1

    jobs = await services.jobs.get_available_jobs()
    snapp = _by_name(jobs, "اسنپ")
    assert snapp.required_level == 5

    with pytest.raises(JobRequirementError):
        await services.jobs.apply_job(player.player_id, snapp.id)

    # Level up to 5
    await services.levels.set_level(player.player_id, 5)
    assert await services.levels.get_level(player.player_id) == 5

    # Now should succeed
    result = await services.jobs.apply_job(player.player_id, snapp.id)
    assert result.success is True

    # Highest tier really requires level 8
    bank = _by_name(jobs, "کارمند بانک")
    assert bank.required_level == 8
    await services.jobs.leave_job(player.player_id)  # drop اسنپ first
    await services.levels.set_level(player.player_id, 7)
    with pytest.raises(JobRequirementError):
        await services.jobs.apply_job(player.player_id, bank.id)
    await services.levels.set_level(player.player_id, 8)
    assert (await services.jobs.apply_job(player.player_id, bank.id)).success is True

    # Test non-existent job
    with pytest.raises(JobNotFoundError):
        await services.jobs.apply_job(player.player_id, 999999)


async def test_settlement_normal_payment(services, register, monkeypatch):
    player = await register(tg_id=8005)

    jobs = await services.jobs.get_available_jobs()
    job = _by_name(jobs, "بنایی")  # 80_000/hour
    await services.jobs.apply_job(player.player_id, job.id)

    await _set_started_at(services, player.player_id, minutes_ago=120)  # 2 hours
    monkeypatch.setattr(services.jobs, "_roll_employer_event", lambda: ("normal", 0))

    result = await services.jobs.settle_with_employer(player.player_id)

    assert result.event_type == "normal"
    assert result.status == "paid"
    assert result.paid is True
    assert result.worked_minutes == 120
    assert result.hourly_salary == 80_000
    assert result.gross_salary == 160_000
    assert result.final_amount == result.gross_salary
    assert result.bonus_amount == 0
    assert result.penalty_amount == 0

    # Paid through the wallet
    assert result.balance_after == result.gross_salary
    assert await services.money.get_balance(player.player_id) == result.gross_salary

    # Work timer reset
    pj = await services.jobs.get_player_job(player.player_id)
    assert pj is not None
    assert pj.worked_minutes == 0
    assert pj.total_earnings == result.gross_salary


async def test_settlement_restaurant_rate(services, register, monkeypatch):
    """رستوران pays 70_000/hour — the accrual math reads the job row."""
    player = await register(tg_id=8011)

    jobs = await services.jobs.get_available_jobs()
    job = _by_name(jobs, "رستوران")
    await services.jobs.apply_job(player.player_id, job.id)

    await _set_started_at(services, player.player_id, minutes_ago=90)  # 1.5 hours
    monkeypatch.setattr(services.jobs, "_roll_employer_event", lambda: ("normal", 0))

    result = await services.jobs.settle_with_employer(player.player_id)
    assert result.hourly_salary == 70_000
    assert result.gross_salary == 70_000 * 90 // 60  # 105_000
    assert await services.money.get_balance(player.player_id) == 105_000


async def test_settlement_bonus_payment(services, register, monkeypatch):
    player = await register(tg_id=8006)

    jobs = await services.jobs.get_available_jobs()
    job = _by_name(jobs, "بنایی")
    await services.jobs.apply_job(player.player_id, job.id)

    await _set_started_at(services, player.player_id, minutes_ago=60)  # 1 hour
    monkeypatch.setattr(services.jobs, "_roll_employer_event", lambda: ("bonus", 20))

    result = await services.jobs.settle_with_employer(player.player_id)

    gross = 80_000
    assert result.event_type == "bonus"
    assert result.bonus_percent == 20
    assert result.bonus_amount == gross * 20 // 100
    assert result.final_amount == gross + result.bonus_amount
    assert result.paid is True
    assert await services.money.get_balance(player.player_id) == result.final_amount


async def test_settlement_mistake_penalty(services, register, monkeypatch):
    player = await register(tg_id=8007)

    jobs = await services.jobs.get_available_jobs()
    job = _by_name(jobs, "بنایی")
    await services.jobs.apply_job(player.player_id, job.id)

    # 2 hours -> 160_000 gross, 30% penalty -> 112_000
    await _set_started_at(services, player.player_id, minutes_ago=120)
    monkeypatch.setattr(services.jobs, "_roll_employer_event", lambda: ("mistake", 30))

    result = await services.jobs.settle_with_employer(player.player_id)

    gross = 160_000
    assert result.event_type == "mistake"
    assert result.penalty_percent == 30
    assert result.penalty_amount == gross * 30 // 100  # 48_000
    assert result.final_amount == gross - result.penalty_amount  # 112_000
    assert result.paid is True
    assert await services.money.get_balance(player.player_id) == result.final_amount


async def test_settlement_delayed_payment_comes_later(services, register, monkeypatch):
    player = await register(tg_id=8008)

    jobs = await services.jobs.get_available_jobs()
    job = _by_name(jobs, "بنایی")
    await services.jobs.apply_job(player.player_id, job.id)

    await _set_started_at(services, player.player_id, minutes_ago=120)
    monkeypatch.setattr(services.jobs, "_roll_employer_event", lambda: ("delayed", 0))

    first = await services.jobs.settle_with_employer(player.player_id)

    assert first.event_type == "delayed"
    assert first.status == "delayed"
    assert first.paid is False
    assert first.final_amount == 0

    # No money received immediately
    assert await services.money.get_balance(player.player_id) == 0

    # Work timer NOT reset — the accrued hours are still pending
    pj = await services.jobs.get_player_job(player.player_id)
    assert pj is not None
    assert pj.worked_minutes >= 120

    # Later, the employer pays normally — the delayed work is included.
    await _set_started_at(services, player.player_id, minutes_ago=120)
    monkeypatch.setattr(services.jobs, "_roll_employer_event", lambda: ("normal", 0))
    second = await services.jobs.settle_with_employer(player.player_id)

    gross = 160_000
    assert second.paid is True
    assert second.final_amount == gross
    assert await services.money.get_balance(player.player_id) == gross


async def test_settlement_before_one_minute_is_rejected(services, register):
    player = await register(tg_id=8009)

    jobs = await services.jobs.get_available_jobs()
    job = _by_name(jobs, "بنایی")
    await services.jobs.apply_job(player.player_id, job.id)

    with pytest.raises(JobNotEnoughTimeError):
        await services.jobs.settle_with_employer(player.player_id)

    # Nothing was paid, timer still running from the start.
    assert await services.money.get_balance(player.player_id) == 0


async def test_employer_event_rolls_stay_in_bounds():
    # Exercise the real random roller with a seeded RNG.
    service = JobService(None, rng=random.Random(12345))  # type: ignore[arg-type]
    valid_types = {"normal", "bonus", "mistake", "delayed"}
    for _ in range(500):
        event_type, percent = service._roll_employer_event()
        assert event_type in valid_types
        if event_type == "mistake":
            assert (
                constants.MISTAKE_PENALTY_MIN_PERCENT
                <= percent
                <= constants.MISTAKE_PENALTY_MAX_PERCENT
            )
        elif event_type == "bonus":
            assert constants.BONUS_MIN_PERCENT <= percent <= constants.BONUS_MAX_PERCENT
        else:
            assert percent == 0


async def test_all_events_are_saved(services, register, monkeypatch):
    player = await register(tg_id=8010)

    jobs = await services.jobs.get_available_jobs()
    job = _by_name(jobs, "بنایی")
    await services.jobs.apply_job(player.player_id, job.id)

    rolls = [
        ("normal", 0),
        ("bonus", 15),
        ("mistake", 40),
        ("delayed", 0),
    ]
    for event, percent in rolls:
        await _set_started_at(services, player.player_id, minutes_ago=60)
        monkeypatch.setattr(
            services.jobs, "_roll_employer_event", lambda e=event, p=percent: (e, p)
        )
        await services.jobs.settle_with_employer(player.player_id)

    events = await services.jobs.get_salary_events(player.player_id, limit=20)
    # Newest first.
    assert len(events) == 4
    kinds = {e.event_type for e in events}
    assert kinds == {"normal", "bonus", "mistake", "delayed"}

    delayed = next(e for e in events if e.event_type == "delayed")
    assert delayed.status == "delayed"
    assert delayed.final_amount == 0
    assert delayed.gross_salary > 0

    mistake = next(e for e in events if e.event_type == "mistake")
    assert mistake.penalty_percent == 40
    assert mistake.penalty_amount > 0
    assert mistake.final_amount == mistake.gross_salary - mistake.penalty_amount

    bonus = next(e for e in events if e.event_type == "bonus")
    assert bonus.bonus_percent == 15
    assert bonus.final_amount == bonus.gross_salary + bonus.bonus_amount

    assert all(e.employer == job.employer for e in events)


async def test_database_persistence(db, services, register):
    player = await register(tg_id=8009)

    jobs = await services.jobs.get_available_jobs()
    job = _by_name(jobs, "بنایی")

    await services.jobs.apply_job(player.player_id, job.id)
    await _set_started_at(services, player.player_id, minutes_ago=60)
    # Deterministic normal payment for this isolated test
    services.jobs._roll_employer_event = lambda: ("normal", 0)
    await services.jobs.settle_with_employer(player.player_id)

    # Simulate restart
    new_services = ServiceRegistry(db.session_factory)
    await new_services.jobs.ensure_initial_jobs()  # what main.py does on boot

    # Job should persist
    pj = await new_services.jobs.get_player_job(player.player_id)
    assert pj is not None
    assert pj.job_id == job.id
    assert pj.total_earnings == 80_000

    # Events should persist
    events = await new_services.jobs.get_salary_events(player.player_id)
    assert len(events) == 1
    assert events[0].event_type == "normal"
    assert events[0].gross_salary == 80_000

    # Money should persist
    assert await new_services.money.get_balance(player.player_id) == 80_000

    # Available jobs should still exist (and the same six)
    all_jobs = await new_services.jobs.get_available_jobs()
    assert {j.name for j in all_jobs} == set(EXPECTED_CATALOG)


async def test_leave_job(services, register):
    player = await register(tg_id=8010)

    jobs = await services.jobs.get_available_jobs()
    job = _by_name(jobs, "پیک موتوری")

    await services.levels.set_level(player.player_id, 3)
    await services.jobs.apply_job(player.player_id, job.id)
    await _set_started_at(services, player.player_id, minutes_ago=60)
    services.jobs._roll_employer_event = lambda: ("normal", 0)
    await services.jobs.settle_with_employer(player.player_id)

    # Leave
    leave_result = await services.jobs.leave_job(player.player_id)
    assert leave_result.success is True
    assert leave_result.total_earnings == 120_000

    # No job now
    assert await services.jobs.get_player_job(player.player_id) is None

    # Settle should fail
    with pytest.raises(NoJobError):
        await services.jobs.settle_with_employer(player.player_id)

    # Can apply again
    result = await services.jobs.apply_job(player.player_id, job.id)
    assert result.success is True


# --- Player-facing rename --------------------------------------------------------


def test_job_system_is_named_khar_hammali():
    from app.bot.keyboards.main_menu import BUTTON_JOBS

    assert constants.JOB_SYSTEM_TITLE == "خر حمالی"
    assert BUTTON_JOBS == "💼 خر حمالی"
    assert "شغل" not in BUTTON_JOBS


def test_menu_and_list_texts_use_the_new_name():
    from app.bot.messages.job import jobs_menu_text, my_job_text

    assert "خر حمالی" in jobs_menu_text()
    assert "شغل" not in jobs_menu_text()

    assert "کاری نداری" in my_job_text(None)
    assert "شغل" not in my_job_text(None)


def test_jobs_list_text_renders_new_catalog():
    from app.bot.messages.job import jobs_list_text

    class _J:
        name = "بنایی"
        description = "d"
        employer = "e"
        hourly_salary = 80_000
        required_level = 1

    text = jobs_list_text([_J()])
    assert "لیست کارهای موجود" in text
    assert "بنایی" in text
    assert "شغل" not in text


async def test_apply_error_when_inactive_job(services, db, register):
    """A job row that exists but is inactive cannot be applied for anymore."""
    async with db.session_factory() as session:
        repo = JobRepository(session)
        custom = await repo.create_job(
            name="نقاشی", description="t", salary=1, cooldown=0, required_level=1
        )
        custom_id = custom.id  # read before update_fields expires the cache
        await repo.update_fields(custom_id, is_active=False)
        await session.commit()

    player = await register(tg_id=8012)
    with pytest.raises(JobNotFoundError):
        await services.jobs.apply_job(player.player_id, custom_id)
