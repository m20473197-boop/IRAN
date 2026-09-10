"""Repository for the ``houses`` table — ownership and lookup queries."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.house import House


class HouseRepository:
    """All database operations for houses."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Reads ------------------------------------------------------------

    async def get_by_id(self, house_id: int) -> House | None:
        return await self._session.get(House, house_id)

    async def list_by_owner(self, player_id: int) -> list[House]:
        statement = (
            select(House)
            .where(House.owner_player_id == player_id)
            .order_by(House.id)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def list_unowned(self) -> list[House]:
        """All system-market houses (no owner yet), cheapest city first."""
        statement = (
            select(House)
            .where(House.owner_player_id.is_(None))
            .order_by(House.id)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def list_all(self) -> list[House]:
        result = await self._session.execute(select(House).order_by(House.id))
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self._session.execute(select(func.count(House.id)))
        return int(result.scalar_one())

    async def count_owned_by(self, player_id: int) -> int:
        result = await self._session.execute(
            select(func.count(House.id)).where(House.owner_player_id == player_id)
        )
        return int(result.scalar_one())

    # --- Writes -----------------------------------------------------------

    def add(self, house: House) -> None:
        """Stage a new house; the owning service commits the transaction."""
        self._session.add(house)

    async def create(
        self,
        *,
        city: str,
        neighborhood: str,
        area_sqm: int,
        bedrooms: int,
        living_rooms: int,
        bathrooms: int,
        kitchen_type: str,
        building_age_years: int,
        parking: bool,
        elevator: bool,
        storage: bool,
        quality: str,
        owner_player_id: int | None = None,
    ) -> House:
        house = House(
            city=city,
            neighborhood=neighborhood,
            area_sqm=area_sqm,
            bedrooms=bedrooms,
            living_rooms=living_rooms,
            bathrooms=bathrooms,
            kitchen_type=kitchen_type,
            building_age_years=building_age_years,
            parking=parking,
            elevator=elevator,
            storage=storage,
            quality=quality,
            owner_player_id=owner_player_id,
        )
        self._session.add(house)
        await self._session.flush()
        return house

    async def set_owner(self, house_id: int, owner_player_id: int | None) -> bool:
        """Transfer ownership (``None`` releases the house to nobody)."""
        statement = (
            update(House)
            .where(House.id == house_id)
            .values(owner_player_id=owner_player_id)
        )
        result = await self._session.execute(
            statement, execution_options={"synchronize_session": False}
        )
        return bool(result.rowcount)
