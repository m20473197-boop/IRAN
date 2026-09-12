# Iran Life Bot 🇮🇷

A multiplayer **life-simulation game** running as a **Telegram Bot**, inspired
by real life in Iran — casual, humorous and friendly. This repository contains
the clean, scalable foundation plus the **Job and Income System**, the
**Housing and Real-Estate System**, the **Land, Construction and Renovation
System** and the **Admin Panel**: players, main menu, profile, status,
level/XP, wallet, a time-based salary job system, a full housing market with
dynamic prices, land trading, time-based construction and renovations that
raise property value, and a button-driven admin console to run the game. Future
systems (education, vehicles, markets, ...) will be built on top of this base
step by step.

## Tech Stack

| Component   | Choice                                        |
|-------------|-----------------------------------------------|
| Language    | Python 3.10+ (developed and tested on 3.13)   |
| Bot framework | [python-telegram-bot](https://docs.python-telegram-bot.org) v22 (fully async) |
| Database    | SQLite via `aiosqlite` (async)                |
| ORM         | SQLAlchemy 2.0 (async, ORM-enabled updates)   |
| Config      | `python-dotenv` + environment variables       |
| Tests       | `pytest` + `pytest-asyncio`                   |

> **PostgreSQL-ready:** the database layer is URL-driven. Switching to
> PostgreSQL later only means changing `DATABASE_URL`
> (e.g. `postgresql+asyncpg://user:pass@host/db`) — no game code changes.

## Requirements

- Python **3.10 or newer**
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Installation

### 1. Clone and enter the project

```bash
cd iran_life_bot
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows (PowerShell: .venv\Scripts\Activate.ps1)
```

### 3. Install dependencies

```bash
pip install -r requirements-dev.txt   # runtime + test dependencies
# or: pip install -r requirements.txt  (runtime only)
```

### 4. Configure `.env`

```bash
cp .env.example .env
```

Then edit `.env` and set your real token:

```env
BOT_TOKEN=123456789:AA...your_real_token...
```

Never commit `.env` (it is already git-ignored). The bot **fails fast with a
clear message** if `BOT_TOKEN` is missing.

## Database

- **Automatic:** the bot creates any missing tables on every startup
  (`post_init` hook). Existing tables and rows are never dropped or altered,
  so player data survives restarts.
- **Manual:** you can also initialize it yourself:

```bash
python scripts/init_db.py
```

The SQLite file lives at `data/iran_life_bot.db` by default (configurable via
`DATABASE_URL`).

## Running the Bot

```bash
python main.py
```

Stop it with `Ctrl+C` (a graceful shutdown log line is printed).

## Running the Tests

```bash
pytest
```

The suite covers registration, duplicate prevention (including concurrent
`/start`), starting values, level/XP progression, the money service, profile
and status retrieval, DB persistence across restarts, keyboard/menu shape,
handler flows, config guards, log-secret redaction, the time-based salary
job system (settlement, employer behaviour, penalties, bonuses and delayed
payments), the additive column migration, the **complete Housing system**
(dynamic pricing, market buying, player-to-player selling and renting,
rental contracts, rent payments, money-transfer atomicity, assets, schema
upgrade of old databases) and the **complete Land, Construction and
Renovation system** (dynamic land pricing, buying land, the full
button-driven construction wizard, progress and completion, house creation,
renovation options and value increases, cancellations with refunds, the
economy knob and schema upgrades), the **complete Admin Panel** (auth guard,
ban enforcement, Persian-number parsing, dashboard, users, economy, real
estate, jobs, trading, settings, database tools and logs — **113 tests**) —
**365 tests**.

## Basic Project Structure

```
iran_life_bot/
├── app/
│   ├── bot/                     # Telegram layer (and nothing else)
│   │   ├── handlers/            #   start, jobs, housing, land/construction, family, admin panel, error handler
│   │   ├── keyboards/           #   inline keyboard builders + callback ids
│   │   ├── messages/            #   ALL player-facing Persian texts
│   │   ├── middleware/          #   cross-cutting update processing
│   │   └── context.py           #   dependency access inside handlers
│   ├── core/
│   │   ├── config.py            # env-based settings (fails fast, no secrets)
│   │   ├── logging.py           # structured logging + secret redaction
│   │   └── constants.py         # starting values, tunable XP curve, limits
│   ├── database/
│   │   ├── models/              # SQLAlchemy ORM models (Player, Job, House, Land, ...)
│   │   ├── repositories/        # the only layer that queries the DB
│   │   ├── database.py          # async engine + session factory
│   │   └── migrations/          # migration strategy notes (Alembic later)
│   ├── game/
│   │   ├── player/              # pure domain: progression math, DTOs
│   │   ├── housing/             # pure domain: city catalog, dynamic pricing, DTOs
│   │   ├── realestate/          # pure domain: land pricing, construction, renovation
│   │   ├── family/              # pure domain: marriage/divorce/cheating rules, DTOs
│   │   ├── admin/               # pure domain: runtime knobs, Persian-number parsing, DTOs
│   │   └── shared/              # shared domain errors
│   └── services/                # business logic + transaction boundaries
├── tests/                       # pytest suite
├── scripts/
│   └── init_db.py               # standalone DB initializer
├── .env.example
├── .gitignore
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── README.md
└── main.py                      # entry point
```

## Architecture

Strict dependency flow — each layer only talks to the one below it:

```
Telegram Handler   (app/bot/handlers)      → Telegram interaction only
       ↓
Service            (app/services)          → business rules + transactions
       ↓
Repository         (app/database/repositories) → all database access
       ↓
Database           (SQLAlchemy async engine)
```

Design decisions worth knowing:

- **One profile per Telegram user** is enforced by a *unique index* on
  `telegram_user_id` in the database itself, plus an idempotent
  register-or-get flow that also survives concurrent `/start` races.
- **Money is an exact integer** (Toman). Floats are never used. Removals are
  atomic single-statement operations — the balance can never go negative.
- **Level/XP progression** is isolated: pure math in `app/game/player/progression.py`,
  tunable constants in `app/core/constants.py`, mutations only via the
  `LevelService`. No system grants XP implicitly.
- **All Persian texts** live in `app/bot/messages/` — no strings scattered
  through handlers.
- **Secrets** come only from the environment; a log filter redacts the token
  even if it ever appears inside an exception traceback.
- **No age attribute** exists anywhere in the model — progression is Level + XP only.

## Job and Income System — «خر حمالی», time-based salary

The job system is called **خر حمالی** for players (the old label «شغل» was
renamed — internal ids and the existing text triggers «مشاغل» / «شغل من» /
«ترک کار» / «استخدام …» keep working). The selectable catalog is exactly:

| Job | Level | Hourly salary |
|-----|-------|----------------|
| بنایی | 1 | ۸۰٬۰۰۰ تومان |
| رستوران | 1 | ۷۰٬۰۰۰ تومان |
| فروشندگی | 2 | ۹۰٬۰۰۰ تومان |
| پیک موتوری | 3 | ۱۲۰٬۰۰۰ تومان |
| اسنپ | 5 | ۱۶۰٬۰۰۰ تومان |
| کارمند بانک | 8 | ۲۲۰٬۰۰۰ تومان |

The legacy catalog («کارگر»، «کارمند»، «متخصص») is **retired**: existing
databases keep those rows for history but they are disabled (deactivated) —
never deleted. The sync runs once per catalog version (marker in
`bot_settings`), so later admin edits of jobs survive restarts.

Jobs are not a "type `کار` to earn per click" mechanic — the time-based
settlement above is unchanged. Each job pays an **hourly salary** from a named
**employer** (صاحبکار):

1. Pick a job from 💼 خر حمالی — the work start time is saved immediately.
2. Working time accrues automatically from that moment.
3. Press **💰 تسویه با صاحبکار** whenever you want to get paid:
   - the hours worked are calculated,
   - the salary is computed from the hourly rate,
   - the money is paid through the wallet system,
   - the work timer is reset.

Settling with the employer triggers a random **employer-behaviour event**:

| Event | Effect |
|-------|--------|
| ✅ Normal payment | Full earned salary is paid. |
| 🎉 Bonus payment | A random 10–30% bonus is added on top. |
| ⚠️ Mistake | A random 10–50% penalty is deducted from the earned salary. |
| ⏳ Delayed payment | The employer withholds payment — the timer keeps running so you can settle again later. |

Every event (payments, bonuses, penalties and delayed payments) is saved to the
`job_events` table and shown in 📜 تاریخچه تسویه‌ها.

## Business System (کسب و کار) 🏪

Players run businesses from a **predefined, configurable catalog** — arbitrary
custom businesses are not allowed. The whole list lives in
``constants.BUSINESS_CATALOG`` (add an entry, retune a price or an income band
there — the menu, the confirmations and the rolls all follow the data). Each
entry carries: name, Persian description, **startup cost**, **min/max daily
income** and an ``available`` switch.

- **Start:** «کسب و کار» / «بیزینس» (or the inline menu) → pick a business →
  confirmation screen → the startup cost is charged **through the existing
  MoneyService** (atomic, refuses when the wallet can't pay — with the exact
  shortfall shown). A player may own at most ``BUSINESS_MAX_OWNED`` (2 by
  default, configurable).
- **Daily income:** every active business earns once per Iranian calendar day
  (UTC+3:30). The amount is **rolled randomly inside the type's configured
  band** — some days less, some days more, never a fixed number. The income
  is credited to the **business' own balance, never to the player's wallet**;
  the once-per-day rule is enforced by a guarded ``UPDATE`` in the repository
  so the same day can never be paid twice, even under concurrent taps.
- **View:** «کسب‌وکارهای من» shows every owned business with startup cost,
  current balance, start date and today's income state; each business has its
  own detail screen (total income, paid days).

Tables: ``businesses`` (id, owner, catalog key + name snapshot, startup cost,
balance, status ``active|closed``, created date, last income date/amount,
lifetime income). Architecture stays strict: handlers → ``BusinessService`` →
``BusinessRepository`` → DB, and all player money flows through the wallet.

> Employee hiring (استخدام نیرو), salaries, taxes, loans and trading are
> explicitly **not** part of this system yet — the business runs without a
> workforce and the API deliberately has no hiring surface.

## Housing and Real-Estate System 🏠

Players own real houses with realistic properties, prices are **always computed
dynamically** — nothing is ever a fixed number — and the whole market is
**player-to-player** (no NPC buyers, sellers, landlords or tenants).

### Houses

Every house has a unique ID plus a full property list: city, neighborhood,
area (m²), bedrooms, living rooms, bathrooms, kitchen type (مدرن/معمولی/قدیمی),
construction year (سال ساخت, Solar Hijri — e.g. ۱۳۹۵), parking, elevator,
storage and a quality level (عالی/خوب/متوسط/ضعیف). The building's age is
never stored — it is derived internally as
``current_iranian_year() − construction_year`` wherever needed, while the UI
only ever shows the construction year.

### Dynamic pricing

The price of a house is recomputed from its attributes and the market catalog
every time it is shown:

```
price = base_price_per_sqm(city) × neighborhood_multiplier × area
      × size_factor × construction-year depreciation (floor 45%) × facility_bonus
      × kitchen_factor × quality_factor × market_factor × per-house jitter
```

* `app/game/housing/catalog.py` holds the Iranian cities (تهران، مشهد، اصفهان،
  شیراز، تبریز، کرج، قم، اهواز، رشت، یزد) with their neighborhoods and
  multipliers — **this file is the single connection point for a future live
  feed of the real Iranian housing market**: refresh it and every price in the
  game moves automatically.
* Rent follows the Iranian رهن/اجاره model: a bigger refundable deposit (رهن)
  lowers the monthly rent (اجاره).

### Buying, selling and renting

| Flow | How it works |
|------|--------------|
| Buy from the market | Ownerless houses (bank/developer) cost their live dynamic price. |
| Sell to players | Owner picks a price preset (85%–130% of live value) → other players buy it. Money and ownership move in **one atomic transaction**. |
| Rent to players | Owner picks a رهن/اجاره preset → a tenant signs a **rental contract** (stored with both parties), pays the deposit, then pays monthly rent via 💵 پرداخت اجاره. Either side can end the contract. |
| Assets | Owned houses are the player's assets — 🏠 خانه‌های من shows every house plus the total live value. |

Buying a house explicitly grants XP through the LevelService (never implicitly).

### Housing screens (all button-driven)

Send **«خانه»** (or use 🏠 خانه in the main menu):

* 🏠 خانه‌های من — assets + manage (فروش / اجاره‌دادن / لغو آگهی / پایان قرارداد)
* 🏖️ بازار مسکن — every purchasable house with ℹ️ and 🛒 buttons
* 🛏️ خانه‌های اجاره‌ای — rent offers from other players
* 📜 قراردادهای اجاره من — your contracts, rent payments and endings
* ℹ️ اطلاعات خانه — the full property sheet for any house

## Land, Construction and Renovation System 🌍🏗️🛠️

Everything starts with land. Land trades with **fully dynamic prices**, houses
are **built over real time** (never instantly) and renovations **raise
property value** by changing the very attributes the dynamic pricing engine
reads.

### Land

Every parcel has a unique ID, an owner, city, neighborhood, size (m²) and a
location-quality label (لوکس/عالی/خوب/متوسط derived from the neighborhood).
The market value is always recomputed live:

```
price = base_price_per_sqm(city) × LAND_RATIO(0.45) × neighborhood
      × size × wholesale_size_discount × market_factor × per-parcel jitter
```

``market_factor`` is the shared **economy knob**
(``constants.ECONOMY_MARKET_CONDITIONS``) — land prices, construction costs
and renovation costs all move together when the economy moves. This is the
future integration point for the Inflation/Economy system (and for real
Iranian market data, through the same housing catalog).

### Building on your land (🏗️ ساخت خانه)

A fully button-driven wizard picks: building type (آپارتمانی ۲–۴ طبقه /
ویلایی) → floors → total built area (bounded by land × floors) → bedrooms →
material grade (اقتصادی/استاندارد/لوکس) → facilities. Cost depends on size,
materials, floors, facilities and the live market; duration scales with
area/quality/floors (days). Money is paid upfront; progress can be followed:

```
🏗️ Building progress:
▓▓▓░░░░░░░ 40%
Time remaining: 6 days
```

On completion a brand-new House (age 0, chosen quality/kitchen/facilities) is
created on the parcel and plugs straight into the Housing system — it appears
in خانه‌های من, can be sold, rented out, and its value is the standard dynamic
house price. Cancelling an active project refunds 70%. Completion grants XP.

### Renovation (🛠️ بازسازی خانه)

Each owned, tenant-free house offers live-quoted options — raise quality,
renovate the kitchen, add a bathroom, add a room, add parking/elevator/
storage, or modernize an old building (advances the construction year).
Every option costs
money and takes days; on completion the house attributes change and the
dynamic pricing engine immediately values it higher (recorded as
value_before → value_after in the `property_upgrades` audit table).

### Screens

Inside 🏠 خانه: 🌍 زمین‌های من · 🛒 خرید زمین · 🏗️ ساخت خانه · 📈 وضعیت ساخت ·
🛠️ بازسازی خانه · ℹ️ اطلاعات ملک — plus the Persian text commands «زمین‌های من»،
«خرید زمین»، «ساخت خانه»، «وضعیت ساخت»، «بازسازی خانه». Completed
constructions and renovations settle lazily whenever any related screen is
opened (atomic, race-safe) — a future scheduler can also call
``RealEstateService.settle_due()`` periodically.

## Marriage and Family System 💍

A complete life-simulation layer **driven entirely by Persian text commands —
no menus and no buttons are added anywhere**. It integrates with the player,
wallet, level/XP and profile systems.

### Commands (all plain text messages)

| Command | What it does |
|---|---|
| «ازدواج» *(reply to a player)* | Marriage request; optionally with a Mahriyeh: «ازدواج ۵۰۰۰۰۰» |
| «قبول» | The target accepts the request → both become spouses (marriage date saved, profiles updated) |
| «رد» | The target rejects the request |
| «طلاق» | Files a divorce request (a second «طلاق» — by either side — finalizes it) |
| «بخشش» | Forgive a pending divorce → relationship points are restored |
| «خیانت» | A **secret** cheating attempt (success + discovery are independent random rolls) |
| «رابطه» *(reply to your spouse)* | Relationship event with a pregnancy chance → children |
| «خانواده» | Marriage status, spouse, marriage date, Mahriyeh, children |
| «سابقه طلاق» / «تاریخچه خانواده» | Stored divorce records / the append-only family log |

### Rules & integration

* **Monogamy**: a married player can never marry again — and a married target
  is reported as married. A partial unique index enforces one active marriage
  per player at the database level, so even concurrent accepts cannot create
  a double marriage.
* **Mahriyeh (مهریه)** is agreed at the proposal, stored on the marriage, and
  is settled through the existing atomic wallet primitives (`MoneyService` /
  `remove_money_if_enough`) inside the divorce transaction. If the initiator
  cannot pay, the divorce is **refused** with the exact required amount and
  shortfall.
* **Cheating («خیانت»)** is hidden — only the author ever sees the attempt's
  result. When discovered the spouse is notified and consequences follow:
  relationship points burn, a social fine leaves the wallet, reputation XP is
  removed (through `LevelService` with full history), and divorce becomes a
  real possibility — once the relationship is at its floor, the *betrayed*
  spouse's «طلاق» makes the proven cheater pay the Mahriyeh (any shortfall
  is recorded as an unpaid debt in the divorce record).
* **Children**: a pregnancy creates a `children` row (father, mother, birth
  date, child id), updates the family counters (marriage + both profiles) and
  grants XP to both parents. The rows already carry the prepared structure for
  the future child-growth / education / family-expense systems
  (`growth_stage`, `education_level`, `expense_total`).
* **Profile**: the 👤 profile screen shows marriage status, spouse name,
  marriage year (Solar-Hijri) and the children count — read from the mirrored
  `players` columns, kept in sync inside every family transaction.

### Tables

`marriages`, `marriage_proposals`, `divorce_records`, `relationship_events`,
`children`, `family_histories` — created additively on existing databases,
plus four new additive `players` columns (`marriage_status`,
`spouse_player_id`, `married_at`, `children_count`).

## Admin Panel 🛡️

The `/admin` command opens a fully **button-driven control console** for the
game's administrators (default: Telegram ID `8154313073`). Everyone else is
blocked with a polite message, and a middleware layer stops every update from
banned players with a short notice before any handler runs.

* **📊 Dashboard** — live stats: total/active/banned users, money in
  circulation, houses, lands, jobs, active listings/contracts/rentals, the
  live market factor and the server/database health.
* **👥 Users** — paged list, search (by ID / username / name), full profile,
  transactions and properties; add/remove money, add/remove XP, set level,
  ban/unban. Persian digits and suffixes (k/m/B, میلیون/میلیارد) are parsed.
* **💰 Economy** — inflation rate, base market conditions, currency/gold/
  crypto assets with price history, timed economic events and a one-tap
  crisis preset. The **effective market factor** (base × events) drives all
  house, land, construction and renovation prices live.
* **🏠 Real estate** — every house/land with edit screens (area, city,
  construction year, facilities, quality, location, per-property price
  override), active sale listings (close/remove) and rental contracts
  (terminate).
* **💼 Jobs** — create jobs through a guided 6-step flow, edit salary/level/
  employer, enable/disable jobs, watch active workers.
* **📈 Trading** — market activity, sale history and rental volume (a full
  trading exchange stays a future system; the read-side scaffold is ready).
* **⚙️ Settings** — XP reward bounds/divisors, minimum settle minutes and
  **feature flags** that instantly enable/disable the jobs and housing
  systems (menus hide them automatically).
* **🗄️ Database tools** — stats, one-tap backups (also sent as a file),
  restore with a confirm step, and safe cleanup of old listings/audit
  rows/price ticks.
* **📋 Logs** — the immutable admin-audit trail (who did what, when),
  user/economy/land/DB action views and the recent error log.

The admin code follows the same architecture (handlers → `AdminService` →
repositories); every money/XP mutation reuses the existing atomic services,
and old databases are upgraded additively (no rows dropped).

## What is intentionally NOT in this stage

Education, skills, vehicles, businesses, loans, investments, markets, a
trading exchange, crime, police, prisons and bankruptcy are **not
implemented** — the architecture is simply prepared for them. (Marriage and
family life is implemented — see the section above; child growth, education
and family expenses stay prepared for later stages.)

## Useful Commands

| Command                     | Purpose                        |
|-----------------------------|--------------------------------|
| `python main.py`            | Run the bot                    |
| `python scripts/init_db.py` | Initialize the database        |
| `pytest`                    | Run the test suite             |
| `cp .env.example .env`      | Create your local config       |
