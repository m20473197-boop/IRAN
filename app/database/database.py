"""Async database engine and session management.

The connection URL drives everything: the default is SQLite (via
``aiosqlite``), and moving to PostgreSQL later only requires changing
``DATABASE_URL`` in the environment — no game code changes needed.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.database import models as _models  # noqa: F401  (registers all ORM models)
from app.database.models.base import Base

_SQLITE_PREFIX = "sqlite"
_MEMORY_MARKER = ":memory:"


class Database:
    """Owns the async engine and the session factory for the whole app."""

    def __init__(self, database_url: str, *, echo: bool = False) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_dir(database_url)

        engine_kwargs: dict = {"echo": echo}
        if database_url.startswith(_SQLITE_PREFIX) and _MEMORY_MARKER in database_url:
            # Share a single in-memory database across connections (tests).
            engine_kwargs["poolclass"] = StaticPool

        self._engine: AsyncEngine = create_async_engine(database_url, **engine_kwargs)
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
            autoflush=False,
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    async def create_all(self) -> None:
        """Create any missing tables.

        Existing tables and rows are never dropped or recreated, so player
        data safely survives bot restarts.
        """
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        """Close all connections (called on shutdown)."""
        await self._engine.dispose()

    @staticmethod
    def _ensure_sqlite_parent_dir(url: str) -> None:
        if not url.startswith(_SQLITE_PREFIX):
            return
        path_part = url.split("///", 1)[-1]
        if not path_part or _MEMORY_MARKER in path_part:
            return
        Path(path_part).parent.mkdir(parents=True, exist_ok=True)
