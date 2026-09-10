"""Global game constants.

Starting values and tunable progression settings live here so the game design
can be adjusted in a single place without touching any logic.
"""

# --- New player starting values --------------------------------------------
STARTING_LEVEL: int = 1
STARTING_XP: int = 0
STARTING_MONEY: int = 0

# --- Money ------------------------------------------------------------------
# Money is stored as an exact integer amount of Toman. Floats are never used.
CURRENCY_NAME: str = "تومان"

# --- XP / Level progression -------------------------------------------------
# XP required to advance from level L to L+1:
#     xp_for_level_up(L) = XP_BASE_PER_LEVEL * XP_GROWTH_PER_LEVEL ** (L - 1)
# Tune these two values to reshape the whole curve — nothing else changes.
XP_BASE_PER_LEVEL: int = 100
XP_GROWTH_PER_LEVEL: float = 1.35

# --- Input limits -------------------------------------------------------------
MAX_DISPLAY_NAME_LENGTH: int = 64
MAX_USERNAME_LENGTH: int = 32
MAX_XP_REASON_LENGTH: int = 128

# --- Labor system -----------------------------------------------------------
LABOR_REWARD: int = 50_000
LABOR_COOLDOWN_SECONDS: int = 5 * 60  # 5 minutes

# --- Admin ------------------------------------------------------------------
# Default admin IDs placeholder — real IDs come from env var ADMIN_IDS
DEFAULT_ADMIN_IDS: list[int] = []
