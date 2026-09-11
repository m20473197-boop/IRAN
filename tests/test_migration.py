"""Additive column-migration tests — old databases gain new job columns."""

from __future__ import annotations

import sqlite3

from app.database.database import Database


def _create_old_schema_jobs(db_path: str) -> None:
    """Recreate the pre-update ``jobs`` table shape (no hourly_salary/employer)."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE jobs (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(64) NOT NULL UNIQUE,
            description VARCHAR(256) NOT NULL,
            salary BIGINT NOT NULL,
            cooldown INTEGER NOT NULL,
            required_level INTEGER NOT NULL,
            required_skill VARCHAR(64),
            is_active BOOLEAN NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "INSERT INTO jobs (name, description, salary, cooldown, required_level, "
        "is_active) VALUES ('کارگر', 'کار ساده با درآمد کم', 50000, 300, 1, 1)"
    )
    conn.commit()
    conn.close()


async def test_existing_database_gains_new_job_columns(tmp_path):
    db_path = tmp_path / "old.db"
    _create_old_schema_jobs(db_path.as_posix())

    database = Database(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await database.create_all()

    async with database.engine.begin() as connection:
        columns = {
            row[1]
            for row in (
                await connection.exec_driver_sql("PRAGMA table_info(jobs)")
            ).fetchall()
        }
        assert "hourly_salary" in columns
        assert "employer" in columns

    await database.dispose()


async def test_existing_database_gets_the_new_catalog_and_retires_old_jobs(tmp_path):
    """The «خر حمالی» catalog replaces the legacy jobs on old databases.

    The seeded legacy row (کارگر, 50 000, no employer) must NOT keep a
    selectable job: the catalog sync disables retired jobs and seeds the
    six canonical ones — without dropping the old row (history integrity).
    """
    db_path = tmp_path / "old.db"
    _create_old_schema_jobs(db_path.as_posix())

    database = Database(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await database.create_all()

    from app.core import constants
    from app.services import ServiceRegistry

    services = ServiceRegistry(database.session_factory)
    jobs = await services.jobs.ensure_initial_jobs()

    assert {j.name for j in jobs} == {spec["name"] for spec in constants.JOB_CATALOG}
    banaei = next(j for j in jobs if j.name == "بنایی")
    assert banaei.hourly_salary == 80_000
    assert banaei.employer.strip() != ""

    # the retired row survives — disabled, not deleted
    async with database.session_factory() as session:
        from sqlalchemy import select

        from app.database.models.job import Job

        worker = (
            await session.execute(select(Job).where(Job.name == "کارگر"))
        ).scalar_one()
        assert worker.is_active is False

    await database.dispose()
