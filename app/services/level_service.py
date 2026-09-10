"""Level/XP service.

Every present and future system (jobs, education, businesses, events, ...)
must grant XP through this service, so progression rules stay isolated in
one place. XP is never granted implicitly and never generated randomly.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.player import Player
from app.database.repositories.player_repository import PlayerRepository
from app.game.player.dto import AddXpResult
from app.game.player.progression import level_from_total_xp
from app.game.shared.errors import InvalidAmountError, PlayerNotFoundError

logger = logging.getLogger(__name__)


class LevelService:
    """Reading XP/level and applying XP changes with level-up detection."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # --- Use cases ---------------------------------------------------------

    async def get_xp(self, player_id: int) -> int:
        player = await self._get_player(player_id)
        return player.xp

    async def get_level(self, player_id: int) -> int:
        player = await self._get_player(player_id)
        return player.level

    async def add_xp(self, player_id: int, amount: int) -> AddXpResult:
        """Add XP, re-resolve the level, and detect level-ups.

        Raises:
            InvalidAmountError: If ``amount`` is not a positive integer.
            PlayerNotFoundError: If the player does not exist.
        """
        if amount <= 0:
            raise InvalidAmountError("XP amount must be a positive integer")

        async with self._session_factory() as session:
            player = await PlayerRepository(session).get_by_id(player_id)
            if player is None:
                raise PlayerNotFoundError(f"player_id={player_id} not found")

            xp_before = player.xp
            old_level = player.level
            player.xp = xp_before + amount
            player.level = level_from_total_xp(player.xp)  # level update is derived
            await session.commit()

            result = AddXpResult(
                player_id=player.id,
                xp_before=xp_before,
                xp_after=player.xp,
                old_level=old_level,
                new_level=player.level,
                leveled_up=player.level > old_level,
            )
        if result.leveled_up:
            logger.info(
                "Player %s leveled up: %s -> %s",
                player_id,
                result.old_level,
                result.new_level,
            )
        return result

    # --- Helpers -----------------------------------------------------------

    async def _get_player(self, player_id: int) -> Player:
        async with self._session_factory() as session:
            player = await PlayerRepository(session).get_by_id(player_id)
            if player is None:
                raise PlayerNotFoundError(f"player_id={player_id} not found")
            return player
