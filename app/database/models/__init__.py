"""ORM models package. Importing it registers every model on ``Base.metadata``."""

from app.database.models.base import Base
from app.database.models.house import House
from app.database.models.house_listing import HouseListing
from app.database.models.house_sale import HouseSale
from app.database.models.house_transaction import HouseTransaction
from app.database.models.job import Job
from app.database.models.job_event import JobEvent
from app.database.models.job_history import JobHistory
from app.database.models.level_up_history import LevelUpHistory
from app.database.models.player import Player
from app.database.models.player_job import PlayerJob
from app.database.models.rental_contract import RentalContract
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
    "House",
    "HouseListing",
    "HouseSale",
    "RentalContract",
    "HouseTransaction",
]
