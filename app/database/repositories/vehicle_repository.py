from sqlalchemy import select,func
from app.database.models.vehicle import VehicleModel,OwnedVehicle
from app.game.vehicles import CAR_CATALOG
class VehicleRepository:
 def __init__(self,s): self.s=s
 async def ensure(self):
  for x in CAR_CATALOG:
   r=await self.s.scalar(select(VehicleModel).where(VehicleModel.key==x.key))
   if not r:self.s.add(VehicleModel(key=x.key,name=x.name,price=x.price,available=x.available,shoti_eligible=x.shoti_eligible))
  await self.s.flush()
 async def models(self): return list((await self.s.scalars(select(VehicleModel).where(VehicleModel.available).order_by(VehicleModel.id))).all())
 async def get(self,key): return await self.s.scalar(select(VehicleModel).where(VehicleModel.key==key))
 async def mine(self,pid): return list((await self.s.scalars(select(OwnedVehicle).where(OwnedVehicle.owner_player_id==pid,OwnedVehicle.status=='owned').order_by(OwnedVehicle.id))).all())
