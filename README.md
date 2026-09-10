# Iran Life Bot 🇮🇷

A multiplayer **life-simulation game** running as a **Telegram Bot**, inspired
by real life in Iran — casual, humorous and friendly. This repository contains
the clean, scalable foundation plus the **Job and Income System**: the player
system, main menu, profile, status, level/XP service, money service and a
time-based salary job system. Future systems (economy, housing, crime, markets,
...) will be built on top of this base step by step.

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
payments) and the additive column migration — **98 tests**.

## Basic Project Structure

```
iran_life_bot/
├── app/
│   ├── bot/                     # Telegram layer (and nothing else)
│   │   ├── handlers/            #   start, main-menu callbacks, jobs, error handler
│   │   ├── keyboards/           #   inline keyboard builders + callback ids
│   │   ├── messages/            #   ALL player-facing Persian texts
│   │   ├── middleware/          #   cross-cutting update processing
│   │   └── context.py           #   dependency access inside handlers
│   ├── core/
│   │   ├── config.py            # env-based settings (fails fast, no secrets)
│   │   ├── logging.py           # structured logging + secret redaction
│   │   └── constants.py         # starting values, tunable XP curve, limits
│   ├── database/
│   │   ├── models/              # SQLAlchemy ORM models (Player, Job, JobEvent, ...)
│   │   ├── repositories/        # the only layer that queries the DB
│   │   ├── database.py          # async engine + session factory
│   │   └── migrations/          # migration strategy notes (Alembic later)
│   ├── game/
│   │   ├── player/              # pure domain: progression math, DTOs
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

## Job and Income System — time-based salary

Jobs are no longer a "type `کار` to earn per click" mechanic. Instead, each job
pays a **hourly salary** from a named **employer** (صاحبکار):

1. Pick a job from 💼 شغل‌ها — the work start time is saved immediately.
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

## What is intentionally NOT in this stage

Education, skills, housing, vehicles, marriage, businesses, loans,
investments, markets, inflation, trading, crime, police, prisons,
bankruptcy, crises and similar systems are **not implemented** — the
architecture is simply prepared for them.

## Useful Commands

| Command                     | Purpose                        |
|-----------------------------|--------------------------------|
| `python main.py`            | Run the bot                    |
| `python scripts/init_db.py` | Initialize the database        |
| `pytest`                    | Run the test suite             |
| `cp .env.example .env`      | Create your local config       |
