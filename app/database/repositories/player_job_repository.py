"""Repository for PlayerJob model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.player_job import PlayerJob


class PlayerJobRepository:
    """Database access for ``player_jobs`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Reads -----------------------------------------------------------

    async def get_by_player_id(self, player_id: int) -> PlayerJob | None:
        stmt = select(PlayerJob).where(PlayerJob.player_id == player_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, record_id: int) -> PlayerJob | None:
        return await self._session.get(PlayerJob, record_id)

    async def has_job(self, player_id: int) -> bool:
        stmt = select(PlayerJob.id).where(PlayerJob.player_id == player_id).limit(1)
        return (await self._session.execute(stmt)).scalar() is not None

    # --- Writes ----------------------------------------------------------

    def add(self, player_job: PlayerJob) -> None:
        self._session.add(player_job)

    async def create(
        self,
        player_id: int,
        job_id: int,
        total_earnings: int = 0,
    ) -> PlayerJob:
        record = PlayerJob(
            player_id=player_id,
            job_id=job_id,
            total_earnings=total_earnings,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def update_last_work_time(
        self, player_id: int, timestamp: datetime, earnings_to_add: int = 0
    ) -> bool:
        """Update last work time and total earnings."""
        if earnings_to_add:
            stmt = (
                update(PlayerJob)
                .where(PlayerJob.player_id == player_id)
                .values(
                    last_work_time=timestamp,
                    total_earnings=PlayerJob.total_earnings + earnings_to_add,
                )
            )
        else:
            stmt = (
                update(PlayerJob)
                .where(PlayerJob.player_id == player_id)
                .values(last_work_time=timestamp)
            )
        result = await self._session.execute(
            stmt, execution_options={"synchronize_session": False}
        )
        return bool(result.rowcount)

    async def delete_by_player_id(self, player_id: int) -> bool:
        stmt = delete(PlayerJob).where(PlayerJob.player_id == player_id)
        result = await self._session.execute(
            stmt, execution_options={"synchronize_session": False}
        )
        return bool(result.rowcount)
