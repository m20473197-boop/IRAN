"""Business system DTOs — the contract between the service and the bot layer.

The bot layer never sees ORM rows; everything it renders is one of these.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class BusinessData:
    """A player-owned business, fully resolved for display (no ORM leaks).

    ``type_name`` is the snapshot of the catalog name taken at start time,
    so renaming a catalog entry later never rewrites history.
    """

    id: int
    owner_player_id: int
    business_key: str
    type_name: str
    description: str
    startup_cost: int
    balance: int
    status: str  # "active" | "closed" — only active businesses earn
    created_at: datetime
    last_income_date: date | None
    last_income_amount: int
    total_income: int
    income_days: int

    def credited_on(self, day: date | None) -> bool:
        """Whether the daily income of ``day`` was already credited."""
        return day is not None and self.last_income_date == day


@dataclass(frozen=True)
class BusinessStartResult:
    """Outcome of a successful «شروع کسب و کار»."""

    business: BusinessData
    paid_startup_cost: int
    wallet_balance_after: int


@dataclass(frozen=True)
class BusinessIncomeResult:
    """Outcome of one daily-income grant for one business."""

    business_id: int
    type_name: str
    day: date
    amount: int  # 0 when nothing was granted
    granted: bool  # False = already credited today (or not eligible)
    balance_after: int


@dataclass(frozen=True)
class BusinessOverview:
    """What the «کسب و کارهای من» screen renders."""

    businesses: list[BusinessData] = field(default_factory=list)
    today: date | None = None
    max_owned: int = 0
    wallet_balance: int = 0

    @property
    def total_balance(self) -> int:
        return sum(b.balance for b in self.businesses)

    @property
    def today_income(self) -> int:
        if self.today is None:
            return 0
        return sum(
            b.last_income_amount
            for b in self.businesses
            if b.last_income_date == self.today
        )
