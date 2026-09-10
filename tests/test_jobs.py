"""Job and Income System tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.core import constants
from app.database.repositories.job_repository import JobRepository
from app.database.repositories.player_job_repository import PlayerJobRepository
from app.game.shared.errors import PlayerNotFoundError
from app.services.job_service import (
    AlreadyHasJobError,
    JobCooldownError,
    JobNotFoundError,
    JobRequirementError,
    NoJobError,
)


async def test_creating_jobs(services, db):
    # Ensure initial jobs are seeded
    jobs = await services.jobs.ensure_initial_jobs()
    assert len(jobs) >= 3

    # Check via repository
    async with db.session_factory() as session:
        repo = JobRepository(session)
        all_jobs = await repo.list_all()
        assert len(all_jobs) >= 3
        names = {j.name for j in all_jobs}
        assert constants.JOB_WORKER_NAME in names
        assert constants.JOB_EMPLOYEE_NAME in names
        assert constants.JOB_SPECIALIST_NAME in names

    # Create custom job
    async with db.session_factory() as session:
        repo = JobRepository(session)
        custom = await repo.create_job(
            name="برنامه‌نویس",
            description="تست",
            salary=500_000,
            cooldown=600,
            required_level=5,
        )
        await session.commit()
        assert custom.id is not None
        assert custom.name == "برنامه‌نویس"
        assert custom.salary == 500_000


async def test_listing_available_jobs(services, register):
    await register(tg_id=8001)
    jobs = await services.jobs.get_available_jobs()

    assert len(jobs) >= 3
    for job in jobs:
        assert job.is_active is True
        assert job.salary > 0
        assert job.cooldown > 0
        assert job.required_level >= 1

    # Check salaries match constants (initial jobs)
    salaries = {j.name: j.salary for j in jobs}
    assert salaries[constants.JOB_WORKER_NAME] == constants.JOB_WORKER_SALARY
    assert salaries[constants.JOB_EMPLOYEE_NAME] == constants.JOB_EMPLOYEE_SALARY
    assert salaries[constants.JOB_SPECIALIST_NAME] == constants.JOB_SPECIALIST_SALARY


async def test_applying_for_a_job(services, register):
    player = await register(tg_id=8002)

    jobs = await services.jobs.get_available_jobs()
    worker_job = next(j for j in jobs if j.name == constants.JOB_WORKER_NAME)

    result = await services.jobs.apply_job(player.player_id, worker_job.id)

    assert result.success is True
    assert result.job_id == worker_job.id
    assert result.job_name == worker_job.name

    # Check player job exists
    player_job = await services.jobs.get_player_job(player.player_id)
    assert player_job is not None
    assert player_job.job_id == worker_job.id
    assert player_job.job_name == worker_job.name
    assert player_job.total_earnings == 0


async def test_preventing_multiple_active_jobs(services, register):
    player = await register(tg_id=8003)

    jobs = await services.jobs.get_available_jobs()
    worker = next(j for j in jobs if j.name == constants.JOB_WORKER_NAME)
    employee = next(j for j in jobs if j.name == constants.JOB_EMPLOYEE_NAME)

    # Need level 2 for employee, so level up player
    await services.levels.add_xp(player.player_id, 100, reason="level up")  # to level 2

    await services.jobs.apply_job(player.player_id, worker.id)

    # Try to apply for another job — should fail
    with pytest.raises(AlreadyHasJobError):
        await services.jobs.apply_job(player.player_id, employee.id)

    # Still has first job
    pj = await services.jobs.get_player_job(player.player_id)
    assert pj is not None
    assert pj.job_id == worker.id


async def test_checking_job_requirements(services, register):
    player = await register(tg_id=8004)  # level 1

    jobs = await services.jobs.get_available_jobs()
    specialist = next(j for j in jobs if j.name == constants.JOB_SPECIALIST_NAME)
    # Specialist requires level 3
    assert specialist.required_level == 3

    with pytest.raises(JobRequirementError):
        await services.jobs.apply_job(player.player_id, specialist.id)

    # Level up to 3
    # Level 1->2 needs 100, 2->3 needs 135, total 235
    await services.levels.add_xp(player.player_id, 235, reason="level up to 3")
    assert await services.levels.get_level(player.player_id) == 3

    # Now should succeed
    result = await services.jobs.apply_job(player.player_id, specialist.id)
    assert result.success is True

    # Test non-existent job
    with pytest.raises(JobNotFoundError):
        await services.jobs.apply_job(player.player_id, 999999)


async def test_working_successfully(services, register):
    player = await register(tg_id=8005)

    jobs = await services.jobs.get_available_jobs()
    worker = next(j for j in jobs if j.name == constants.JOB_WORKER_NAME)

    await services.jobs.apply_job(player.player_id, worker.id)

    balance_before = await services.money.get_balance(player.player_id)
    assert balance_before == 0

    result = await services.jobs.work_job(player.player_id)

    assert result.success is True
    assert result.income == worker.salary
    assert result.income == 50_000
    assert result.balance_after == 50_000
    assert result.total_earnings == 50_000

    balance_after = await services.money.get_balance(player.player_id)
    assert balance_after == 50_000


async def test_preventing_work_before_cooldown_ends(services, register):
    player = await register(tg_id=8006)

    jobs = await services.jobs.get_available_jobs()
    worker = next(j for j in jobs if j.name == constants.JOB_WORKER_NAME)

    await services.jobs.apply_job(player.player_id, worker.id)
    first = await services.jobs.work_job(player.player_id)
    assert first.success is True

    # Immediate second work should fail with cooldown
    with pytest.raises(JobCooldownError) as exc_info:
        await services.jobs.work_job(player.player_id)

    assert exc_info.value.remaining_seconds > 0
    assert exc_info.value.remaining_seconds <= worker.cooldown

    # Balance should not increase
    assert await services.money.get_balance(player.player_id) == worker.salary

    # Simulate cooldown passed
    past = datetime.now(timezone.utc) - timedelta(seconds=worker.cooldown + 10)
    async with services.jobs._session_factory() as session:
        from app.database.models.player_job import PlayerJob

        from sqlalchemy import update

        stmt = (
            update(PlayerJob)
            .where(PlayerJob.player_id == player.player_id)
            .values(last_work_time=past)
        )
        await session.execute(stmt, execution_options={"synchronize_session": False})
        await session.commit()

    second = await services.jobs.work_job(player.player_id)
    assert second.success is True
    assert await services.money.get_balance(player.player_id) == worker.salary * 2


async def test_salary_payment_through_wallet_service(services, register):
    player = await register(tg_id=8007)

    jobs = await services.jobs.get_available_jobs()
    employee = next(j for j in jobs if j.name == constants.JOB_EMPLOYEE_NAME)

    # Level up to 2 for employee
    await services.levels.add_xp(player.player_id, 100, reason="up")

    await services.jobs.apply_job(player.player_id, employee.id)

    # Work and check via MoneyService
    await services.jobs.work_job(player.player_id)
    balance = await services.money.get_balance(player.player_id)
    assert balance == employee.salary
    assert balance == 100_000

    # Add extra money via MoneyService, ensure stacking
    await services.money.add_money(player.player_id, 10_000)
    assert await services.money.get_balance(player.player_id) == 110_000

    # Work after cooldown
    past = datetime.now(timezone.utc) - timedelta(seconds=employee.cooldown + 5)
    async with services.jobs._session_factory() as session:
        from app.database.models.player_job import PlayerJob
        from sqlalchemy import update

        stmt = (
            update(PlayerJob)
            .where(PlayerJob.player_id == player.player_id)
            .values(last_work_time=past)
        )
        await session.execute(stmt, execution_options={"synchronize_session": False})
        await session.commit()

    await services.jobs.work_job(player.player_id)
    assert await services.money.get_balance(player.player_id) == 210_000


async def test_job_history_creation(services, register):
    player = await register(tg_id=8008)

    jobs = await services.jobs.get_available_jobs()
    worker = next(j for j in jobs if j.name == constants.JOB_WORKER_NAME)

    await services.jobs.apply_job(player.player_id, worker.id)

    # Work twice with cooldown manipulation
    await services.jobs.work_job(player.player_id)

    past = datetime.now(timezone.utc) - timedelta(seconds=worker.cooldown + 1)
    async with services.jobs._session_factory() as session:
        from app.database.models.player_job import PlayerJob
        from sqlalchemy import update

        stmt = (
            update(PlayerJob)
            .where(PlayerJob.player_id == player.player_id)
            .values(last_work_time=past)
        )
        await session.execute(stmt, execution_options={"synchronize_session": False})
        await session.commit()

    await services.jobs.work_job(player.player_id)

    # Check history
    history = await services.jobs.get_job_history(player.player_id, limit=10)
    assert len(history) == 2
    assert all(h.income == worker.salary for h in history)
    assert all(h.job_id == worker.id for h in history)
    assert history[0].job_name == worker.name


async def test_database_persistence(db, services, register):
    player = await register(tg_id=8009)

    jobs = await services.jobs.get_available_jobs()
    worker = next(j for j in jobs if j.name == constants.JOB_WORKER_NAME)

    await services.jobs.apply_job(player.player_id, worker.id)
    await services.jobs.work_job(player.player_id)

    # Simulate restart
    from app.services import ServiceRegistry

    new_services = ServiceRegistry(db.session_factory)

    # Job should persist
    pj = await new_services.jobs.get_player_job(player.player_id)
    assert pj is not None
    assert pj.job_id == worker.id
    assert pj.total_earnings == worker.salary

    # History should persist
    history = await new_services.jobs.get_job_history(player.player_id)
    assert len(history) == 1
    assert history[0].income == worker.salary

    # Money should persist
    assert await new_services.money.get_balance(player.player_id) == worker.salary

    # Available jobs should still exist
    all_jobs = await new_services.jobs.get_available_jobs()
    assert len(all_jobs) >= 3


async def test_leave_job(services, register):
    player = await register(tg_id=8010)

    jobs = await services.jobs.get_available_jobs()
    worker = next(j for j in jobs if j.name == constants.JOB_WORKER_NAME)

    await services.jobs.apply_job(player.player_id, worker.id)
    await services.jobs.work_job(player.player_id)

    # Leave
    leave_result = await services.jobs.leave_job(player.player_id)
    assert leave_result.success is True
    assert leave_result.total_earnings == worker.salary

    # No job now
    assert await services.jobs.get_player_job(player.player_id) is None

    # Work should fail
    with pytest.raises(NoJobError):
        await services.jobs.work_job(player.player_id)

    # Can apply again
    result = await services.jobs.apply_job(player.player_id, worker.id)
    assert result.success is True


async def test_concurrent_work_does_not_bypass_cooldown(services, register):
    player = await register(tg_id=8011)

    jobs = await services.jobs.get_available_jobs()
    worker = next(j for j in jobs if j.name == constants.JOB_WORKER_NAME)

    await services.jobs.apply_job(player.player_id, worker.id)

    # 5 concurrent work attempts
    results = []
    errors = []

    async def try_work():
        try:
            r = await services.jobs.work_job(player.player_id)
            results.append(r)
        except JobCooldownError as e:
            errors.append(e)
        except Exception as e:
            errors.append(e)

    await asyncio.gather(*[try_work() for _ in range(5)])

    assert len(results) == 1
    assert len(errors) == 4
    assert await services.money.get_balance(player.player_id) == worker.salary


async def test_job_messages_simple():
    from app.bot.messages.job import (
        job_applied_success,
        job_no_job,
        job_work_cooldown,
        job_work_success,
    )

    # Simple messages, no motivational
    applied = job_applied_success("کارگر")
    assert "کارگر" in applied
    assert "موفقیت" in applied

    success = job_work_success(100_000, 100_000)
    assert "کار انجام شد" in success
    assert "تومان" in success

    cooldown = job_work_cooldown(125)
    assert "زمان" in cooldown

    no_job = job_no_job()
    assert "شغلی نداری" in no_job
