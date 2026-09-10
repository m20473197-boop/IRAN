"""Repositories package — the only layer that talks to the database."""

from app.database.repositories.job_event_repository import JobEventRepository
from app.database.repositories.job_history_repository import JobHistoryRepository
from app.database.repositories.job_repository import JobRepository
from app.database.repositories.level_up_repository import LevelUpRepository
from app.database.repositories.player_job_repository import PlayerJobRepository
from app.database.repositories.player_repository import PlayerRepository
from app.database.repositories.xp_transaction_repository import (
    XPTransactionRepository,
)

__all__ = [
    "PlayerRepository",
    "XPTransactionRepository",
    "LevelUpRepository",
    "JobRepository",
    "PlayerJobRepository",
    "JobHistoryRepository",
    "JobEventRepository",
]
