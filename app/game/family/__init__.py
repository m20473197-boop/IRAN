"""Marriage & Family domain layer (pure rules + random sources, no I/O).

Same convention as the housing / real-estate domains: the *rules* of the
game live here as pure functions, the ORM/repositories persist them and
``FamilyService`` owns the transactions.
"""

from app.game.family.family import (
    FixedRandom,
    RandomModuleSource,
    RandomSource,
    after_cheat_discovered,
    after_forgiveness,
    after_relationship_event,
    divorce_payer_is_cheater,
    roll_cheat_attempt,
    roll_percent,
    roll_pregnancy,
    sanity_check_mahr,
)

__all__ = [
    "FixedRandom",
    "RandomModuleSource",
    "RandomSource",
    "after_cheat_discovered",
    "after_forgiveness",
    "after_relationship_event",
    "divorce_payer_is_cheater",
    "roll_cheat_attempt",
    "roll_percent",
    "roll_pregnancy",
    "sanity_check_mahr",
]
