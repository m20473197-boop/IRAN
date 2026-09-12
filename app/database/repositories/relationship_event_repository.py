"""Repository for ``relationship_events`` (the couple's intimacy log)."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.relationship_event import (
    OUTCOME_BIRTH,
    OUTCOME_EVENT,
    OUTCOME_PREGNANCY,
    RelationshipEvent,
)


class RelationshipEventRepository:
    """Database access for relationship events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        marriage_id: int,
        initiator_player_id: int,
        partner_player_id: int,
        satisfaction: int,
        pregnancy_chance_percent: int,
        rolled_percent: int,
        pregnant: bool,
        note: str = "",
    ) -> RelationshipEvent:
        event = RelationshipEvent(
            marriage_id=marriage_id,
            initiator_player_id=initiator_player_id,
            partner_player_id=partner_player_id,
            satisfaction=satisfaction,
            pregnancy_chance_percent=pregnancy_chance_percent,
            rolled_percent=rolled_percent,
            outcome=OUTCOME_PREGNANCY if pregnant else OUTCOME_EVENT,
            note=note,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def mark_birth(self, event_id: int) -> None:
        """Upgrade a pregnancy event to ``birth`` once the child row exists."""
        await self._session.execute(
            update(RelationshipEvent)
            .where(RelationshipEvent.id == event_id)
            .values(outcome=OUTCOME_BIRTH),
            execution_options={"synchronize_session": False},
        )

    async def list_by_marriage(
        self, marriage_id: int, limit: int = 20
    ) -> list[RelationshipEvent]:
        statement = (
            select(RelationshipEvent)
            .where(RelationshipEvent.marriage_id == marriage_id)
            .order_by(RelationshipEvent.id.desc())
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())
