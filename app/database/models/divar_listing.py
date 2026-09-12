from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, CheckConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database.models.base import Base
class DivarListing(Base):
    __tablename__='divar_listings'
    id: Mapped[int]=mapped_column(primary_key=True)
    seller_player_id: Mapped[int]=mapped_column(ForeignKey('players.id',ondelete='CASCADE'),nullable=False,index=True)
    asset_type: Mapped[str]=mapped_column(String(16),nullable=False)
    asset_id: Mapped[int]=mapped_column(BigInteger,nullable=False)
    price: Mapped[int]=mapped_column(BigInteger,nullable=False)
    status: Mapped[str]=mapped_column(String(16),nullable=False,default='active',index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,server_default=func.now(),nullable=False)
    sold_at: Mapped[datetime|None]=mapped_column(DateTime)
    __table_args__=(CheckConstraint('price > 0','ck_divar_price_positive'),Index('ux_divar_active_asset','asset_type','asset_id','status',unique=True))
