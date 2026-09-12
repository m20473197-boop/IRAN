"""Repository for Job model."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.job import Job


class JobRepository:
    """Database access for ``jobs`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Reads -----------------------------------------------------------

    async def get_by_id(self, job_id: int) -> Job | None:
        return await self._session.get(Job, job_id)

    async def get_by_name(self, name: str) -> Job | None:
        stmt = select(Job).where(Job.name == name)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_active(self) -> list[Job]:
        stmt = (
            select(Job)
            .where(Job.is_active.is_(True))
            .order_by(Job.required_level, Job.hourly_salary)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self) -> list[Job]:
        stmt = select(Job).order_by(Job.required_level, Job.hourly_salary)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        stmt = select(Job.id)
        result = await self._session.execute(stmt)
        return len(result.scalars().all())

    async def update_fields(self, job_id: int, **fields: object) -> bool:
        """Update a whitelisted set of job settings (admin panel)."""
        allowed = {
            "description",
            "salary",
            "hourly_salary",
            "employer",
            "cooldown",
            "required_level",
            "is_active",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"unknown job attributes: {sorted(unknown)}")
        if not fields:
            return False
        statement = update(Job).where(Job.id == job_id).values(**fields)
        result = await self._session.execute(
            statement, execution_options={"synchronize_session": False}
        )
        cached = await self._session.get(Job, job_id)
        if cached is not None:
            self._session.expire(cached)
        return bool(result.rowcount)

    # --- Writes ----------------------------------------------------------

    def add(self, job: Job) -> None:
        self._session.add(job)

    async def create_job(
        self,
        name: str,
        description: str,
        salary: int,
        cooldown: int,
        required_level: int,
        required_skill: str | None = None,
        is_active: bool = True,
        hourly_salary: int | None = None,
        employer: str = "",
    ) -> Job:
        job = Job(
            name=name,
            description=description,
            salary=salary,
            hourly_salary=hourly_salary if hourly_salary is not None else salary,
            employer=employer,
            cooldown=cooldown,
            required_level=required_level,
            required_skill=required_skill,
            is_active=is_active,
        )
        self._session.add(job)
        await self._session.flush()
        return job

    async def ensure_initial_jobs(self) -> list[Job]:
        """Sync the canonical «خر حمالی» catalog into the ``jobs`` table.

        Runs once per catalog version: the marker lives in ``bot_settings``
        (``jobs_catalog_version``), so normal restarts never touch job rows
        and admin edits of jobs survive. When the stored version differs
        (first boot after a catalog update):

        * every catalog job is created — or updated in place when a row with
          that name already exists (this also backfills the hourly-salary /
          employer columns on databases older than the time-based system),
        * retired legacy jobs (``JOB_RETIRED_NAMES``) are **disabled** —
          never deleted, because ``player_jobs``/history rows still point at
          them.

        Returns the active jobs.
        """
        from app.core import constants
        from app.database.repositories.bot_setting_repository import (
            BotSettingRepository,
        )

        settings = BotSettingRepository(self._session)
        stored_version = await settings.get(constants.JOBS_CATALOG_SETTING_KEY)
        if stored_version == constants.JOB_CATALOG_VERSION:
            return await self.list_active()

        existing = {job.name: job for job in await self.list_all()}

        for spec in constants.JOB_CATALOG:
            job = existing.get(spec["name"])
            if job is None:
                await self.create_job(**spec)
                continue
            for field, value in spec.items():
                setattr(job, field, value)
            job.is_active = True
            self._session.add(job)

        for name in constants.JOB_RETIRED_NAMES:
            retired = existing.get(name)
            if retired is not None and retired.is_active:
                retired.is_active = False
                self._session.add(retired)

        await settings.set(constants.JOBS_CATALOG_SETTING_KEY, constants.JOB_CATALOG_VERSION)
        await self._session.flush()
        return await self.list_active()
