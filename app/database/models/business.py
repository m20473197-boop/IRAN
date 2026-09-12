"""Business ORM model — one row per business owned by a player.

A business is a wallet-for-itself: the owner paid ``startup_cost`` once
through the MoneyService, and every daily income roll is credited to the
business' own ``balance`` (never directly to the player's wallet). The
``last_income_date`` column is what makes "once per day" a *database*
invariant, not just a service-layer check: the crediting repository updates
a row only while its date still differs from the day being credited.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base

# Lifecycle states of a business row. "closed" stops the daily income and is
# reserved for admin/future use — players cannot create or close businesses
# by hand; only the predefined catalog can be started.
STATUS_ACTIVE: str = "active"
STATUS_CLOSED: str = "closed"


class Business(Base):
    """A player-owned business instance.

    Fields:
        id: Primary key — the business id.
        owner_player_id: FK to ``players.id`` — the owner.
        business_key: The predefined catalog key this row was started from.
        type_name: Snapshot of the catalog display name at start time.
        startup_cost: What the owner actually paid (exact Toman, immutable).
        balance: Money the business has accumulated (exact Toman, >= 0).
        status: ``active`` | ``closed`` — only active rows earn income.
        created_at: When the business was started (saved start date).
        last_income_date: The Iranian business day of the latest income
            grant — the once-per-day guard (``None`` = never credited).
        last_income_amount: How much the latest grant paid (for "today's
            income" display; 0 until the first credit).
        total_income: Lifetime income credited to this business.
        income_days: How many days actually paid out.
    """

    __tablename__ = "businesses"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_businesses_balance_non_negative"),
        CheckConstraint(
            "startup_cost >= 0", name="ck_businesses_cost_non_negative"
        ),
        CheckConstraint(
            "status IN ('active', 'closed')", name="ck_businesses_status"
        ),
        Index("ix_businesses_owner", "owner_player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    owner_player_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
    )
    business_key: Mapped[str] = mapped_column(String(32), nullable=False)
    type_name: Mapped[str] = mapped_column(String(64), nullable=False)

    startup_cost: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=STATUS_ACTIVE,
        server_default=text("'active'"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_income_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, default=None
    )
    last_income_amount: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    total_income: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    income_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    def __repr__(self) -> str:  # pragma: no cover — debugging aid only
        return (
            f"<Business id={self.id} owner={self.owner_player_id} "
            f"key={self.business_key!r} balance={self.balance} "
            f"status={self.status!r}>"
        )
