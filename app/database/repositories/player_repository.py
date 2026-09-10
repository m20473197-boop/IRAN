"""Database access for players.

Repositories are the only place where queries live. Services call them and
own the transaction; Telegram handlers never touch this layer directly.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.player import Player


class PlayerRepository:
    """All database operations for the ``players`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Reads -----------------------------------------------------------

    async def get_by_id(self, player_id: int) -> Player | None:
        return await self._session.get(Player, player_id)

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> Player | None:
        statement = select(Player).where(Player.telegram_user_id == telegram_user_id)
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def exists(self, player_id: int) -> bool:
        statement = select(Player.id).where(Player.id == player_id).limit(1)
        return (await self._session.execute(statement)).scalar() is not None

    async def get_money(self, player_id: int) -> int | None:
        """Return the balance, or ``None`` when the player does not exist."""
        statement = select(Player.money).where(Player.id == player_id)
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def get_last_labor_at(self, player_id: int) -> datetime | None:
        """Return last labor timestamp, or None if never worked."""
        statement = select(Player.last_labor_at).where(Player.id == player_id)
        return (await self._session.execute(statement)).scalar_one_or_none()

    # --- Writes ------------------------------------------------------------

    def add(self, player: Player) -> None:
        """Stage a new player; the owning service commits the transaction."""
        self._session.add(player)

    async def add_money(self, player_id: int, amount: int) -> bool:
        """Atomically increase the balance.

        Returns:
            ``False`` when the player does not exist.
        """
        statement = (
            update(Player)
            .where(Player.id == player_id)
            .values(money=Player.money + amount)
        )
        result = await self._session.execute(
            statement, execution_options={"synchronize_session": False}
        )
        return bool(result.rowcount)

    async def remove_money_if_enough(self, player_id: int, amount: int) -> bool:
        """Atomically remove money, but only if the balance covers it.

        The check and the subtraction happen in a single SQL statement, so a
        concurrent operation can never drive the balance below zero.

        Returns:
            ``False`` when the player is missing or the balance is too low.
        """
        statement = (
            update(Player)
            .where(Player.id == player_id, Player.money >= amount)
            .values(money=Player.money - amount)
        )
        result = await self._session.execute(
            statement, execution_options={"synchronize_session": False}
        )
        return bool(result.rowcount)

    async def update_last_labor_at(
        self, player_id: int, timestamp: datetime | None
    ) -> bool:
        """Update last labor timestamp (None allowed to reset)."""
        statement = (
            update(Player)
            .where(Player.id == player_id)
            .values(last_labor_at=timestamp)
        )
        result = await self._session.execute(
            statement, execution_options={"synchronize_session": False}
        )
        return bool(result.rowcount)

    async def try_claim_labor(
        self, player_id: int, now: datetime, cooldown_seconds: int
    ) -> bool:
        """Atomically claim labor if cooldown passed.

        This prevents race conditions: only one concurrent request can claim.

        Returns:
            True if claim succeeded (cooldown passed and timestamp updated),
            False if cooldown still active or player missing.
        """
        threshold = now - timedelta(seconds=cooldown_seconds)
        # Claim if last_labor_at is NULL or <= threshold
        # Use synchronize_session=False to avoid Python-side evaluation of
        # timezone-aware vs naive datetimes (SQLite returns naive).
        statement = (
            update(Player)
            .where(
                Player.id == player_id,
                (Player.last_labor_at.is_(None)) | (Player.last_labor_at <= threshold),
            )
            .values(last_labor_at=now)
        )
        result = await self._session.execute(
            statement, execution_options={"synchronize_session": False}
        )
        return bool(result.rowcount)

    async def add_money_and_update_labor(
        self, player_id: int, amount: int, now: datetime, cooldown_seconds: int
    ) -> bool:
        """Atomically add money and update labor timestamp if cooldown passed.

        Combines both operations in a single UPDATE to guarantee no bypass.

        Returns:
            True if both operations succeeded (cooldown passed),
            False if cooldown still active.
        """
        threshold = now - timedelta(seconds=cooldown_seconds)
        statement = (
            update(Player)
            .where(
                Player.id == player_id,
                (Player.last_labor_at.is_(None)) | (Player.last_labor_at <= threshold),
            )
            .values(money=Player.money + amount, last_labor_at=now)
        )
        result = await self._session.execute(
            statement, execution_options={"synchronize_session": False}
        )
        return bool(result.rowcount)
