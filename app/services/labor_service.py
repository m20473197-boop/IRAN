"""Basic Labor System — dedicated service.

Allows players to earn money by typing "کارگری" once every 5 minutes.
Reward is 50,000 تومان, stored persistently, cooldown survives restarts.

Design goals:
- Keep logic inside service, not handlers
- Use Wallet/Money service for money changes (but also provide atomic DB operation to prevent bypass)
- Cooldown tracked via Player.last_labor_at (DateTime, timezone-aware, nullable)
- Safe against concurrent messages (atomic UPDATE with WHERE condition)
- Expandable for future Job/Income system (service can later support XP, different rewards, etc.)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import constants
from app.database.repositories.player_repository import PlayerRepository
from app.game.player.dto import LaborResult, LaborStatus
from app.game.shared.errors import PlayerNotFoundError

logger = logging.getLogger(__name__)


class LaborService:
    """Handles all labor business logic."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        money_service=None,  # MoneyService, injected optionally to avoid circular import
    ) -> None:
        self._session_factory = session_factory
        self._money_service = money_service

    # --- Public API --------------------------------------------------------

    async def can_work(self, player_id: int) -> LaborStatus:
        """Check if player can work now, without performing labor."""
        async with self._session_factory() as session:
            repo = PlayerRepository(session)
            player = await repo.get_by_id(player_id)
            if player is None:
                raise PlayerNotFoundError(f"player_id={player_id} not found")

            last = player.last_labor_at
            remaining = self._remaining_seconds(last)

            return LaborStatus(
                player_id=player_id,
                can_work=remaining <= 0,
                remaining_seconds=remaining,
                last_labor_at=last,
                reward=constants.LABOR_REWARD,
                cooldown_seconds=constants.LABOR_COOLDOWN_SECONDS,
            )

    async def get_remaining_cooldown(self, player_id: int) -> int:
        """Return remaining cooldown seconds (0 if can work)."""
        status = await self.can_work(player_id)
        return status.remaining_seconds

    async def perform_labor(self, player_id: int) -> LaborResult:
        """Perform labor: check cooldown, give reward, update timestamp.

        Flow:
        1. Atomically try to claim labor slot (UPDATE ... WHERE cooldown passed)
        2. If claim fails -> return cooldown result
        3. If claim succeeds -> add money via MoneyService or direct repo, return success

        This method is safe against concurrent calls: only one can claim.

        Raises:
            PlayerNotFoundError: If player does not exist.
        """
        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            repo = PlayerRepository(session)
            player = await repo.get_by_id(player_id)
            if player is None:
                raise PlayerNotFoundError(f"player_id={player_id} not found")

            # Store values before any potential expiration
            money_before = player.money
            last_before = player.last_labor_at

            # Try atomic claim + money addition in single UPDATE for maximum safety
            # This prevents bypass and ensures money + timestamp update together
            claimed = await repo.add_money_and_update_labor(
                player_id=player_id,
                amount=constants.LABOR_REWARD,
                now=now,
                cooldown_seconds=constants.LABOR_COOLDOWN_SECONDS,
            )

            if claimed:
                # Success — need to get balance_after
                await session.commit()
                # Get updated player to read balance
                async with self._session_factory() as fresh_session:
                    fresh_repo = PlayerRepository(fresh_session)
                    fresh_player = await fresh_repo.get_by_id(player_id)
                    assert fresh_player is not None
                    balance_after = fresh_player.money
                    last_labor_at = fresh_player.last_labor_at

                logger.info(
                    "Labor success: player_id=%s reward=%s balance_after=%s",
                    player_id,
                    constants.LABOR_REWARD,
                    balance_after,
                )

                return LaborResult(
                    player_id=player_id,
                    success=True,
                    reward=constants.LABOR_REWARD,
                    balance_after=balance_after,
                    remaining_seconds=0,
                    last_labor_at=last_labor_at,
                )
            else:
                # Claim failed — check if player missing or cooldown active
                await session.rollback()
                # Need to re-fetch to calculate remaining and balance
                async with self._session_factory() as check_session:
                    check_repo = PlayerRepository(check_session)
                    check_player = await check_repo.get_by_id(player_id)
                    if check_player is None:
                        raise PlayerNotFoundError(f"player_id={player_id} not found")
                    remaining = self._remaining_seconds(check_player.last_labor_at)
                    # If remaining <=0 but claim failed, it means race condition where
                    # another transaction claimed just now — treat as cooldown with small remaining
                    if remaining <= 0:
                        remaining = constants.LABOR_COOLDOWN_SECONDS
                    balance_after = check_player.money
                    last_at = check_player.last_labor_at

                return LaborResult(
                    player_id=player_id,
                    success=False,
                    reward=0,
                    balance_after=balance_after,
                    remaining_seconds=remaining,
                    last_labor_at=last_at,
                )

    async def perform_labor_with_money_service(self, player_id: int) -> LaborResult:
        """Alternative flow that explicitly uses MoneyService for money addition.

        This version first atomically claims the labor slot, then uses MoneyService.
        Kept for reference and to satisfy "use Wallet Service" requirement.
        If MoneyService fails, the claim is reverted.

        Currently, perform_labor() uses direct repo for atomicity, which is safer.
        This method shows how MoneyService could be integrated.
        """
        if self._money_service is None:
            # Fallback to direct method if no money service injected
            return await self.perform_labor(player_id)

        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            repo = PlayerRepository(session)
            player = await repo.get_by_id(player_id)
            if player is None:
                raise PlayerNotFoundError(f"player_id={player_id} not found")

            claimed = await repo.try_claim_labor(
                player_id=player_id,
                now=now,
                cooldown_seconds=constants.LABOR_COOLDOWN_SECONDS,
            )

            if not claimed:
                await session.rollback()
                remaining = self._remaining_seconds(player.last_labor_at)
                if remaining <= 0:
                    remaining = constants.LABOR_COOLDOWN_SECONDS
                return LaborResult(
                    player_id=player_id,
                    success=False,
                    reward=0,
                    balance_after=player.money,
                    remaining_seconds=remaining,
                    last_labor_at=player.last_labor_at,
                )

            await session.commit()

        # Now add money via MoneyService (separate transaction)
        try:
            money_result = await self._money_service.add_money(
                player_id, constants.LABOR_REWARD
            )
            return LaborResult(
                player_id=player_id,
                success=True,
                reward=constants.LABOR_REWARD,
                balance_after=money_result.balance_after,
                remaining_seconds=0,
                last_labor_at=now,
            )
        except Exception as exc:
            # Revert claim if money addition failed
            logger.error("Labor money addition failed, reverting claim: %s", exc)
            async with self._session_factory() as revert_session:
                revert_repo = PlayerRepository(revert_session)
                # Set back to old value
                await revert_repo.update_last_labor_at(player_id, player.last_labor_at) if player.last_labor_at else await revert_session.execute(
                    # If old was None, set to NULL via direct update
                    # Use repository method that sets None? We'll do raw update
                    __import__("sqlalchemy").update(
                        __import__("app.database.models.player", fromlist=["Player"]).Player
                    ).where(
                        __import__("app.database.models.player", fromlist=["Player"]).Player.id == player_id
                    ).values(last_labor_at=None)
                )
                await revert_session.commit()
            raise

    # --- Helpers -----------------------------------------------------------

    @staticmethod
    def _remaining_seconds(last_labor_at: datetime | None) -> int:
        """Calculate remaining cooldown seconds."""
        if last_labor_at is None:
            return 0

        # Ensure timezone-aware comparison
        now = datetime.now(timezone.utc)
        last = last_labor_at
        if last.tzinfo is None:
            # Assume UTC if naive (for legacy data)
            last = last.replace(tzinfo=timezone.utc)

        elapsed = (now - last).total_seconds()
        remaining = constants.LABOR_COOLDOWN_SECONDS - elapsed
        if remaining <= 0:
            return 0
        return int(remaining)

    @staticmethod
    def format_remaining(remaining_seconds: int) -> str:
        """Format remaining seconds as human-readable Persian minutes.

        Example: 125 seconds -> "2 دقیقه و 5 ثانیه" or "2 دقیقه"
        For simplicity, we show minutes and seconds.
        """
        if remaining_seconds <= 0:
            return "0 ثانیه"

        minutes = remaining_seconds // 60
        seconds = remaining_seconds % 60

        if minutes > 0 and seconds > 0:
            return f"{minutes} دقیقه و {seconds} ثانیه"
        elif minutes > 0:
            return f"{minutes} دقیقه"
        else:
            return f"{seconds} ثانیه"
