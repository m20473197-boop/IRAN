import asyncio,logging,os
from app.database.repositories.vehicle_repository import VehicleRepository
from app.database.models.vehicle import OwnedVehicle
from app.game.shared.errors import DomainError,InsufficientFundsError
class VehicleError(DomainError):pass
class VehicleUnavailableError(VehicleError):pass
class VehicleLimitError(VehicleError):pass
class VehicleService:
 def __init__(self,sf,money): self.sf=sf;self.money=money;self.limit=int(os.getenv('VEHICLE_MAX_OWNED','0'));self.lock=asyncio.Lock()
 async def ensure_catalog(self):
  async with self.sf() as s: await VehicleRepository(s).ensure();await s.commit()
 async def catalog(self):
  async with self.sf() as s:return await VehicleRepository(s).models()
 async def mine(self,pid):
  async with self.sf() as s:return await VehicleRepository(s).mine(pid)
 async def purchase(self,pid,key):
  async with self.lock:
   async with self.sf() as s:
    repo=VehicleRepository(s); await repo.ensure(); m=await repo.get(key)
    if not m or not m.available: raise VehicleUnavailableError('unavailable')
    owned=await repo.mine(pid)
    if self.limit and len(owned)>=self.limit: raise VehicleLimitError('limit')
    try: await self.money.remove_money(pid,m.price)
    except InsufficientFundsError: raise
    try:
     row=OwnedVehicle(owner_player_id=pid,model_id=m.id,purchase_price=m.price);s.add(row);await s.commit();return row,m
    except Exception:
     await self.money.add_money(pid,m.price);raise
