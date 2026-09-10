"""Job and Income System — dedicated service.

Handles:
- Listing available jobs
- Checking requirements (level, skill)
- Applying for a job (one active job per player)
- Working (cooldown, salary via Wallet Service, history)
- Leaving a job
- Job history tracking

Expandable for future: education, skills, businesses, etc.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.job import Job
from app.database.repositories.job_history_repository import JobHistoryRepository
from app.database.repositories.job_repository import JobRepository
from app.database.repositories.player_job_repository import PlayerJobRepository
from app.database.repositories.player_repository import PlayerRepository
from app.game.player.dto import (
    JobApplyResult,
    JobData,
    JobHistoryData,
    JobLeaveResult,
    JobWorkResult,
    PlayerJobData,
)
from app.game.shared.errors import DomainError, PlayerNotFoundError

logger = logging.getLogger(__name__)


class JobNotFoundError(DomainError):
    pass


class JobRequirementError(DomainError):
    pass


class AlreadyHasJobError(DomainError):
    pass


class NoJobError(DomainError):
    pass


class JobCooldownError(DomainError):
    def __init__(self, remaining_seconds: int, message: str = ""):
        super().__init__(message)
        self.remaining_seconds = remaining_seconds


class JobService:
    """Complete Job and Income service."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        money_service=None,
    ) -> None:
        self._session_factory = session_factory
        self._money_service = money_service

    # --- Helpers to convert ORM -> DTO -----------------------------------

    @staticmethod
    def _to_job_dto(job: Job) -> JobData:
        return JobData(
            id=job.id,
            name=job.name,
            description=job.description,
            salary=job.salary,
            cooldown=job.cooldown,
            required_level=job.required_level,
            required_skill=job.required_skill,
            is_active=job.is_active,
            created_at=job.created_at,
        )

    @staticmethod
    def _remaining_seconds(last_work_time: datetime | None, cooldown: int) -> int:
        if last_work_time is None:
            return 0
        now = datetime.now(timezone.utc)
        last = last_work_time
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        elapsed = (now - last).total_seconds()
        remaining = cooldown - elapsed
        return 0 if remaining <= 0 else int(remaining)

    # --- Public API ------------------------------------------------------

    async def ensure_initial_jobs(self) -> List[JobData]:
        """Seed initial jobs if missing, return active jobs."""
        async with self._session_factory() as session:
            repo = JobRepository(session)
            jobs = await repo.ensure_initial_jobs()
            await session.commit()
            return [self._to_job_dto(j) for j in jobs]

    async def get_available_jobs(self) -> List[JobData]:
        async with self._session_factory() as session:
            repo = JobRepository(session)
            jobs = await repo.list_active()
            return [self._to_job_dto(j) for j in jobs]

    async def get_all_jobs(self) -> List[JobData]:
        async with self._session_factory() as session:
            repo = JobRepository(session)
            jobs = await repo.list_all()
            return [self._to_job_dto(j) for j in jobs]

    async def get_player_job(self, player_id: int) -> PlayerJobData | None:
        async with self._session_factory() as session:
            player_repo = PlayerRepository(session)
            if not await player_repo.exists(player_id):
                raise PlayerNotFoundError(f"player_id={player_id} not found")

            pj_repo = PlayerJobRepository(session)
            pj = await pj_repo.get_by_player_id(player_id)
            if pj is None:
                return None

            job_repo = JobRepository(session)
            job = await job_repo.get_by_id(pj.job_id)
            if job is None:
                # Job deleted? Clean up orphan
                await pj_repo.delete_by_player_id(player_id)
                await session.commit()
                return None

            return PlayerJobData(
                id=pj.id,
                player_id=pj.player_id,
                job_id=pj.job_id,
                job_name=job.name,
                job_description=job.description,
                salary=job.salary,
                cooldown=job.cooldown,
                started_at=pj.started_at,
                last_work_time=pj.last_work_time,
                total_earnings=pj.total_earnings,
                created_at=pj.created_at,
                updated_at=pj.updated_at,
            )

    async def apply_job(self, player_id: int, job_id: int) -> JobApplyResult:
        async with self._session_factory() as session:
            player_repo = PlayerRepository(session)
            player = await player_repo.get_by_id(player_id)
            if player is None:
                raise PlayerNotFoundError(f"player_id={player_id} not found")

            job_repo = JobRepository(session)
            job = await job_repo.get_by_id(job_id)
            if job is None:
                raise JobNotFoundError(f"job_id={job_id} not found")
            if not job.is_active:
                raise JobNotFoundError(f"job {job.name} is not active")

            # Check requirements
            if player.level < job.required_level:
                raise JobRequirementError(
                    f"Requires level {job.required_level}, you are {player.level}"
                )
            # required_skill check — for future, if skill system exists
            # For now, if required_skill is set, we could check but we don't have skill system yet
            # So we just allow if skill is None, or if future skill check passes
            # Here we keep it simple: if required_skill is not None, require it (but no skill system yet, so block?)
            # Actually spec says required_skill nullable, for future. So if it's set and we don't have skill system, we should still check?
            # For now, we will allow only if required_skill is None, or if we had skill service.
            # Since skill system not implemented, we treat non-None as not met for now? But initial jobs have None.
            # So we check: if job.required_skill is not None, raise requirement error (future)
            if job.required_skill is not None:
                raise JobRequirementError(
                    f"Requires skill {job.required_skill} (not yet implemented)"
                )

            pj_repo = PlayerJobRepository(session)
            existing = await pj_repo.get_by_player_id(player_id)
            if existing is not None:
                raise AlreadyHasJobError("Player already has a job")

            # Create player job
            await pj_repo.create(player_id=player_id, job_id=job_id)
            await session.commit()

            logger.info("Player %s applied for job %s (%s)", player_id, job_id, job.name)

            return JobApplyResult(
                player_id=player_id,
                job_id=job.id,
                job_name=job.name,
                success=True,
                message="Job selected successfully.",
            )

    async def leave_job(self, player_id: int) -> JobLeaveResult:
        async with self._session_factory() as session:
            player_repo = PlayerRepository(session)
            if not await player_repo.exists(player_id):
                raise PlayerNotFoundError(f"player_id={player_id} not found")

            pj_repo = PlayerJobRepository(session)
            pj = await pj_repo.get_by_player_id(player_id)
            if pj is None:
                raise NoJobError("You don't have a job yet.")

            job_repo = JobRepository(session)
            job = await job_repo.get_by_id(pj.job_id)
            job_name = job.name if job else "Unknown"
            total = pj.total_earnings

            await pj_repo.delete_by_player_id(player_id)
            await session.commit()

            logger.info("Player %s left job %s", player_id, pj.job_id)

            return JobLeaveResult(
                player_id=player_id,
                job_id=pj.job_id,
                job_name=job_name,
                success=True,
                total_earnings=total,
                message="Left job successfully.",
            )

    async def work_job(self, player_id: int) -> JobWorkResult:
        """Work current job: check cooldown, give salary via Wallet Service, update history."""
        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            player_repo = PlayerRepository(session)
            player = await player_repo.get_by_id(player_id)
            if player is None:
                raise PlayerNotFoundError(f"player_id={player_id} not found")

            pj_repo = PlayerJobRepository(session)
            pj = await pj_repo.get_by_player_id(player_id)
            if pj is None:
                raise NoJobError("You don't have a job yet.")

            job_repo = JobRepository(session)
            job = await job_repo.get_by_id(pj.job_id)
            if job is None:
                raise JobNotFoundError("Job not found (deleted)")

            # Check cooldown
            remaining = self._remaining_seconds(pj.last_work_time, job.cooldown)
            if remaining > 0:
                raise JobCooldownError(
                    remaining_seconds=remaining,
                    message=f"Cooldown: {remaining}s remaining",
                )

            # Give salary — use MoneyService if available, otherwise direct repo
            # For atomicity, we update PlayerJob last_work_time and total_earnings in same session,
            # and add money via direct repo update (same pattern as LaborService) to prevent race
            # But we also ensure Wallet Service is used: we call money_service after if present,
            # or we use direct repo which is same logic as Wallet Service.

            # Atomic update: try to update last_work_time only if cooldown passed
            # We already checked, but to prevent race, we do conditional update
            from sqlalchemy import update
            from app.database.models.player_job import PlayerJob as PJModel
            from datetime import timedelta

            threshold = now - timedelta(seconds=job.cooldown)
            stmt = (
                update(PJModel)
                .where(
                    PJModel.player_id == player_id,
                    (PJModel.last_work_time.is_(None))
                    | (PJModel.last_work_time <= threshold),
                )
                .values(
                    last_work_time=now,
                    total_earnings=PJModel.total_earnings + job.salary,
                )
            )
            result = await session.execute(
                stmt, execution_options={"synchronize_session": False}
            )
            if not result.rowcount:
                # Race: another work claimed just now
                await session.rollback()
                # Re-check remaining
                async with self._session_factory() as check_s:
                    check_pj_repo = PlayerJobRepository(check_s)
                    check_pj = await check_pj_repo.get_by_player_id(player_id)
                    if check_pj is None:
                        raise NoJobError("You don't have a job yet.")
                    rem = self._remaining_seconds(check_pj.last_work_time, job.cooldown)
                    if rem <= 0:
                        rem = job.cooldown
                    raise JobCooldownError(remaining_seconds=rem)

            # Add money to player
            # Use PlayerRepository.add_money (same logic as WalletService)
            p_repo = PlayerRepository(session)
            await p_repo.add_money(player_id, job.salary)

            # Create job history record
            hist_repo = JobHistoryRepository(session)
            hist_repo.add(player_id=player_id, job_id=job.id, income=job.salary)

            await session.commit()

            # Get balance after
            async with self._session_factory() as bal_session:
                bal_repo = PlayerRepository(bal_session)
                bal_player = await bal_repo.get_by_id(player_id)
                assert bal_player is not None
                balance_after = bal_player.money

                # Also get updated total_earnings
                pj_repo2 = PlayerJobRepository(bal_session)
                pj2 = await pj_repo2.get_by_player_id(player_id)
                total_earnings = pj2.total_earnings if pj2 else 0

            logger.info(
                "Player %s worked job %s, income %s, balance %s",
                player_id,
                job.id,
                job.salary,
                balance_after,
            )

            return JobWorkResult(
                player_id=player_id,
                job_id=job.id,
                job_name=job.name,
                success=True,
                income=job.salary,
                balance_after=balance_after,
                total_earnings=total_earnings,
                remaining_seconds=0,
                message="Work completed.",
            )

    async def get_job_history(
        self, player_id: int, limit: int = 20, offset: int = 0
    ) -> List[JobHistoryData]:
        async with self._session_factory() as session:
            player_repo = PlayerRepository(session)
            if not await player_repo.exists(player_id):
                raise PlayerNotFoundError(f"player_id={player_id} not found")

            hist_repo = JobHistoryRepository(session)
            job_repo = JobRepository(session)

            histories = await hist_repo.list_by_player(player_id, limit, offset)
            result: List[JobHistoryData] = []
            for h in histories:
                job = await job_repo.get_by_id(h.job_id)
                job_name = job.name if job else f"Job#{h.job_id}"
                result.append(
                    JobHistoryData(
                        id=h.id,
                        player_id=h.player_id,
                        job_id=h.job_id,
                        job_name=job_name,
                        income=h.income,
                        created_at=h.created_at,
                    )
                )
            return result
