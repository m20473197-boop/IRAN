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

# --- Job system («خر حمالی») --------------------------------------------------
# Initial jobs — stored in DB, values here are used for seeding.
# The player-facing name of the system: the old label «شغل» was renamed to
# «خر حمالی» (internal ids/callbacks stay stable; only player-facing texts,
# buttons and menus use this title).
JOB_SYSTEM_TITLE: str = "خر حمالی"

# The canonical job catalog. Salary values are exact Toman per hour; the
# time-based settlement only uses ``hourly_salary`` — ``salary`` and
# ``cooldown`` are the legacy schema fields (mirrored for completeness).
JOB_CATALOG: tuple[dict, ...] = (
    {
        "name": "بنایی",
        "description": "کار ساختمانی؛ ملات‌کاری و باربری در کارگاه",
        "salary": 80_000,
        "hourly_salary": 80_000,  # Toman per hour
        "employer": "شرکت ساختمانی آجر",
        "cooldown": 5 * 60,  # 5 minutes
        "required_level": 1,
    },
    {
        "name": "رستوران",
        "description": "کار در آشپزخانه و سالن پذیرایی رستوران",
        "salary": 70_000,
        "hourly_salary": 70_000,  # Toman per hour
        "employer": "رستوران سنتی شاندیز",
        "cooldown": 5 * 60,  # 5 minutes
        "required_level": 1,
    },
    {
        "name": "فروشندگی",
        "description": "فروش در مغازه و ارتباط با مشتری",
        "salary": 90_000,
        "hourly_salary": 90_000,  # Toman per hour
        "employer": "پاساژ آرمان",
        "cooldown": 10 * 60,  # 10 minutes
        "required_level": 2,
    },
    {
        "name": "پیک موتوری",
        "description": "رساندن بسته‌ها با موتور در سراسر شهر",
        "salary": 120_000,
        "hourly_salary": 120_000,  # Toman per hour
        "employer": "شبکه پیک شهر",
        "cooldown": 10 * 60,  # 10 minutes
        "required_level": 3,
    },
    {
        "name": "اسنپ",
        "description": "مسافرکشی با خودروی شخصی",
        "salary": 160_000,
        "hourly_salary": 160_000,  # Toman per hour
        "employer": "اسنپ",
        "cooldown": 15 * 60,  # 15 minutes
        "required_level": 5,
    },
    {
        "name": "کارمند بانک",
        "description": "کار پشت باجه و امور مشتریان بانک",
        "salary": 220_000,
        "hourly_salary": 220_000,  # Toman per hour
        "employer": "بانک شهر — شعبه مرکزی",
        "cooldown": 15 * 60,  # 15 minutes
        "required_level": 8,
    },
)

# Legacy selectable jobs retired by the catalog update. They are disabled on
# existing databases (never deleted — old job history keeps pointing at them).
JOB_RETIRED_NAMES: tuple[str, ...] = ("کارگر", "کارمند", "متخصص")

# Catalog version marker (stored in ``bot_settings``). Bump it when
# ``JOB_CATALOG`` changes so every database re-syncs once; afterwards admin
# edits of jobs survive restarts untouched.
JOB_CATALOG_VERSION: str = "v2"
JOBS_CATALOG_SETTING_KEY: str = "jobs_catalog_version"

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

# --- Marriage & Family system --------------------------------------------------
# All amounts are exact integer Toman; all chances are percents rolled with
# ``random.randint(1, 100) <= chance`` (see app/game/family/family.py).

# Minimum level required before a player may propose marriage.
FAMILY_MIN_LEVEL_TO_MARRY: int = 3

# Mahriyeh (مهریه): agreed at the proposal («ازدواج [amount]»), stored on the
# marriage, paid through the wallet system when a divorce is finalized.
FAMILY_DEFAULT_MAHRIYEH: int = 500_000
FAMILY_MAHR_MIN: int = 0
FAMILY_MAHR_MAX: int = 5_000_000_000

# How long a marriage proposal waits for its answer before it lapses.
FAMILY_PROPOSAL_EXPIRY_SECONDS: int = 24 * 60 * 60

# Relationship points of a fresh marriage and its bounds (0 = collapsed).
FAMILY_RELATIONSHIP_START_POINTS: int = 100
FAMILY_RELATIONSHIP_MAX_POINTS: int = 100
FAMILY_RELATIONSHIP_MIN_POINTS: int = 0

# Relationship-point movements (per event, no randomness).
FAMILY_RELATIONSHIP_EVENT_HEAL: int = 5  # a nice «رابطه» day heals +5
FAMILY_CHEAT_RELATIONSHIP_DAMAGE: int = 35  # one discovered betrayal burns −35
FAMILY_FORGIVENESS_HEAL: int = 15  # «بخشش» after a pending divorce

# Cheating («خیانت»): two independent rolls — success of the affair itself
# and the chance that the spouse finds out about it.
FAMILY_CHEAT_SUCCESS_CHANCE: int = 55
FAMILY_CHEAT_DISCOVER_CHANCE: int = 35
# Cooldown between two attempts, so the roll cannot be spammed.
FAMILY_CHEAT_COOLDOWN_SECONDS: int = 60 * 60
# Consequences when discovered: social fine (wallet) + reputation XP loss.
FAMILY_CHEAT_SOCIAL_FINE: int = 300_000
FAMILY_CHEAT_XP_LOSS: int = 80
# Discovered betrayals that make the *cheater* liable for the Mahriyeh when
# the betrayed spouse files for divorce.
FAMILY_CHEAT_MIN_FOR_MAHR_LIABILITY: int = 1

# «رابطه» → pregnancy chance and its cooldown.
FAMILY_PREGNANCY_CHANCE: int = 20
FAMILY_RELATIONSHIP_COOLDOWN_SECONDS: int = 2 * 60 * 60

# A filed divorce request can be forgiven («بخشش») for this long; after that
# a repeated «طلاق» finalizes it.
FAMILY_DIVORCE_COOLDOWN_SECONDS: int = 24 * 60 * 60

# XP rewards (granted explicitly through LevelService — never implicitly).
FAMILY_XP_FOR_MARRIAGE: int = 250
FAMILY_XP_FOR_MARRIAGE_REASON: str = "ازدواج"
FAMILY_XP_FOR_CHILD_BIRTH: int = 200
FAMILY_XP_FOR_CHILD_BIRTH_REASON: str = "تولد فرزند"

# Baby names drawn for a newborn (gender prefix marks the name's gender).
FAMILY_BOY_NAMES: tuple[str, ...] = (
    "آرین", "سورن", "کیان", "بردیا", "سام", "نیما", "آرش", "پویا",
)
FAMILY_GIRL_NAMES: tuple[str, ...] = (
    "آوینا", "نگار", "یاسمن", "هستی", "پریسا", "آبان", "رویا", "مانلی",
)
