"""Repositories package — the only layer that talks to the database."""

from app.database.repositories.admin_audit_log_repository import (
    AdminAuditLogRepository,
)
from app.database.repositories.bot_setting_repository import BotSettingRepository
from app.database.repositories.business_repository import (
    BusinessRepository,
)
from app.database.repositories.child_repository import ChildRepository
from app.database.repositories.divorce_record_repository import (
    DivorceRecordRepository,
)
from app.database.repositories.family_history_repository import (
    FamilyHistoryRepository,
)
from app.database.repositories.construction_project_repository import (
    ConstructionProjectRepository,
)
from app.database.repositories.economic_event_repository import (
    EconomicEventRepository,
)
from app.database.repositories.market_asset_repository import MarketAssetRepository
from app.database.repositories.market_price_tick_repository import (
    MarketPriceTickRepository,
)
from app.database.repositories.house_listing_repository import (
    HouseListingRepository,
)
from app.database.repositories.house_repository import HouseRepository
from app.database.repositories.house_sale_repository import HouseSaleRepository
from app.database.repositories.house_transaction_repository import (
    HouseTransactionRepository,
)
from app.database.repositories.job_event_repository import JobEventRepository
from app.database.repositories.job_history_repository import JobHistoryRepository
from app.database.repositories.job_repository import JobRepository
from app.database.repositories.land_repository import LandRepository
from app.database.repositories.marriage_repository import MarriageRepository
from app.database.repositories.relationship_event_repository import (
    RelationshipEventRepository,
)
from app.database.repositories.land_transaction_repository import (
    LandTransactionRepository,
)
from app.database.repositories.level_up_repository import LevelUpRepository
from app.database.repositories.player_job_repository import PlayerJobRepository
from app.database.repositories.player_repository import PlayerRepository
from app.database.repositories.property_upgrade_repository import (
    PropertyUpgradeRepository,
)
from app.database.repositories.renovation_project_repository import (
    RenovationProjectRepository,
)
from app.database.repositories.rental_contract_repository import (
    RentalContractRepository,
)
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
    "HouseRepository",
    "HouseListingRepository",
    "HouseSaleRepository",
    "RentalContractRepository",
    "HouseTransactionRepository",
    "LandRepository",
    "LandTransactionRepository",
    "ConstructionProjectRepository",
    "RenovationProjectRepository",
    "PropertyUpgradeRepository",
    "AdminAuditLogRepository",
    "BotSettingRepository",
    "EconomicEventRepository",
    "MarketAssetRepository",
    "MarketPriceTickRepository",
    "MarriageRepository",
    "ChildRepository",
    "DivorceRecordRepository",
    "RelationshipEventRepository",
    "FamilyHistoryRepository",
    "BusinessRepository",
]
