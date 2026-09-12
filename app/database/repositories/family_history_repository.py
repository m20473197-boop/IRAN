"""Repository for ``family_histories`` (the append-only family log)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.family_history import FamilyHistory


class FamilyHistoryRepository:
    """Database access for family history entries.

    Rows are only ever added — history is immutable by design.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(
        self,
        *,
        player_id: int,
        event_type: str,
        marriage_id: int | None = None,
        details: str = "",
    ) -> FamilyHistory:
        entry = FamilyHistory(
            player_id=player_id,
            marriage_id=marriage_id,
            event_type=event_type,
            details=details[:256],
        )
        self._session.add(entry)
        return entry

    async def list_by_player(
        self, player_id: int, limit: int = 20, offset: int = 0
    ) -> list[FamilyHistory]:
        statement = (
            select(FamilyHistory)
            .where(FamilyHistory.player_id == player_id)
            .order_by(FamilyHistory.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())
