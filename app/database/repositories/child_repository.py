"""Repository for ``children`` (the family tree rows)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.child import Child


def _utc_now() -> datetime:
    """Naive-UTC now — matches how the DB stores ``func.now()``."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ChildRepository:
    """Database access for the ``children`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Reads --------------------------------------------------------------

    async def get_by_id(self, child_id: int) -> Child | None:
        return await self._session.get(Child, child_id)

    async def list_by_parent(self, player_id: int, limit: int = 50) -> list[Child]:
        statement = (
            select(Child)
            .where(
                (Child.father_player_id == player_id)
                | (Child.mother_player_id == player_id)
            )
            .order_by(Child.id)
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def list_by_marriage(self, marriage_id: int) -> list[Child]:
        statement = (
            select(Child).where(Child.marriage_id == marriage_id).order_by(Child.id)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def count_of(self, player_id: int) -> int:
        statement = select(func.count(Child.id)).where(
            (Child.father_player_id == player_id)
            | (Child.mother_player_id == player_id)
        )
        return int((await self._session.execute(statement)).scalar_one())

    # --- Writes -------------------------------------------------------------

    async def create(
        self,
        *,
        marriage_id: int,
        father_player_id: int,
        mother_player_id: int,
        name: str,
        gender: str,
        birth_date: datetime | None = None,
        relationship_event_id: int | None = None,
    ) -> Child:
        child = Child(
            marriage_id=marriage_id,
            relationship_event_id=relationship_event_id,
            father_player_id=father_player_id,
            mother_player_id=mother_player_id,
            name=name,
            gender=gender,
            birth_date=birth_date if birth_date is not None else _utc_now(),
        )
        self._session.add(child)
        await self._session.flush()
        return child
