from __future__ import annotations
from datetime import datetime
from sqlalchemy import select, update, and_, or_, func
from app.database.models.divar_listing import DivarListing
from app.database.models.house import House
from app.database.models.land import Land
class DivarRepository:
 def __init__(self,s): self.s=s
 async def create(self,owner,typ,aid,price):
  q=await self.s.scalar(select(DivarListing).where(DivarListing.asset_type==typ,DivarListing.asset_id==aid,DivarListing.status=='active'))
  if q: raise ValueError('already listed')
  row=DivarListing(seller_player_id=owner,asset_type=typ,asset_id=aid,price=price); self.s.add(row); await self.s.flush(); return row
 async def get(self,lid): return await self.s.get(DivarListing,lid)
 async def search(self,typ=None,city=None,neighborhood=None,min_price=None,max_price=None,min_area=None,max_area=None,query=None,page=0,size=5):
  q=select(DivarListing).where(DivarListing.status=='active')
  if typ:q=q.where(DivarListing.asset_type==typ)
  if min_price is not None:q=q.where(DivarListing.price>=min_price)
  if max_price is not None:q=q.where(DivarListing.price<=max_price)
  if city or neighborhood or min_area is not None or max_area is not None:
   table=House if typ=='house' else Land if typ=='land' else None
   if table is not None:
    q=q.join(table, and_(DivarListing.asset_id==table.id,DivarListing.asset_type==typ))
    if city:q=q.where(table.city.ilike(f'%{city}%'))
    if neighborhood:q=q.where(table.neighborhood.ilike(f'%{neighborhood}%'))
    if min_area is not None:q=q.where(table.area_sqm>=min_area)
    if max_area is not None:q=q.where(table.area_sqm<=max_area)
  if query:q=q.where(or_(DivarListing.asset_type.ilike(f'%{query}%'),DivarListing.price.cast(str).ilike(f'%{query}%')))
  total=await self.s.scalar(select(func.count()).select_from(q.subquery()))
  rows=list((await self.s.scalars(q.order_by(DivarListing.id.desc()).offset(page*size).limit(size))).all()); return rows,total
 async def mine(self,owner): return list((await self.s.scalars(select(DivarListing).where(DivarListing.seller_player_id==owner,DivarListing.status=='active'))).all())
 async def cancel(self,row): row.status='cancelled'; await self.s.flush()
