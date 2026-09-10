"""Pure level/XP progression math.

Kept free of any I/O so it can be unit-tested in isolation and safely reused
by future systems (jobs, education, businesses, ...) without touching the
database or Telegram layers. The curve is driven by the tunable constants in
``app.core.constants`` — changing those reshapes the whole progression.
"""

from __future__ import annotations

from app.core import constants


def xp_for_level_up(level: int) -> int:
    """XP required to advance *from* ``level`` to ``level + 1``."""
    if level < 1:
        raise ValueError("level must be >= 1")
    return int(round(constants.XP_BASE_PER_LEVEL * constants.XP_GROWTH_PER_LEVEL ** (level - 1)))


def total_xp_for_level(level: int) -> int:
    """Total XP a player must have collected to *reach* ``level``."""
    if level < 1:
        raise ValueError("level must be >= 1")
    return sum(xp_for_level_up(lvl) for lvl in range(1, level))


def level_from_total_xp(total_xp: int) -> int:
    """Resolve the level a player is on, given their total collected XP."""
    if total_xp < 0:
        raise ValueError("total_xp must be >= 0")
    level = 1
    remaining = total_xp
    while remaining >= xp_for_level_up(level):
        remaining -= xp_for_level_up(level)
        level += 1
    return level
