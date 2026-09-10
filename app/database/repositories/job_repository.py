"""Repository for Job model."""

from __future__ import annotations

from sqlalchemy import func, select, update
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
        """Seed initial jobs if they don't exist. Returns all active jobs."""
        from app.core import constants

        initial_jobs = [
            {
                "name": constants.JOB_WORKER_NAME,
                "description": constants.JOB_WORKER_DESCRIPTION,
                "salary": constants.JOB_WORKER_SALARY,
                "hourly_salary": constants.JOB_WORKER_HOURLY_SALARY,
                "employer": constants.JOB_WORKER_EMPLOYER,
                "cooldown": constants.JOB_WORKER_COOLDOWN,
                "required_level": constants.JOB_WORKER_REQUIRED_LEVEL,
            },
            {
                "name": constants.JOB_EMPLOYEE_NAME,
                "description": constants.JOB_EMPLOYEE_DESCRIPTION,
                "salary": constants.JOB_EMPLOYEE_SALARY,
                "hourly_salary": constants.JOB_EMPLOYEE_HOURLY_SALARY,
                "employer": constants.JOB_EMPLOYEE_EMPLOYER,
                "cooldown": constants.JOB_EMPLOYEE_COOLDOWN,
                "required_level": constants.JOB_EMPLOYEE_REQUIRED_LEVEL,
            },
            {
                "name": constants.JOB_SPECIALIST_NAME,
                "description": constants.JOB_SPECIALIST_DESCRIPTION,
                "salary": constants.JOB_SPECIALIST_SALARY,
                "hourly_salary": constants.JOB_SPECIALIST_HOURLY_SALARY,
                "employer": constants.JOB_SPECIALIST_EMPLOYER,
                "cooldown": constants.JOB_SPECIALIST_COOLDOWN,
                "required_level": constants.JOB_SPECIALIST_REQUIRED_LEVEL,
            },
        ]

        existing = await self.list_all()
        existing_by_name = {job.name: job for job in existing}

        for job_data in initial_jobs:
            job = existing_by_name.get(job_data["name"])
            if job is None:
                await self.create_job(**job_data)
                continue
            # Backfill fields added by the time-based salary update on jobs
            # that already existed in an older database.
            changed = False
            if not job.employer and job_data.get("employer"):
                job.employer = job_data["employer"]
                changed = True
            if job.hourly_salary == 0 and job_data.get("hourly_salary"):
                job.hourly_salary = job_data["hourly_salary"]
                changed = True
            if changed:
                self._session.add(job)

        await self._session.flush()
        return await self.list_active()
