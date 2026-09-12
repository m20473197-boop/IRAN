from datetime import datetime
from sqlalchemy import BigInteger,Boolean,DateTime,ForeignKey,String,func,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.database.models.base import Base
class VehicleModel(Base):
 __tablename__='vehicle_models'; id:Mapped[int]=mapped_column(primary_key=True); key:Mapped[str]=mapped_column(String(32),unique=True); name:Mapped[str]=mapped_column(String(64)); price:Mapped[int]=mapped_column(BigInteger); available:Mapped[bool]=mapped_column(Boolean,default=True); shoti_eligible:Mapped[bool]=mapped_column(Boolean,default=False)
class OwnedVehicle(Base):
 __tablename__='owned_vehicles'; id:Mapped[int]=mapped_column(primary_key=True); owner_player_id:Mapped[int]=mapped_column(ForeignKey('players.id',ondelete='CASCADE'),index=True); model_id:Mapped[int]=mapped_column(ForeignKey('vehicle_models.id'),index=True); purchase_price:Mapped[int]=mapped_column(BigInteger); purchased_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now()); status:Mapped[str]=mapped_column(String(16),default='owned'); __table_args__=(UniqueConstraint('owner_player_id','model_id','status',name='ux_owned_vehicle_active_model'),)
