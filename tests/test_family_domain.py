"""Pure domain tests for the Marriage & Family rules (no DB, no Telegram)."""

from __future__ import annotations

import random

from app.core import constants
from app.game.family.family import (
    FixedRandom,
    RandomModuleSource,
    after_cheat_discovered,
    after_forgiveness,
    after_relationship_event,
    divorce_payer_is_cheater,
    roll_cheat_attempt,
    roll_percent,
    roll_pregnancy,
    sanity_check_mahr,
)


# --- FixedRandom ----------------------------------------------------------------


def test_fixedrandom_scripts_exact_percent_rolls():
    rng = FixedRandom([1, 100, 55])
    assert roll_percent(rng, 55) == (True, 1)
    assert roll_percent(rng, 35) == (False, 100)
    assert roll_percent(rng, 55) == (True, 55)


def test_fixedrandom_always_modes():
    win = FixedRandom(always="success")
    lose = FixedRandom(always="fail")
    for _ in range(5):
        assert roll_percent(win, 1) == (True, 1)
        assert roll_percent(lose, 99) == (False, 100)


def test_cheat_roll_combinations_are_all_reachable():
    rng = FixedRandom([100, 1])  # fail, but discovered
    succeeded, discovered, sr, dr = roll_cheat_attempt(rng)
    assert succeeded is False and discovered is True
    assert (sr, dr) == (100, 1)

    rng = FixedRandom([1, 1])  # success and discovery
    assert roll_cheat_attempt(rng)[:2] == (True, True)


def test_production_source_uses_stdlib_bounds():
    random.seed(42)
    rng = RandomModuleSource()
    for _ in range(50):
        assert 1 <= rng.randint(1, 100) <= 100
    assert rng.choice([7]) == 7


# --- Game rules -------------------------------------------------------------------


def test_cheat_discovery_burns_relationship_and_clamps_at_floor():
    start = constants.FAMILY_RELATIONSHIP_START_POINTS
    hurt = after_cheat_discovered(start)
    assert hurt == start - constants.FAMILY_CHEAT_RELATIONSHIP_DAMAGE
    assert after_cheat_discovered(hurt) > 0 or hurt - constants.FAMILY_CHEAT_RELATIONSHIP_DAMAGE < 0
    # one hit from the floor: clamped to the minimum, never negative
    floor_edge = constants.FAMILY_CHEAT_RELATIONSHIP_DAMAGE
    assert after_cheat_discovered(floor_edge) == constants.FAMILY_RELATIONSHIP_MIN_POINTS


def test_forgiveness_heals_capped_and_half_heals_from_floor():
    assert after_forgiveness(65) == 65 + constants.FAMILY_FORGIVENESS_HEAL
    assert after_forgiveness(100) == 100
    assert after_forgiveness(0) == constants.FAMILY_FORGIVENESS_HEAL // 2


def test_relationship_event_heals_capped():
    assert after_relationship_event(50) == 50 + constants.FAMILY_RELATIONSHIP_EVENT_HEAL
    assert after_relationship_event(100) == 100
    # a collapsed relationship only gets a token heal
    assert after_relationship_event(0) >= 1


def test_pregnancy_roll_uses_the_configured_chance():
    rng = FixedRandom([constants.FAMILY_PREGNANCY_CHANCE])
    assert roll_pregnancy(rng) == (True, constants.FAMILY_PREGNANCY_CHANCE)
    rng = FixedRandom([constants.FAMILY_PREGNANCY_CHANCE + 1])
    assert roll_pregnancy(rng) == (False, constants.FAMILY_PREGNANCY_CHANCE + 1)


def test_mahr_liability_only_for_the_proven_innocent_betrayed_spouse():
    kw = dict(
        initiator_player_id=1,
        other_player_id=2,
        relationship_points=constants.FAMILY_RELATIONSHIP_MIN_POINTS,
        mahr=500_000,
    )
    # betrayed spouse files against a proven cheater → the cheater pays
    assert divorce_payer_is_cheater(**kw, initiator_caught_count=0, other_caught_count=1)
    # relationship not yet collapsed → the initiator pays as usual
    assert not divorce_payer_is_cheater(
        **{**kw, "relationship_points": 65},
        initiator_caught_count=0,
        other_caught_count=3,
    )
    # both cheated → the filer pays (no free ride for the guilty side)
    assert not divorce_payer_is_cheater(
        **kw, initiator_caught_count=1, other_caught_count=3
    )
    # nothing proven → normal rule
    assert not divorce_payer_is_cheater(
        **kw, initiator_caught_count=0, other_caught_count=0
    )
    # zero Mahriyeh → no liability games
    assert not divorce_payer_is_cheater(
        **{**kw, "mahr": 0}, initiator_caught_count=0, other_caught_count=2
    )


def test_mahr_sanity_bounds():
    assert sanity_check_mahr(1_000_000) == 1_000_000
    assert sanity_check_mahr(-42) == constants.FAMILY_MAHR_MIN
    assert sanity_check_mahr(10**15) == constants.FAMILY_MAHR_MAX
