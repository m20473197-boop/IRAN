"""Repository for ``divorce_records`` (permanent history of divorces)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.divorce_record import DivorceRecord


class DivorceRecordRepository:
    """Database access for finalized divorces."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        marriage_id: int | None,
        initiator_player_id: int,
        partner_a_id: int,
        partner_b_id: int,
        mahr: int,
        mahr_payer_player_id: int | None,
        mahr_payee_player_id: int | None,
        paid_amount: int,
        unpaid_debt: int,
        reason: str,
    ) -> DivorceRecord:
        record = DivorceRecord(
            marriage_id=marriage_id,
            initiator_player_id=initiator_player_id,
            partner_a_id=partner_a_id,
            partner_b_id=partner_b_id,
            mahr=mahr,
            mahr_payer_player_id=mahr_payer_player_id,
            mahr_payee_player_id=mahr_payee_player_id,
            paid_amount=paid_amount,
            unpaid_debt=unpaid_debt,
            reason=reason,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def list_by_player(self, player_id: int, limit: int = 20) -> list[DivorceRecord]:
        statement = (
            select(DivorceRecord)
            .where(
                (DivorceRecord.partner_a_id == player_id)
                | (DivorceRecord.partner_b_id == player_id)
            )
            .order_by(DivorceRecord.id.desc())
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())
