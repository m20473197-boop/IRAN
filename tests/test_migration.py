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


async def test_existing_job_rows_are_backfilled_with_salary_and_employer(tmp_path):
    db_path = tmp_path / "old.db"
    _create_old_schema_jobs(db_path.as_posix())

    database = Database(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await database.create_all()

    from app.services import ServiceRegistry

    services = ServiceRegistry(database.session_factory)
    jobs = await services.jobs.ensure_initial_jobs()

    worker = next(j for j in jobs if j.name == "کارگر")
    assert worker.hourly_salary > 0
    assert worker.employer.strip() != ""

    await database.dispose()
