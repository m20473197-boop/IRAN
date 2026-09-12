"""Repository for the ``businesses`` table — the only layer touching the DB."""

from __future__ import annotations

from datetime import date

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.business import STATUS_ACTIVE, Business


class BusinessRepository:
    """Database access for business rows. No business rules live here."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Reads -------------------------------------------------------------

    async def get_by_id(self, business_id: int) -> Business | None:
        return await self._session.get(Business, business_id)

    async def list_for_owner(self, owner_player_id: int) -> list[Business]:
        """Every business of the player (active and closed), oldest first."""
        statement = (
            select(Business)
            .where(Business.owner_player_id == owner_player_id)
            .order_by(Business.id)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def count_active_for_owner(self, owner_player_id: int) -> int:
        statement = select(Business.id).where(
            Business.owner_player_id == owner_player_id,
            Business.status == STATUS_ACTIVE,
        )
        result = await self._session.execute(statement)
        return len(result.scalars().all())

    # --- Writes ------------------------------------------------------------

    async def create(
        self,
        owner_player_id: int,
        business_key: str,
        type_name: str,
        startup_cost: int,
    ) -> Business:
        business = Business(
            owner_player_id=owner_player_id,
            business_key=business_key,
            type_name=type_name,
            startup_cost=startup_cost,
            balance=0,
            status=STATUS_ACTIVE,
        )
        self._session.add(business)
        await self._session.flush()
        return business

    async def credit_daily_income(
        self, business_id: int, day: date, amount: int
    ) -> bool:
        """Grant ``amount`` of daily income to one business — once per day.

        The guard is part of the UPDATE itself: the row is only touched while
        ``last_income_date`` still differs from ``day`` and the business is
        ``active``. Two concurrent collections can therefore never pay the
        same day twice — whichever UPDATE runs first flips the date and the
        other one matches zero rows.

        Returns whether the credit was applied (False = already paid today
        or the business cannot earn).
        """
        if amount <= 0:
            raise ValueError(f"daily income must be positive, got {amount}")
        statement = (
            update(Business)
            .where(
                Business.id == business_id,
                Business.status == STATUS_ACTIVE,
                or_(
                    Business.last_income_date.is_(None),
                    Business.last_income_date != day,
                ),
            )
            .values(
                balance=Business.balance + amount,
                last_income_date=day,
                last_income_amount=amount,
                total_income=Business.total_income + amount,
                income_days=Business.income_days + 1,
            )
        )
        result = await self._session.execute(
            statement, execution_options={"synchronize_session": False}
        )
        if result.rowcount:
            cached = await self._session.get(Business, business_id)
            if cached is not None:
                self._session.expire(cached)
        return bool(result.rowcount)

    async def set_status(self, business_id: int, status: str) -> bool:
        """Lifecycle switch (admin/future use — players never call this)."""
        statement = (
            update(Business)
            .where(Business.id == business_id)
            .values(status=status)
        )
        result = await self._session.execute(
            statement, execution_options={"synchronize_session": False}
        )
        return bool(result.rowcount)
