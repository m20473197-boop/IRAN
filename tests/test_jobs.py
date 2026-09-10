"""Job and Income System tests — time-based salary system."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from app.core import constants
from app.database.models.player_job import PlayerJob
from app.database.repositories.job_repository import JobRepository
from app.services import ServiceRegistry
from app.services.job_service import (
    AlreadyHasJobError,
    JobNotFoundError,
    JobNotEnoughTimeError,
    JobRequirementError,
    JobService,
    NoJobError,
)


async def _set_started_at(services, player_id: int, minutes_ago: int) -> None:
    """Rewind the work-start clock so elapsed time is deterministic."""
    past = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    async with services.jobs._session_factory() as session:
        stmt = (
            update(PlayerJob)
            .where(PlayerJob.player_id == player_id)
            .values(started_at=past)
        )
        await session.execute(stmt, execution_options={"synchronize_session": False})
        await session.commit()


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

    # Create custom job with hourly salary + employer
    async with db.session_factory() as session:
        repo = JobRepository(session)
        custom = await repo.create_job(
            name="برنامه‌نویس",
            description="تست",
            salary=500_000,
            hourly_salary=750_000,
            employer="استارتاپ زرین",
            cooldown=600,
            required_level=5,
        )
        await session.commit()
        assert custom.id is not None
        assert custom.name == "برنامه‌نویس"
        assert custom.salary == 500_000
        assert custom.hourly_salary == 750_000
        assert custom.employer == "استارتاپ زرین"


async def test_each_job_has_hourly_salary_and_employer(services):
    jobs = await services.jobs.get_available_jobs()
    assert len(jobs) >= 3

    for job in jobs:
        assert job.hourly_salary > 0
        assert job.employer.strip() != ""

    salaries = {j.name: j.hourly_salary for j in jobs}
    employers = {j.name: j.employer for j in jobs}
    assert salaries[constants.JOB_WORKER_NAME] == constants.JOB_WORKER_HOURLY_SALARY
    assert salaries[constants.JOB_EMPLOYEE_NAME] == constants.JOB_EMPLOYEE_HOURLY_SALARY
    assert (
        salaries[constants.JOB_SPECIALIST_NAME]
        == constants.JOB_SPECIALIST_HOURLY_SALARY
    )
    assert employers[constants.JOB_WORKER_NAME] == constants.JOB_WORKER_EMPLOYER
    assert employers[constants.JOB_EMPLOYEE_NAME] == constants.JOB_EMPLOYEE_EMPLOYER
    assert (
        employers[constants.JOB_SPECIALIST_NAME] == constants.JOB_SPECIALIST_EMPLOYER
    )


async def test_applying_for_a_job_saves_start_time(services, register):
    player = await register(tg_id=8002)

    jobs = await services.jobs.get_available_jobs()
    worker_job = next(j for j in jobs if j.name == constants.JOB_WORKER_NAME)

    result = await services.jobs.apply_job(player.player_id, worker_job.id)

    assert result.success is True
    assert result.job_id == worker_job.id
    assert result.job_name == worker_job.name
    assert result.employer == worker_job.employer
    assert result.hourly_salary == worker_job.hourly_salary

    # Check player job exists with a saved work start time
    player_job = await services.jobs.get_player_job(player.player_id)
    assert player_job is not None
    assert player_job.job_id == worker_job.id
    assert player_job.job_name == worker_job.name
    assert player_job.employer == worker_job.employer
    assert player_job.hourly_salary == worker_job.hourly_salary
    assert player_job.started_at is not None
    assert player_job.total_earnings == 0
    # Just started — no meaningful accrued salary yet.
    assert player_job.worked_minutes == 0
    assert player_job.accrued_salary == 0


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


async def test_settlement_normal_payment(services, register, monkeypatch):
    player = await register(tg_id=8005)

    jobs = await services.jobs.get_available_jobs()
    worker = next(j for j in jobs if j.name == constants.JOB_WORKER_NAME)
    await services.jobs.apply_job(player.player_id, worker.id)

    await _set_started_at(services, player.player_id, minutes_ago=120)  # 2 hours
    monkeypatch.setattr(services.jobs, "_roll_employer_event", lambda: ("normal", 0))

    result = await services.jobs.settle_with_employer(player.player_id)

    assert result.event_type == "normal"
    assert result.status == "paid"
    assert result.paid is True
    assert result.worked_minutes == 120
    assert result.hourly_salary == constants.JOB_WORKER_HOURLY_SALARY
    assert result.gross_salary == constants.JOB_WORKER_HOURLY_SALARY * 2  # 120_000
    assert result.final_amount == result.gross_salary
    assert result.bonus_amount == 0
    assert result.penalty_amount == 0

    # Paid through the wallet
    assert result.balance_after == result.gross_salary
    assert await services.money.get_balance(player.player_id) == result.gross_salary

    # Work timer reset
    pj = await services.jobs.get_player_job(player.player_id)
    assert pj is not None
    assert pj.worked_minutes == 0
    assert pj.total_earnings == result.gross_salary


async def test_settlement_bonus_payment(services, register, monkeypatch):
    player = await register(tg_id=8006)

    jobs = await services.jobs.get_available_jobs()
    worker = next(j for j in jobs if j.name == constants.JOB_WORKER_NAME)
    await services.jobs.apply_job(player.player_id, worker.id)

    await _set_started_at(services, player.player_id, minutes_ago=60)  # 1 hour
    monkeypatch.setattr(services.jobs, "_roll_employer_event", lambda: ("bonus", 20))

    result = await services.jobs.settle_with_employer(player.player_id)

    gross = constants.JOB_WORKER_HOURLY_SALARY  # 1 hour
    assert result.event_type == "bonus"
    assert result.bonus_percent == 20
    assert result.bonus_amount == gross * 20 // 100
    assert result.final_amount == gross + result.bonus_amount
    assert result.paid is True
    assert await services.money.get_balance(player.player_id) == result.final_amount


async def test_settlement_mistake_penalty(services, register, monkeypatch):
    player = await register(tg_id=8007)

    jobs = await services.jobs.get_available_jobs()
    worker = next(j for j in jobs if j.name == constants.JOB_WORKER_NAME)
    await services.jobs.apply_job(player.player_id, worker.id)

    # 2 hours -> 120_000 gross, 30% penalty -> 84_000
    await _set_started_at(services, player.player_id, minutes_ago=120)
    monkeypatch.setattr(services.jobs, "_roll_employer_event", lambda: ("mistake", 30))

    result = await services.jobs.settle_with_employer(player.player_id)

    gross = constants.JOB_WORKER_HOURLY_SALARY * 2  # 120_000
    assert result.event_type == "mistake"
    assert result.penalty_percent == 30
    assert result.penalty_amount == gross * 30 // 100  # 36_000
    assert result.final_amount == gross - result.penalty_amount  # 84_000
    assert result.paid is True
    assert await services.money.get_balance(player.player_id) == result.final_amount


async def test_settlement_delayed_payment_comes_later(services, register, monkeypatch):
    player = await register(tg_id=8008)

    jobs = await services.jobs.get_available_jobs()
    worker = next(j for j in jobs if j.name == constants.JOB_WORKER_NAME)
    await services.jobs.apply_job(player.player_id, worker.id)

    await _set_started_at(services, player.player_id, minutes_ago=120)
    monkeypatch.setattr(services.jobs, "_roll_employer_event", lambda: ("delayed", 0))

    first = await services.jobs.settle_with_employer(player.player_id)

    assert first.event_type == "delayed"
    assert first.status == "delayed"
    assert first.paid is False
    assert first.final_amount == 0

    # No money received immediately
    assert await services.money.get_balance(player.player_id) == 0

    # Work timer NOT reset — the accrued hours are still pending
    pj = await services.jobs.get_player_job(player.player_id)
    assert pj is not None
    assert pj.worked_minutes >= 120

    # Later, the employer pays normally — the delayed work is included.
    await _set_started_at(services, player.player_id, minutes_ago=120)
    monkeypatch.setattr(services.jobs, "_roll_employer_event", lambda: ("normal", 0))
    second = await services.jobs.settle_with_employer(player.player_id)

    gross = constants.JOB_WORKER_HOURLY_SALARY * 2
    assert second.paid is True
    assert second.final_amount == gross
    assert await services.money.get_balance(player.player_id) == gross


async def test_settlement_before_one_minute_is_rejected(services, register):
    player = await register(tg_id=8009)

    jobs = await services.jobs.get_available_jobs()
    worker = next(j for j in jobs if j.name == constants.JOB_WORKER_NAME)
    await services.jobs.apply_job(player.player_id, worker.id)

    with pytest.raises(JobNotEnoughTimeError):
        await services.jobs.settle_with_employer(player.player_id)

    # Nothing was paid, timer still running from the start.
    assert await services.money.get_balance(player.player_id) == 0


async def test_employer_event_rolls_stay_in_bounds():
    # Exercise the real random roller with a seeded RNG.
    service = JobService(None, rng=random.Random(12345))  # type: ignore[arg-type]
    valid_types = {"normal", "bonus", "mistake", "delayed"}
    for _ in range(500):
        event_type, percent = service._roll_employer_event()
        assert event_type in valid_types
        if event_type == "mistake":
            assert (
                constants.MISTAKE_PENALTY_MIN_PERCENT
                <= percent
                <= constants.MISTAKE_PENALTY_MAX_PERCENT
            )
        elif event_type == "bonus":
            assert constants.BONUS_MIN_PERCENT <= percent <= constants.BONUS_MAX_PERCENT
        else:
            assert percent == 0


async def test_all_events_are_saved(services, register, monkeypatch):
    player = await register(tg_id=8010)

    jobs = await services.jobs.get_available_jobs()
    worker = next(j for j in jobs if j.name == constants.JOB_WORKER_NAME)
    await services.jobs.apply_job(player.player_id, worker.id)

    rolls = [
        ("normal", 0),
        ("bonus", 15),
        ("mistake", 40),
        ("delayed", 0),
    ]
    for event, percent in rolls:
        await _set_started_at(services, player.player_id, minutes_ago=60)
        monkeypatch.setattr(
            services.jobs, "_roll_employer_event", lambda e=event, p=percent: (e, p)
        )
        await services.jobs.settle_with_employer(player.player_id)

    events = await services.jobs.get_salary_events(player.player_id, limit=20)
    # Newest first.
    assert len(events) == 4
    kinds = {e.event_type for e in events}
    assert kinds == {"normal", "bonus", "mistake", "delayed"}

    delayed = next(e for e in events if e.event_type == "delayed")
    assert delayed.status == "delayed"
    assert delayed.final_amount == 0
    assert delayed.gross_salary > 0

    mistake = next(e for e in events if e.event_type == "mistake")
    assert mistake.penalty_percent == 40
    assert mistake.penalty_amount > 0
    assert mistake.final_amount == mistake.gross_salary - mistake.penalty_amount

    bonus = next(e for e in events if e.event_type == "bonus")
    assert bonus.bonus_percent == 15
    assert bonus.final_amount == bonus.gross_salary + bonus.bonus_amount

    assert all(e.employer == worker.employer for e in events)


async def test_database_persistence(db, services, register):
    player = await register(tg_id=8009)

    jobs = await services.jobs.get_available_jobs()
    worker = next(j for j in jobs if j.name == constants.JOB_WORKER_NAME)

    await services.jobs.apply_job(player.player_id, worker.id)
    await _set_started_at(services, player.player_id, minutes_ago=60)
    # Deterministic normal payment for this isolated test
    services.jobs._roll_employer_event = lambda: ("normal", 0)
    await services.jobs.settle_with_employer(player.player_id)

    # Simulate restart
    new_services = ServiceRegistry(db.session_factory)

    # Job should persist
    pj = await new_services.jobs.get_player_job(player.player_id)
    assert pj is not None
    assert pj.job_id == worker.id
    assert pj.total_earnings == constants.JOB_WORKER_HOURLY_SALARY

    # Events should persist
    events = await new_services.jobs.get_salary_events(player.player_id)
    assert len(events) == 1
    assert events[0].event_type == "normal"
    assert events[0].gross_salary == constants.JOB_WORKER_HOURLY_SALARY

    # Money should persist
    assert (
        await new_services.money.get_balance(player.player_id)
        == constants.JOB_WORKER_HOURLY_SALARY
    )

    # Available jobs should still exist
    all_jobs = await new_services.jobs.get_available_jobs()
    assert len(all_jobs) >= 3


async def test_leave_job(services, register):
    player = await register(tg_id=8010)

    jobs = await services.jobs.get_available_jobs()
    worker = next(j for j in jobs if j.name == constants.JOB_WORKER_NAME)

    await services.jobs.apply_job(player.player_id, worker.id)
    await _set_started_at(services, player.player_id, minutes_ago=60)
    services.jobs._roll_employer_event = lambda: ("normal", 0)
    await services.jobs.settle_with_employer(player.player_id)

    # Leave
    leave_result = await services.jobs.leave_job(player.player_id)
    assert leave_result.success is True
    assert leave_result.total_earnings == constants.JOB_WORKER_HOURLY_SALARY

    # No job now
    assert await services.jobs.get_player_job(player.player_id) is None

    # Settle should fail
    with pytest.raises(NoJobError):
        await services.jobs.settle_with_employer(player.player_id)

    # Can apply again
    result = await services.jobs.apply_job(player.player_id, worker.id)
    assert result.success is True


async def test_job_messages_simple():
    from app.bot.messages.job import (
        job_applied_success,
        job_no_job,
        job_settle_too_early,
    )

    applied = job_applied_success("کارگر", "کارگاه حاج رضا", 60_000)
    assert "کارگر" in applied
    assert "موفقیت" in applied
    assert "کارگاه حاج رضا" in applied
    assert "تومان" in applied

    no_job = job_no_job()
    assert "شغلی نداری" in no_job

    too_early = job_settle_too_early()
    assert "دقیقه" in too_early
