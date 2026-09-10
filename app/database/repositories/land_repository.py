"""Repository for the ``lands`` table — ownership and lookup queries."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.land import Land


class LandRepository:
    """All database operations for land parcels."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Reads ------------------------------------------------------------

    async def get_by_id(self, land_id: int) -> Land | None:
        return await self._session.get(Land, land_id)

    async def list_by_owner(self, player_id: int) -> list[Land]:
        statement = (
            select(Land).where(Land.owner_player_id == player_id).order_by(Land.id)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def list_unowned(self) -> list[Land]:
        """All system-market parcels (no owner yet)."""
        statement = (
            select(Land).where(Land.owner_player_id.is_(None)).order_by(Land.id)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self._session.execute(select(func.count(Land.id)))
        return int(result.scalar_one())

    # --- Writes -----------------------------------------------------------

    def add(self, land: Land) -> None:
        self._session.add(land)

    async def create(
        self,
        *,
        city: str,
        neighborhood: str,
        area_sqm: int,
        location_quality: str,
        owner_player_id: int | None = None,
    ) -> Land:
        land = Land(
            city=city,
            neighborhood=neighborhood,
            area_sqm=area_sqm,
            location_quality=location_quality,
            owner_player_id=owner_player_id,
        )
        self._session.add(land)
        await self._session.flush()
        return land

    async def set_owner(self, land_id: int, owner_player_id: int | None) -> bool:
        """Transfer ownership (``None`` returns the parcel to the market)."""
        statement = (
            update(Land)
            .where(Land.id == land_id)
            .values(owner_player_id=owner_player_id)
        )
        result = await self._session.execute(
            statement, execution_options={"synchronize_session": False}
        )
        return bool(result.rowcount)

    async def mark_built(self, land_id: int, house_id: int) -> bool:
        """Link the finished house — the parcel can never be built on again."""
        statement = (
            update(Land)
            .where(Land.id == land_id)
            .values(built_house_id=house_id)
        )
        result = await self._session.execute(
            statement, execution_options={"synchronize_session": False}
        )
        return bool(result.rowcount)
