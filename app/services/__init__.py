"""Application services and the registry used by the Telegram layer.

Dependency flow (strict):

    Telegram handler -> Service -> Repository -> Database

Services own transactions and business rules; handlers only translate
between Telegram objects and service calls.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.admin_service import AdminService
from app.services.business_service import BusinessService
from app.services.family_service import FamilyService
from app.services.housing_service import HousingService
from app.services.job_service import JobService
from app.services.level_service import LevelService
from app.services.money_service import MoneyService
from app.services.market_service import MarketService
from app.services.divar_service import DivarService
from app.services.player_service import PlayerService
from app.services.realestate_service import RealEstateService

__all__ = [
    "ServiceRegistry",
    "AdminService",
    "PlayerService",
    "LevelService",
    "MoneyService",
    "JobService",
    "BusinessService",
    "HousingService",
    "FamilyService",
]


class ServiceRegistry:
    """Bundles every service; created once at startup and shared via bot_data."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.players = PlayerService(session_factory)
        self.levels = LevelService(session_factory)
        self.money = MoneyService(session_factory)
        self.market = MarketService(session_factory)
        self.divar = DivarService(session_factory, self.money)
        self.jobs = JobService(session_factory, money_service=self.money)
        self.housing = HousingService(session_factory, level_service=self.levels)
        self.realestate = RealEstateService(
            session_factory, level_service=self.levels, housing_service=self.housing
        )
        # Marriage & Family system — pure commands, no menus. Reuses the
        # LevelService for family XP; profile integration reads the family
        # snapshot through the provider below.
        self.family = FamilyService(session_factory, level_service=self.levels)
        # Business system — predefined catalog, wallet-paid startups, daily
        # income credited to the business balance (never the player wallet).
        self.business = BusinessService(session_factory, money_service=self.money)
        self.players.set_family_provider(self.family.get_snapshot_by_telegram_user_id)
        self.admin = AdminService(
            session_factory,
            level_service=self.levels,
            housing_service=self.housing,
            realestate_service=self.realestate,
        )

    def attach_database(self, database) -> None:
        """Hand engine access to services that need it (admin backup/restore)."""
        self.admin.attach_database(database)
