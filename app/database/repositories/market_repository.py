from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models.market import MarketAsset, MarketPriceHistory

class MarketRepository:
    def __init__(self, session: AsyncSession): self.session=session
    async def ensure_assets(self, specs):
        rows=[]
        for key,name in specs:
            row=await self.session.scalar(select(MarketAsset).where(MarketAsset.asset_key==key))
            if row is None:
                row=MarketAsset(asset_key=key,display_name=name); self.session.add(row)
            rows.append(row)
        await self.session.flush(); return rows
    async def list_assets(self): return list((await self.session.scalars(select(MarketAsset).where(MarketAsset.is_active).order_by(MarketAsset.id))).all())
    async def get(self,key): return await self.session.scalar(select(MarketAsset).where(MarketAsset.asset_key==key,MarketAsset.is_active))
    async def mark_attempt(self, when): await self.session.execute(update(MarketAsset).values(last_attempted_update=when))
    async def update_price(self,row,new,when,source):
        old=row.current_price
        row.previous_price=old; row.current_price=Decimal(str(new)); row.last_successful_update=when
        change=Decimal(str(new))-(old or Decimal("0")); direction="up" if change>0 else "down" if change<0 else "same"
        self.session.add(MarketPriceHistory(asset_id=row.id,previous_price=old,new_price=row.current_price,change_amount=change,direction=direction,updated_at=when,source=source))
    async def history(self,key,limit=50):
        q=select(MarketPriceHistory).join(MarketAsset).where(MarketAsset.asset_key==key).order_by(MarketPriceHistory.updated_at.desc()).limit(limit)
        return list((await self.session.scalars(q)).all())
