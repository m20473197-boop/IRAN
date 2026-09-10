"""Application services and the registry used by the Telegram layer.

Dependency flow (strict):

    Telegram handler -> Service -> Repository -> Database

Services own transactions and business rules; handlers only translate
between Telegram objects and service calls.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.labor_service import LaborService
from app.services.level_service import LevelService
from app.services.money_service import MoneyService
from app.services.player_service import PlayerService

__all__ = [
    "ServiceRegistry",
    "PlayerService",
    "LevelService",
    "MoneyService",
    "LaborService",
]


class ServiceRegistry:
    """Bundles every service; created once at startup and shared via bot_data."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.players = PlayerService(session_factory)
        self.levels = LevelService(session_factory)
        self.money = MoneyService(session_factory)
        # LaborService depends on MoneyService for wallet integration
        self.labor = LaborService(session_factory, money_service=self.money)
