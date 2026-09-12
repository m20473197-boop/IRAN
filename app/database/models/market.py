from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, Boolean, DateTime, Index, Numeric, String, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database.models.base import Base

class MarketAsset(Base):
    __tablename__ = "iran_market_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(24,2), nullable=True)
    previous_price: Mapped[Decimal | None] = mapped_column(Numeric(24,2), nullable=True)
    base_value: Mapped[Decimal | None] = mapped_column(Numeric(24,2), nullable=True)
    last_successful_update: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_attempted_update: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

class MarketPriceHistory(Base):
    __tablename__ = "market_price_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("iran_market_assets.id", ondelete="CASCADE"), nullable=False)
    previous_price: Mapped[Decimal | None] = mapped_column(Numeric(24,2))
    new_price: Mapped[Decimal] = mapped_column(Numeric(24,2), nullable=False)
    change_amount: Mapped[Decimal] = mapped_column(Numeric(24,2), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (Index("ix_market_history_asset_time", "asset_id", "updated_at"),)
