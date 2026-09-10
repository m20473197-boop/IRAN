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

# --- Job system -------------------------------------------------------------
# Initial jobs — stored in DB, values here are used for seeding
JOB_WORKER_NAME: str = "کارگر"
JOB_WORKER_DESCRIPTION: str = "کار ساده با درآمد کم"
JOB_WORKER_SALARY: int = 50_000
JOB_WORKER_COOLDOWN: int = 5 * 60  # 5 minutes
JOB_WORKER_REQUIRED_LEVEL: int = 1
JOB_WORKER_HOURLY_SALARY: int = 60_000  # Toman per hour
JOB_WORKER_EMPLOYER: str = "کارگاه حاج رضا"

JOB_EMPLOYEE_NAME: str = "کارمند"
JOB_EMPLOYEE_DESCRIPTION: str = "کار اداری با درآمد متوسط"
JOB_EMPLOYEE_SALARY: int = 100_000
JOB_EMPLOYEE_COOLDOWN: int = 10 * 60  # 10 minutes
JOB_EMPLOYEE_REQUIRED_LEVEL: int = 2
JOB_EMPLOYEE_HOURLY_SALARY: int = 120_000  # Toman per hour
JOB_EMPLOYEE_EMPLOYER: str = "شرکت بازرگانی آریا"

JOB_SPECIALIST_NAME: str = "متخصص"
JOB_SPECIALIST_DESCRIPTION: str = "کار تخصصی با درآمد بالا"
JOB_SPECIALIST_SALARY: int = 200_000
JOB_SPECIALIST_COOLDOWN: int = 15 * 60  # 15 minutes
JOB_SPECIALIST_REQUIRED_LEVEL: int = 3
JOB_SPECIALIST_HOURLY_SALARY: int = 240_000  # Toman per hour
JOB_SPECIALIST_EMPLOYER: str = "هلدینگ فناوری پارس"

# --- Time-based salary settlement -------------------------------------------
# A settlement is only possible after at least this many whole minutes of work.
MIN_WORK_MINUTES_FOR_SETTLEMENT: int = 1

# Employer behaviour: probability of each random event during settlement.
EMPLOYER_EVENT_DELAY_PROBABILITY: float = 0.20
EMPLOYER_EVENT_MISTAKE_PROBABILITY: float = 0.20
EMPLOYER_EVENT_BONUS_PROBABILITY: float = 0.20
# (The remaining probability — 0.40 — is a normal payment.)

# Mistake penalty: random percentage of the earned salary (inclusive range).
MISTAKE_PENALTY_MIN_PERCENT: int = 10
MISTAKE_PENALTY_MAX_PERCENT: int = 50

# Bonus payment: random percentage added on top of the earned salary.
BONUS_MIN_PERCENT: int = 10
BONUS_MAX_PERCENT: int = 30

# --- Admin ------------------------------------------------------------------
# Canonical admin Telegram user IDs. These are the fallback when the ADMIN_IDS
# environment variable is empty, so the panel owner never gets locked out.
# Real IDs can be extended via the ADMIN_IDS env var (comma-separated).
ADMIN_TELEGRAM_IDS: tuple[int, ...] = (8154313073,)

# Default admin IDs placeholder — real IDs come from env var ADMIN_IDS
DEFAULT_ADMIN_IDS: list[int] = []

# --- Housing / Real-estate system -------------------------------------------
# Rental period: one "month" of a contract, in days.
HOUSING_RENT_PERIOD_DAYS: int = 30

# Sale-listing bounds: a player's asking price must stay within these
# multiples of the dynamic market value (prevents absurd markets).
HOUSING_SALE_MIN_PER_MILLE: int = 300     # 30% of market value
HOUSING_SALE_MAX_PER_MILLE: int = 3000    # 300% of market value

# Button presets for sale prices (per-mille of the dynamic market value).
HOUSING_SALE_PRICE_PRESETS_PER_MILLE: tuple[int, ...] = (850, 1000, 1150, 1300)

# Rent-listing bounds (relative to the dynamic market value).
HOUSING_RENT_MIN_PER_MILLE: int = 1       # >= 0.1% of value per month
HOUSING_RENT_MAX_PER_MILLE: int = 20      # <= 2% of value per month
HOUSING_DEPOSIT_MAX_PER_MILLE: int = 500  # deposit <= 50% of value

# Deposit presets when renting a house out: (deposit_percent of value,).
HOUSING_DEPOSIT_PRESET_PERCENTS: tuple[int, ...] = (0, 10, 20)

# XP reward for buying a house: xp = price / divisor, clamped to [min, max].
HOUSING_PURCHASE_XP_DIVISOR: int = 20_000_000
HOUSING_PURCHASE_XP_MIN: int = 5
HOUSING_PURCHASE_XP_MAX: int = 300
HOUSING_PURCHASE_XP_REASON: str = "خرید خانه"

# Number of system-market houses seeded on first boot (spread over the
# catalog cities with varied specs).
HOUSING_SEED_COUNT: int = 30

# --- Land / Construction / Renovation ----------------------------------------
# The single economy knob for the whole real-estate market: land prices,
# construction costs and renovation costs are all multiplied by it. The future
# Economy/Inflation system just moves this value (or passes an explicit
# ``market_factor``) and every price in the game reacts — nothing is fixed.
ECONOMY_MARKET_CONDITIONS: float = 1.0

# Ownerless lands seeded on first boot (system land market).
REALESTATE_SEED_LAND_COUNT: int = 24

# XP reward for completing a construction: xp = cost / divisor, clamped to
# the same [min, max] band as house purchases.
CONSTRUCTION_XP_DIVISOR: int = 30_000_000
CONSTRUCTION_XP_REASON: str = "تکمیل ساخت ملک"

# Cancelling an in-progress construction refunds this share of the paid cost
# (the rest is wasted materials/permits).
CONSTRUCTION_CANCEL_REFUND_PERCENT: int = 70
