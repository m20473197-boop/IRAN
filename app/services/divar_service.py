from __future__ import annotations
from datetime import datetime
from sqlalchemy import select,update
from app.database.models.house import House
from app.database.models.land import Land
from app.database.repositories.divar_repository import DivarRepository
from app.game.shared.errors import DomainError,InsufficientFundsError
class DivarError(DomainError): pass
class InvalidPriceError(DivarError): pass
class NotOwnerError(DivarError): pass
class ListingNotFoundError(DivarError): pass
class OwnListingError(DivarError): pass
class NotAvailableError(DivarError): pass
class DivarService:
 def __init__(self,sf,money_service): self.sf=sf; self.money=money_service
 def _table(self,t): return House if t=='house' else Land if t=='land' else None
 async def create_listing(self,pid,typ,aid,price):
  if price<=0: raise InvalidPriceError('price')
  table=self._table(typ)
  if table is None: raise DivarError('unsupported asset')
  async with self.sf() as s:
   asset=await s.get(table,aid)
   if asset is None or asset.owner_player_id!=pid: raise NotOwnerError('owner')
   row=await DivarRepository(s).create(pid,typ,aid,price); await s.commit(); return row
 async def search(self,**kwargs):
  async with self.sf() as s:return await DivarRepository(s).search(**kwargs)
 async def get_listing(self,lid):
  async with self.sf() as s:
   row=await DivarRepository(s).get(lid)
   if row is None: raise ListingNotFoundError('missing')
   table=self._table(row.asset_type); asset=await s.get(table,row.asset_id) if table else None
   return row,asset
 async def mine(self,pid):
  async with self.sf() as s:return await DivarRepository(s).mine(pid)
 async def cancel(self,pid,lid):
  async with self.sf() as s:
   r=await DivarRepository(s).get(lid)
   if not r or r.status!='active': raise NotAvailableError('inactive')
   if r.seller_player_id!=pid: raise NotOwnerError('owner')
   await DivarRepository(s).cancel(r); await s.commit()
 async def purchase(self,buyer,lid):
  async with self.sf() as s:
   repo=DivarRepository(s); r=await repo.get(lid)
   if not r or r.status!='active': raise NotAvailableError('inactive')
   if r.seller_player_id==buyer: raise OwnListingError('self')
   table=self._table(r.asset_type); asset=await s.get(table,r.asset_id) if table else None
   if asset is None or asset.owner_player_id!=r.seller_player_id: raise NotAvailableError('ownership changed')
   try: await self.money.remove_money(buyer,r.price)
   except InsufficientFundsError: raise
   try:
    await self.money.add_money(r.seller_player_id,r.price)
    asset.owner_player_id=buyer; r.status='sold'; r.sold_at=datetime.utcnow(); await s.commit(); return r
   except Exception:
    await self.money.add_money(buyer,r.price); raise
