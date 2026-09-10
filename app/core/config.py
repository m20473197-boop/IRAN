"""Application configuration.

Secrets (the bot token above all) never live in code — they are read from
environment variables, optionally backed by a local ``.env`` file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

_DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///data/iran_life_bot.db"
_SQLITE_URL_PREFIX = "sqlite+aiosqlite:///"


class ConfigError(RuntimeError):
    """Raised when the configuration is invalid or incomplete."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable runtime settings."""

    bot_token: str
    database_url: str
    log_level: str


def load_settings(env_file: Path | None = None) -> Settings:
    """Load settings from the environment (and an optional ``.env`` file).

    Raises:
        ConfigError: If the mandatory bot token is missing.
    """
    load_dotenv(env_file if env_file is not None else PROJECT_ROOT / ".env")

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise ConfigError(
            "BOT_TOKEN is not set. "
            "Copy .env.example to .env and paste the token you got from @BotFather."
        )

    database_url = load_database_url(env_file=env_file)
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"

    return Settings(bot_token=bot_token, database_url=database_url, log_level=log_level)


def load_database_url(env_file: Path | None = None) -> str:
    """Resolve the database URL without requiring a bot token.

    Useful for maintenance scripts (e.g. initializing the database).
    """
    load_dotenv(env_file if env_file is not None else PROJECT_ROOT / ".env")
    raw = os.getenv("DATABASE_URL", "").strip() or _DEFAULT_DATABASE_URL
    return _resolve_sqlite_path(raw)


def _resolve_sqlite_path(url: str) -> str:
    """Anchor relative SQLite paths to the project root (cwd-independent)."""
    if not url.startswith(_SQLITE_URL_PREFIX):
        return url
    path_part = url[len(_SQLITE_URL_PREFIX):]
    if not path_part or path_part.startswith("/"):
        return url
    absolute = (PROJECT_ROOT / path_part).resolve()
    return f"{_SQLITE_URL_PREFIX}{absolute.as_posix()}"
