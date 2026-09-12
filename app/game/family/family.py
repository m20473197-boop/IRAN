"""Pure Marriage & Family rules (no database, no Telegram).

Everything random in the family system is decided here, through an explicit
*random source* so tests (and a future admin) can make outcomes
deterministic:

    rng = FixedRandom([1, 1, 1])     # every percent roll succeeds
    rng = FixedRandom([50, 50, 50])  # every percent roll fails

Percent rolls are the game's convention: an event happens when
``roll <= chance_percent``. ``random_module`` behaves exactly like Python's
``random`` — that is what production uses.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from app.core import constants

# --- Random sources ------------------------------------------------------------


class RandomSource:
    """Minimal contract every random source used by the family system obeys."""

    def randint(self, low: int, high: int) -> int:  # pragma: no cover - interface
        raise NotImplementedError

    def choice(self, seq):  # pragma: no cover - interface
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class RandomModuleSource(RandomSource):
    """Production source — delegates to the stdlib ``random`` module."""

    def randint(self, low: int, high: int) -> int:
        return random.randint(low, high)

    def choice(self, seq):
        return random.choice(seq)


@dataclass(slots=True)
class FixedRandom(RandomSource):
    """Deterministic source for tests: pops a pre-scripted sequence of rolls.

    Each scripted value is consumed by the next roll (``randint``) and a
    percent event happens when ``value <= chance``::

        rng = FixedRandom([1, 100, 1])   # success, discovery-no, pregnancy-yes

    When the script runs out the behaviour is configurable:
    ``always="success"`` / ``always="fail"`` repeat forever (the friendly
    mode for tests), otherwise stdlib randomness keeps the game alive.
    """

    rolls: list[int] = field(default_factory=list)
    always: str | None = None  # ``"success"`` | ``"fail"`` | None

    def __post_init__(self) -> None:
        self.rolls = list(self.rolls)

    def _next(self) -> int | None:
        if self.rolls:
            return self.rolls.pop(0)
        if self.always == "success":
            return 1
        if self.always == "fail":
            return 100
        return None

    def randint(self, low: int, high: int) -> int:
        value = self._next()
        if value is None:
            return random.randint(low, high)
        return value if low <= value <= high else low

    def choice(self, seq):
        value = self._next()
        if value is None:
            return random.choice(seq)
        return seq[value % len(seq)]



random_module: RandomSource = RandomModuleSource()


# --- Game rules (pure) ----------------------------------------------------------


def roll_percent(rng: RandomSource, chance_percent: int) -> tuple[bool, int]:
    """Roll d100 against a percent chance → ``(event_happened, rolled)``.

    The roll itself goes through ``rng.randint`` so both the scripted
    (test) source and the production module behave identically, and the
    exact dice value can be persisted with the outcome.
    """
    roll = int(rng.randint(1, 100))
    return roll <= chance_percent, roll


def roll_cheat_attempt(
    rng: RandomSource,
) -> tuple[bool, bool, int, int]:
    """Roll a secret cheating attempt.

    Returns ``(succeeded, discovered, success_roll, discovery_roll)``.
    ``succeeded`` is the *success chance* of the affair, ``discovered`` the
    independent *discovery chance*. An affair can succeed and stay secret,
    fail and still be rumoured — every combination is possible by design.
    """
    success_roll = int(rng.randint(1, 100))
    discovery_roll = int(rng.randint(1, 100))
    succeeded = success_roll <= constants.FAMILY_CHEAT_SUCCESS_CHANCE
    discovered = discovery_roll <= constants.FAMILY_CHEAT_DISCOVER_CHANCE
    return succeeded, discovered, success_roll, discovery_roll


def roll_pregnancy(rng: RandomSource) -> tuple[bool, int]:
    """Pregnancy chance of one relationship event → ``(pregnant, roll)``."""
    return roll_percent(rng, constants.FAMILY_PREGNANCY_CHANCE)


def after_cheat_discovered(points: int) -> int:
    """Relationship points left after one discovered betrayal (clamped)."""
    return max(
        constants.FAMILY_RELATIONSHIP_MIN_POINTS,
        points - constants.FAMILY_CHEAT_RELATIONSHIP_DAMAGE,
    )


def after_forgiveness(points: int) -> int:
    """Relationship points after the spouse forgives (clamped).

    A relationship already at the floor only recovers half of the heal, so
    rebuilding trust after a collapse stays meaningful.
    """
    heal = constants.FAMILY_FORGIVENESS_HEAL
    if points <= constants.FAMILY_RELATIONSHIP_MIN_POINTS:
        heal = heal // 2
    return min(constants.FAMILY_RELATIONSHIP_MAX_POINTS, points + heal)


def after_relationship_event(points: int) -> int:
    """Relationship points after a shared «رابطه» (heals + small bonus)."""
    heal = constants.FAMILY_RELATIONSHIP_EVENT_HEAL
    if points <= constants.FAMILY_RELATIONSHIP_MIN_POINTS:
        heal = max(1, heal // 2)
    return min(constants.FAMILY_RELATIONSHIP_MAX_POINTS, points + heal)


def divorce_payer_is_cheater(
    *,
    initiator_player_id: int,
    other_player_id: int,
    initiator_caught_count: int,
    other_caught_count: int,
    relationship_points: int,
    mahr: int,
) -> bool:
    """True when the *other* spouse must pay the Mahriyeh on divorce.

    Rule: a betrayed spouse who files while the relationship is beyond
    repair (points at the floor) and has never been caught themselves
    shifts the Mahriyeh onto the proven cheater.
    """
    return (
        mahr > 0
        and other_caught_count >= constants.FAMILY_CHEAT_MIN_FOR_MAHR_LIABILITY
        and initiator_caught_count == 0
        and relationship_points <= constants.FAMILY_RELATIONSHIP_MIN_POINTS
        and initiator_player_id != other_player_id
    )


def sanity_check_mahr(amount: int) -> int:
    """Clamp a typed Mahriyeh into the legal game range (never negative)."""
    return max(constants.FAMILY_MAHR_MIN, min(int(amount), constants.FAMILY_MAHR_MAX))
