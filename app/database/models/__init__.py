"""ORM models package. Importing it registers every model on ``Base.metadata``."""

from app.database.models.base import Base
from app.database.models.player import Player

__all__ = ["Base", "Player"]
