"""ORM models package. Importing it registers every model on ``Base.metadata``."""

from app.database.models.base import Base
from app.database.models.job import Job
from app.database.models.job_event import JobEvent
from app.database.models.job_history import JobHistory
from app.database.models.level_up_history import LevelUpHistory
from app.database.models.player import Player
from app.database.models.player_job import PlayerJob
from app.database.models.xp_transaction import XPTransaction

__all__ = [
    "Base",
    "Player",
    "XPTransaction",
    "LevelUpHistory",
    "Job",
    "PlayerJob",
    "JobHistory",
    "JobEvent",
]
