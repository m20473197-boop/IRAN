"""Marriage & Family service tests — the whole feature against a real DB.

Every requested scenario is covered end-to-end at the service layer:
proposal → accept/reject → married restrictions → divorce with Mahriyeh
wallet payment → secret cheating with discovery rolls → relationship →
pregnancy → child rows and family counters. Randomness is scripted through
the injectable ``FixedRandom`` source so every dice outcome is exact.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import update as sa_update

from app.core import constants
from app.database.models.marriage import STATUS_ACTIVE, Marriage
from app.database.models.marriage_proposal import STATUS_PENDING, MarriageProposal
from app.game.family.family import FixedRandom
from app.game.shared.errors import PlayerNotFoundError
from app.services.family_service import (
    AlreadyMarriedError,
    CannotForgiveOwnDivorceError,
    CheatingTooSoonError,
    InsufficientMahriyehError,
    LevelTooLowError,
    NoDivorcePendingError,
    NoPendingProposalError,
    NotMarriedError,
    NotSpouseError,
    ProposalBusyError,
    RelationshipTooSoonError,
    SelfMarriageError,
)

# --- Helpers ----------------------------------------------------------------


async def make_player(services, register, tg_id: int, name: str, *, level: int = 5, money: int = 0) -> int:
    result = await register(tg_id=tg_id, username=name, display_name=name)
    if level > 1:
        await services.levels.set_level(result.player_id, level)
    if money:
        await services.money.add_money(result.player_id, money)
    return result.player_id


async def make_couple(services, register, *, mahr=None, tg_a=4101, tg_b=4102):
    """Register two eligible players and marry them via the real flow.

    Note: proposals/marriages consume no randomness — tests can script the
    rng before or after this helper freely.
    """
    a = await make_player(services, register, tg_a, "آرش")
    b = await make_player(services, register, tg_b, "مریم")
    await services.family.create_proposal(sender_player_id=a, receiver_player_id=b, mahr=mahr)
    marriage = await services.family.accept_pending_proposal(b)
    return a, b, marriage


@pytest.fixture(autouse=True)
def no_cooldowns(monkeypatch):
    """Cooldowns would make the tests crawl; zero them (constants read live)."""
    monkeypatch.setattr(constants, "FAMILY_CHEAT_COOLDOWN_SECONDS", 0, raising=False)
    monkeypatch.setattr(constants, "FAMILY_RELATIONSHIP_COOLDOWN_SECONDS", 0, raising=False)


# --- «ازدواج» — proposal -----------------------------------------------------------


async def test_proposal_created_and_visible_to_target(services, register):
    services.family.set_rng(FixedRandom(always="fail"))
    a = await make_player(services, register, 4001, "آرش")
    b = await make_player(services, register, 4002, "مریم")

    result = await services.family.create_proposal(
        sender_player_id=a, receiver_player_id=b, mahr=250_000
    )
    assert result.proposal.mahr == 250_000
    assert result.target_display_name == "مریم"
    assert result.proposer_display_name == "آرش"
    assert result.target_telegram_user_id == 4002

    pending = await services.family.get_pending_proposal_for(b)
    assert pending is not None
    assert pending.sender_player_id == a
    assert pending.mahr == 250_000


async def test_proposal_default_mahr_is_the_constant(services, register):
    a = await make_player(services, register, 4003, "م")
    b = await make_player(services, register, 4004, "ز")
    result = await services.family.create_proposal(sender_player_id=a, receiver_player_id=b)
    assert result.proposal.mahr == constants.FAMILY_DEFAULT_MAHRIYEH


async def test_proposal_to_self_is_rejected(services, register):
    a = await make_player(services, register, 4005, "خودی")
    with pytest.raises(SelfMarriageError):
        await services.family.create_proposal(sender_player_id=a, receiver_player_id=a)


async def test_proposal_requires_level(services, register):
    services.family.set_rng(FixedRandom(always="fail"))
    a = await make_player(services, register, 4006, "لولیک", level=1)
    b = await make_player(services, register, 4007, "لولدو", level=5)
    with pytest.raises(LevelTooLowError) as exc:
        await services.family.create_proposal(sender_player_id=a, receiver_player_id=b)
    assert exc.value.level == 1


async def test_proposal_when_target_already_married(services, register):
    a, b, _ = await make_couple(services, register, tg_a=4008, tg_b=4009)
    c = await make_player(services, register, 4010, "رقیب")

    # A married player cannot marry another person…
    with pytest.raises(AlreadyMarriedError) as own:
        await services.family.create_proposal(sender_player_id=a, receiver_player_id=c)
    assert own.value.married_side == "sender"

    # …and the target being married is reported as such.
    with pytest.raises(AlreadyMarriedError) as side:
        await services.family.create_proposal(sender_player_id=c, receiver_player_id=b)
    assert side.value.married_side == "receiver"


async def test_duplicate_pending_proposal_between_same_pair_blocked(services, register):
    services.family.set_rng(FixedRandom(always="fail"))
    a = await make_player(services, register, 4011, "م" * 2)
    b = await make_player(services, register, 4012, "ز" * 2)
    await services.family.create_proposal(sender_player_id=a, receiver_player_id=b)
    with pytest.raises(ProposalBusyError):
        await services.family.create_proposal(sender_player_id=b, receiver_player_id=a)


async def test_proposal_expires(services, register, monkeypatch):
    a = await make_player(services, register, 4013, "پ")
    b = await make_player(services, register, 4014, "چ")
    await services.family.create_proposal(sender_player_id=a, receiver_player_id=b)

    # Rewind the expiry deadline into the past, then accept must fail.
    async with services.players._session_factory() as session:
        await session.execute(
            sa_update(MarriageProposal)
            .where(MarriageProposal.status == STATUS_PENDING)
            .values(expires_at=datetime(2020, 1, 1))
        )
        await session.commit()

    with pytest.raises(NoPendingProposalError):
        await services.family.accept_pending_proposal(b)
    assert await services.family.get_pending_proposal_for(b) is None


async def test_unknown_proposer_player_not_found(services, register):
    b = await make_player(services, register, 4015, "ب")
    with pytest.raises(PlayerNotFoundError):
        await services.family.create_proposal(sender_player_id=999_999, receiver_player_id=b)


# — Accept / reject —


async def test_accept_creates_marriage_links_and_saves_date(services, register):
    services.family.set_rng(FixedRandom(always="fail"))
    a = await make_player(services, register, 4020, "آرش")
    b = await make_player(services, register, 4021, "مریم")
    await services.family.create_proposal(sender_player_id=a, receiver_player_id=b, mahr=700_000)

    before = datetime.utcnow()
    marriage = await services.family.accept_pending_proposal(b)
    assert marriage.mahr == 700_000
    assert marriage.married_at >= before - timedelta(minutes=5)

    # Both users connected as spouses, marriage date + status on profiles.
    info_a = await services.family.get_family_info(a)
    info_b = await services.family.get_family_info(b)
    assert info_a.marriage_status == "married"
    assert info_b.marriage_status == "married"
    assert info_a.spouse_player_id == b and info_b.spouse_player_id == a
    assert info_a.married_at == marriage.married_at
    assert info_a.mahr == 700_000
    assert info_a.relationship_points == constants.FAMILY_RELATIONSHIP_START_POINTS

    # The proposal is consumed: accepting again finds nothing.
    with pytest.raises(NoPendingProposalError):
        await services.family.accept_pending_proposal(b)


async def test_accept_grants_xp_to_both_spouses(services, register):
    services.family.set_rng(FixedRandom(always="fail"))
    a = await make_player(services, register, 4022, "م")
    b = await make_player(services, register, 4023, "ز")
    xp_before_a = await services.levels.get_xp(a)
    xp_before_b = await services.levels.get_xp(b)

    await services.family.create_proposal(sender_player_id=a, receiver_player_id=b)
    await services.family.accept_pending_proposal(b)

    assert await services.levels.get_xp(a) == xp_before_a + constants.FAMILY_XP_FOR_MARRIAGE
    assert await services.levels.get_xp(b) == xp_before_b + constants.FAMILY_XP_FOR_MARRIAGE
    # the reason lands in the audited XP history of both players
    hist = await services.levels.get_xp_history(a, limit=5)
    assert any(t.reason == constants.FAMILY_XP_FOR_MARRIAGE_REASON for t in hist)


async def test_reject_closes_the_proposal(services, register):
    services.family.set_rng(FixedRandom(always="fail"))
    a = await make_player(services, register, 4024, "م")
    b = await make_player(services, register, 4025, "ز")
    await services.family.create_proposal(sender_player_id=a, receiver_player_id=b)

    proposal = await services.family.reject_pending_proposal(b)
    assert proposal.sender_player_id == a

    assert await services.family.get_pending_proposal_for(b) is None
    with pytest.raises(NoPendingProposalError):
        await services.family.accept_pending_proposal(b)

    # and both players remain free to marry others
    c = await make_player(services, register, 4026, "س")
    result = await services.family.create_proposal(sender_player_id=c, receiver_player_id=a)
    assert result.proposal.id > 0


async def test_answer_without_proposal_raises(services, register):
    b = await make_player(services, register, 4027, "ب")
    with pytest.raises(NoPendingProposalError):
        await services.family.accept_pending_proposal(b)
    with pytest.raises(NoPendingProposalError):
        await services.family.reject_pending_proposal(b)


# — Married restrictions -----------------------------------------------------


async def test_active_marriage_is_unique_at_database_level(services, register):
    """The partial unique index is the last line of defence for monogamy."""
    a, b, _ = await make_couple(services, register, tg_a=4030, tg_b=4031)
    c = await make_player(services, register, 4032, "ثالث")

    from app.database.repositories.marriage_repository import MarriageRepository

    async with services.players._session_factory() as session:
        repo = MarriageRepository(session)
        with pytest.raises(Exception):
            # a direct INSERT bypassing all service checks must still fail:
            # `a` already sits in an active marriage as partner_a.
            await repo.create(player_a=a, player_b=c, mahr=0)
            await session.commit()


async def test_divorce_and_relationship_blocked_for_single_players(services, register):
    single = await make_player(services, register, 4033, "مجرد")
    with pytest.raises(NotMarriedError):
        await services.family.request_or_finalize_divorce(single)
    with pytest.raises(NotMarriedError):
        await services.family.cheat_attempt(single)
    with pytest.raises(NotMarriedError):
        await services.family.relationship_event(single)
    with pytest.raises(NotMarriedError):
        await services.family.forgive_divorce(single)


# — Divorce («طلاق») + Mahriyeh —


async def test_divorce_files_then_finalizes_with_mahr_payment(services, register):
    a, b, marriage = await make_couple(
        services, register, mahr=1_000_000, tg_a=4040, tg_b=4041
    )
    await services.money.add_money(a, 2_000_000)

    first = await services.family.request_or_finalize_divorce(a)
    from app.game.family.dto import DivorceRequestResult, DivorceResult

    assert isinstance(first, DivorceRequestResult)
    assert first.spouse_telegram_user_id == 4041

    second = await services.family.request_or_finalize_divorce(a)
    assert isinstance(second, DivorceResult)
    assert second.mahr == 1_000_000
    assert second.paid_amount == 1_000_000
    assert second.unpaid_debt == 0
    assert second.payer_player_id == a
    assert second.payee_player_id == b

    # Wallet system was used for both sides.
    assert await services.money.get_balance(a) == 1_000_000
    assert await services.money.get_balance(b) == 1_000_000

    # Profiles updated: divorced, spouse link removed.
    info_a = await services.family.get_family_info(a)
    assert info_a.marriage_status == "divorced"
    assert info_a.spouse_player_id is None
    info_b = await services.family.get_family_info(b)
    assert info_b.marriage_status == "divorced"

    # Marriage row kept for history (status flipped, dissolved_at set).
    async with services.players._session_factory() as session:
        row = await session.get(Marriage, marriage.marriage_id)
        assert row.status != STATUS_ACTIVE
        assert row.dissolved_at is not None

    # Divorce history saved.
    records = await services.family.list_divorces_of(a)
    assert len(records) == 1
    assert records[0].mahr == 1_000_000
    assert records[0].paid_amount == 1_000_000
    assert records[0].reason == "divorced"
    # …and also visible to the other side.
    assert len(await services.family.list_divorces_of(b)) == 1


async def test_divorce_without_mahr_money_is_prevented_with_amount(services, register):
    a, b, _ = await make_couple(
        services, register, mahr=50_000_000, tg_a=4042, tg_b=4043
    )
    await services.money.add_money(a, 10_000_000)

    # File the request, then a second «طلاق» tries to finalize — must fail.
    await services.family.request_or_finalize_divorce(a)
    with pytest.raises(InsufficientMahriyehError) as exc:
        await services.family.request_or_finalize_divorce(a)

    assert exc.value.mahr == 50_000_000
    assert exc.value.balance == 10_000_000
    assert exc.value.shortfall == 40_000_000

    # Nothing happened: still married, still money, still pending request.
    assert await services.money.get_balance(a) == 10_000_000
    info = await services.family.get_family_info(a)
    assert info.marriage_status == "married"
    assert info.divorce_pending_by_me is True

    # Save up enough → the second finalize works now.
    await services.money.add_money(a, 40_000_000)
    from app.game.family.dto import DivorceResult

    done = await services.family.request_or_finalize_divorce(a)
    assert isinstance(done, DivorceResult)
    assert done.paid_amount == 50_000_000


async def test_divorce_mahr_zero_needs_no_wallet(services, register):
    a, b, _ = await make_couple(services, register, mahr=0, tg_a=4044, tg_b=4045)
    from app.game.family.dto import DivorceResult

    await services.family.request_or_finalize_divorce(a)
    done = await services.family.request_or_finalize_divorce(a)
    assert isinstance(done, DivorceResult)
    assert done.mahr_waived is True
    assert done.paid_amount == 0


# — Forgiveness («بخشش») ------------------------------------------------------


async def test_forgiveness_cancels_divorce_and_heals(services, register):
    a, b, marriage = await make_couple(services, register, tg_a=4046, tg_b=4047)
    # Start from a damaged (but not collapsed) relationship.
    async with services.players._session_factory() as session:
        row = await session.get(Marriage, marriage.marriage_id)
        row.relationship_points = 65
        await session.commit()
    await services.family.request_or_finalize_divorce(a)

    result = await services.family.forgive_divorce(b)
    assert result.relationship_points_before == 65
    assert result.relationship_points_after == 65 + constants.FAMILY_FORGIVENESS_HEAL
    assert await services.family.list_divorces_of(a) == []

    info_a = await services.family.get_family_info(a)
    assert info_a.marriage_status == "married"
    assert info_a.divorce_pending_by_me is False
    info_b = await services.family.get_family_info(b)
    assert info_b.divorce_requested_by_spouse is False

    # A new filing works again afterwards.
    from app.game.family.dto import DivorceRequestResult

    again = await services.family.request_or_finalize_divorce(b)
    assert isinstance(again, DivorceRequestResult)


async def test_forgive_without_pending_raises(services, register):
    a, b, _ = await make_couple(services, register, tg_a=4048, tg_b=4049)
    with pytest.raises(NoDivorcePendingError):
        await services.family.forgive_divorce(b)
    # And you cannot forgive your own filing.
    await services.family.request_or_finalize_divorce(a)
    with pytest.raises(CannotForgiveOwnDivorceError):
        await services.family.forgive_divorce(a)


# — Cheating («خیانت») ----------------------------------------------------------


async def test_cheat_undiscovered_is_totally_secret(services, register):
    services.family.set_rng(FixedRandom(always="fail"))  # rolls 100: no success, no discovery
    a, b, _ = await make_couple(services, register, tg_a=4050, tg_b=4051)

    result = await services.family.cheat_attempt(a)
    assert result.succeeded is False and result.discovered is False
    assert result.penalty_money == 0 and result.penalty_xp == 0
    info = await services.family.get_family_info(a)
    assert info.cheating_count == 0
    assert info.relationship_points == constants.FAMILY_RELATIONSHIP_START_POINTS


async def test_cheat_success_without_discovery_stays_clean(services, register):
    # success roll 1 (≤55 → yes), discovery roll 100 (>35 → no)
    services.family.set_rng(FixedRandom(rolls=[1, 100]))
    a, b, _ = await make_couple(services, register, tg_a=4052, tg_b=4053)
    await services.money.add_money(a, 1_000_000)

    result = await services.family.cheat_attempt(a)
    assert result.succeeded is True and result.discovered is False
    assert await services.money.get_balance(a) == 1_000_000  # no fine
    info = await services.family.get_family_info(a)
    assert info.cheating_count == 0  # never logged as discovered


async def test_cheat_discovered_applies_consequences_and_notifies(services, register):
    # success 1 → yes; discovery 1 → LOST
    services.family.set_rng(FixedRandom(rolls=[1, 1]))
    a, b, _ = await make_couple(services, register, tg_a=4054, tg_b=4055)
    await services.money.add_money(a, 1_000_000)
    xp_before = (await services.players.get_profile(4054)).xp

    result = await services.family.cheat_attempt(a)
    assert result.discovered is True
    assert result.relationship_points_after == (
        constants.FAMILY_RELATIONSHIP_START_POINTS - constants.FAMILY_CHEAT_RELATIONSHIP_DAMAGE
    )
    # Social penalty through the wallet system.
    assert result.penalty_money == constants.FAMILY_CHEAT_SOCIAL_FINE
    assert await services.money.get_balance(a) == 1_000_000 - constants.FAMILY_CHEAT_SOCIAL_FINE
    # Reputation loss through the XP system.
    assert result.penalty_xp == constants.FAMILY_CHEAT_XP_LOSS
    assert (await services.players.get_profile(4054)).xp == xp_before - constants.FAMILY_CHEAT_XP_LOSS
    # The spouse is identified for a private notification.
    assert result.spouse_telegram_user_id == 4055
    # And it is counted on the marriage row.
    info = await services.family.get_family_info(a)
    assert info.cheating_count == 1
    assert info.relationship_points == result.relationship_points_after

    # Both sides' family histories carry the event.
    hist_a = await services.family.list_history(a, limit=20)
    hist_b = await services.family.list_history(b, limit=20)
    assert any(e.event_type == "cheat_discovered" for e in hist_a)
    assert any(e.event_type == "cheat_discovered" for e in hist_b)


async def test_cheat_fine_never_overdraws_the_wallet(services, register):
    services.family.set_rng(FixedRandom(rolls=[1, 1]))
    a, b, _ = await make_couple(services, register, tg_a=4056, tg_b=4057)
    await services.money.add_money(a, 100)  # far below the fine

    result = await services.family.cheat_attempt(a)
    assert result.discovered is True
    assert result.penalty_money == 100  # capped at the balance
    assert await services.money.get_balance(a) == 0
    assert await services.money.get_balance(b) == 0


async def test_cheat_cooldown(services, register, monkeypatch):
    monkeypatch.setattr(constants, "FAMILY_CHEAT_COOLDOWN_SECONDS", 3600)
    services.family.set_rng(FixedRandom(rolls=[1, 1]))
    a, b, _ = await make_couple(services, register, tg_a=4058, tg_b=4059)
    await services.family.cheat_attempt(a)
    with pytest.raises(CheatingTooSoonError) as exc:
        await services.family.cheat_attempt(a)
    assert exc.value.wait_seconds > 3000


async def test_cheat_divorce_possibility_shifts_mahr_liability(services, register):
    """After the relationship collapses, the betrayed spouse divorces for free."""
    a, b, _ = await make_couple(
        services, register, mahr=2_000_000, tg_a=4060, tg_b=4061
    )
    # The cheater can cover the Mahriyeh even after the social fines
    # (3 × FAMILY_CHEAT_SOCIAL_FINE = 900k → 2.0M remain).
    await services.money.add_money(b, 2_000_000 + 3 * constants.FAMILY_CHEAT_SOCIAL_FINE)

    # Three discovered betrayals burn 100 → 65 → 30 → 0 (rng always succeeds).
    services.family.set_rng(FixedRandom(always="success"))
    for _ in range(3):
        result = await services.family.cheat_attempt(b)
    assert result.divorce_possible is True
    assert result.relationship_points_after == constants.FAMILY_RELATIONSHIP_MIN_POINTS

    # The betrayed spouse files, then confirms.
    from app.game.family.dto import DivorceResult

    await services.family.request_or_finalize_divorce(a)
    done = await services.family.request_or_finalize_divorce(a)
    assert isinstance(done, DivorceResult)
    assert done.cheater_liable is True
    assert done.payer_player_id == b and done.payee_player_id == a
    assert done.paid_amount == 2_000_000

    # Wallet reflects the penalty: the CHEATER paid.
    assert await services.money.get_balance(a) == 2_000_000
    assert await services.money.get_balance(b) == 0
    assert done.unpaid_debt == 0
    records = await services.family.list_divorces_of(a)
    assert records[0].reason == "cheating_discovered"


async def test_cheater_broke_records_unpaid_debt(services, register):
    a, b, _ = await make_couple(
        services, register, mahr=10_000_000, tg_a=4062, tg_b=4063
    )
    await services.money.add_money(a, 5_000_000)  # betrayed side: unrelated
    await services.money.add_money(b, 1_000_000)  # cheater: cannot cover

    services.family.set_rng(FixedRandom(always="success"))
    for _ in range(3):
        await services.family.cheat_attempt(b)  # fine 300k each → 1M left after
    # balance now 1_000_000 - 3*300_000 = 100_000 (capped by wallet logic)

    await services.family.request_or_finalize_divorce(a)
    from app.game.family.dto import DivorceResult

    done = await services.family.request_or_finalize_divorce(a)
    assert isinstance(done, DivorceResult)
    assert done.cheater_liable is True
    # 1_000_000 − 3 fines (900_000) = 100_000 paid; the rest is recorded debt.
    assert done.paid_amount == 100_000
    assert done.unpaid_debt == 9_900_000
    assert done.paid_amount + done.unpaid_debt == 10_000_000
    assert await services.money.get_balance(b) == 0
    assert await services.money.get_balance(a) == 5_000_000 + 100_000
    records = await services.family.list_divorces_of(b)
    assert records[0].unpaid_debt == 10_000_000 - records[0].paid_amount


async def test_cheater_initiator_still_pays_normally(services, register):
    """A caught cheater who files for divorce pays the Mahriyeh as usual."""
    a, b, _ = await make_couple(
        services, register, mahr=1_000_000, tg_a=4064, tg_b=4065
    )
    await services.money.add_money(b, 3_000_000)
    services.family.set_rng(FixedRandom(always="success"))
    for _ in range(3):
        await services.family.cheat_attempt(b)  # 3 × 300k fine
    # balance: 3_000_000 − 900_000 fines = 2_100_000

    from app.game.family.dto import DivorceResult

    await services.family.request_or_finalize_divorce(b)  # cheater files
    done = await services.family.request_or_finalize_divorce(b)
    assert isinstance(done, DivorceResult)
    assert done.payer_player_id == b  # the initiator pays their own way out
    assert done.paid_amount == 1_000_000
    assert await services.money.get_balance(b) == 1_100_000
    assert await services.money.get_balance(a) == 1_000_000


# — Relationship («رابطه») + children ———————————————————————————————————————————


async def test_relationship_event_heals_and_is_recorded(services, register):
    services.family.set_rng(FixedRandom(always="fail"))
    a, b, marriage = await make_couple(services, register, tg_a=4070, tg_b=4071)
    # Damage first so the heal is observable.
    async with services.players._session_factory() as session:
        row = await session.get(Marriage, marriage.marriage_id)
        row.relationship_points = 50
        await session.commit()

    result = await services.family.relationship_event(a)
    assert result.pregnant is False
    assert result.satisfaction == 50 + constants.FAMILY_RELATIONSHIP_EVENT_HEAL
    assert result.partner_player_id == b
    assert result.partner_telegram_user_id == 4071

    async with services.players._session_factory() as session:
        from app.database.repositories.relationship_event_repository import (
            RelationshipEventRepository,
        )

        rows = await RelationshipEventRepository(session).list_by_marriage(marriage.marriage_id)
        assert len(rows) == 1
        assert rows[0].outcome == "event"


async def test_relationship_requires_spouse_match_on_reply(services, register):
    services.family.set_rng(FixedRandom(always="fail"))
    a, b, _ = await make_couple(services, register, tg_a=4072, tg_b=4073)
    stranger = await make_player(services, register, 4074, "غریبه")

    with pytest.raises(NotSpouseError):
        await services.family.relationship_event(a, partner_hint_player_id=stranger)
    # the spouse themselves passes
    ok = await services.family.relationship_event(a, partner_hint_player_id=b)
    assert ok.marriage_id > 0


async def test_relationship_cooldown_blocks_second_event(services, register, monkeypatch):
    monkeypatch.setattr(constants, "FAMILY_RELATIONSHIP_COOLDOWN_SECONDS", 7200)
    services.family.set_rng(FixedRandom(always="fail"))
    a, b, _ = await make_couple(services, register, tg_a=4075, tg_b=4076)
    await services.family.relationship_event(a)
    with pytest.raises(RelationshipTooSoonError) as exc:
        await services.family.relationship_event(b)
    assert exc.value.wait_seconds > 3600


async def test_pregnancy_creates_child_and_updates_family(services, register):
    services.family.set_rng(FixedRandom(always="success"))  # every roll ≤ chance
    a, b, marriage = await make_couple(services, register, tg_a=4077, tg_b=4078)
    xp_a_before = (await services.players.get_profile(4077)).xp
    xp_b_before = (await services.players.get_profile(4078)).xp

    result = await services.family.relationship_event(a)
    assert result.pregnant is True
    child = result.child
    assert child is not None
    assert child.father_player_id in (a, b)
    assert child.mother_player_id in (a, b)
    assert {child.father_player_id, child.mother_player_id} == {a, b}
    assert child.birth_date is not None
    assert child.gender in ("boy", "girl")

    # Children count updated on the marriage and on both player profiles.
    info_a = await services.family.get_family_info(a)
    info_b = await services.family.get_family_info(b)
    assert info_a.children_count == 1 and info_b.children_count == 1
    assert len(info_a.children) == 1
    async with services.players._session_factory() as session:
        row = await session.get(Marriage, marriage.marriage_id)
        assert row.children_count == 1

    # XP for both parents through the LevelService.
    assert (await services.players.get_profile(4077)).xp == xp_a_before + constants.FAMILY_XP_FOR_CHILD_BIRTH
    assert (await services.players.get_profile(4078)).xp == xp_b_before + constants.FAMILY_XP_FOR_CHILD_BIRTH

    # The event was upgraded to a birth and history carries it.
    async with services.players._session_factory() as session:
        from app.database.repositories.relationship_event_repository import (
            RelationshipEventRepository,
        )

        rows = await RelationshipEventRepository(session).list_by_marriage(marriage.marriage_id)
        assert rows[0].outcome == "birth"
    hist = await services.family.list_history(a)
    assert any(e.event_type == "birth" and child.name in e.details for e in hist)


async def test_no_pregnancy_no_child(services, register):
    services.family.set_rng(FixedRandom(always="fail"))
    a, b, _ = await make_couple(services, register, tg_a=4079, tg_b=4080)
    result = await services.family.relationship_event(a)
    assert result.pregnant is False and result.child is None
    assert (await services.family.get_family_info(a)).children_count == 0
    assert await services.family.list_children_of(a) == []


async def test_children_survive_divorce_and_counters_hold(services, register):
    services.family.set_rng(FixedRandom(always="success"))
    a, b, _ = await make_couple(
        services, register, mahr=0, tg_a=4081, tg_b=4082
    )
    await services.family.relationship_event(a)
    await services.family.relationship_event(b)
    assert (await services.family.get_family_info(a)).children_count == 2

    from app.game.family.dto import DivorceResult

    await services.family.request_or_finalize_divorce(a)
    done = await services.family.request_or_finalize_divorce(a)
    assert isinstance(done, DivorceResult)
    # kids keep their parents; the divorced players still list them
    assert len(await services.family.list_children_of(a)) == 2
    assert len(await services.family.list_children_of(b)) == 2


# — Profile integration ————————————————————————————————————————————————————————


async def test_profile_exposes_marriage_data(services, register):
    a, b, marriage = await make_couple(
        services, register, mahr=800_000, tg_a=4090, tg_b=4091
    )
    profile = await services.players.get_profile(4090)
    assert profile.marriage_status == "married"
    assert profile.spouse_display_name == "مریم"
    assert profile.married_at == marriage.married_at
    assert profile.children_count == 0

    from app.bot.messages.player import profile_text

    text = profile_text(profile)
    assert "وضعیت تأهل" in text
    assert "مریم" in text
    assert "فرزندان" in text


async def test_family_snapshot_never_raises_for_unknown(services):
    snap = await services.family.get_snapshot_by_telegram_user_id(999_999_999)
    assert snap is None


async def test_remarriage_after_divorce_allowed(services, register):
    services.family.set_rng(FixedRandom(always="fail"))
    a, b, _ = await make_couple(services, register, mahr=0, tg_a=4092, tg_b=4093)
    await services.family.request_or_finalize_divorce(a)
    from app.game.family.dto import DivorceResult

    done = await services.family.request_or_finalize_divorce(a)
    assert isinstance(done, DivorceResult)

    # a can now propose to b again (both divorced → eligible)
    res = await services.family.create_proposal(sender_player_id=a, receiver_player_id=b)
    assert res.proposal.id > 0
    second = await services.family.accept_pending_proposal(b)
    assert second.marriage_id > 0  # a NEW marriage row, old history intact
    assert await services.family.list_divorces_of(a) != []
