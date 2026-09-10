"""House ORM model — every real-estate object in the game."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base


class House(Base):
    """One unique house with realistic properties.

    Fields:
        id: Primary key — the house's unique ID.
        city / neighborhood: Location (must exist in the housing catalog).
        area_sqm: Floor area in square meters.
        bedrooms / living_rooms / bathrooms: Room counts.
        kitchen_type: ``مدرن`` | ``معمولی`` | ``قدیمی``.
        building_age_years: Age of the building in years.
        parking / elevator / storage: Facility flags.
        quality: ``عالی`` | ``خوب`` | ``متوسط`` | ``ضعیف``.
        owner_player_id: FK to players.id — ``None`` means the house is still
            on the system market (bank/developer) and can be bought by anyone.
            Setting it is *the* ownership record (the player's asset list is
            derived from it).

    The price is intentionally **not stored**: it is always computed
    dynamically from the attributes and the market catalog (see
    ``app/game/housing/pricing.py``), so a future live-market feed moves all
    prices automatically.
    """

    __tablename__ = "houses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    city: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    neighborhood: Mapped[str] = mapped_column(String(64), nullable=False)

    area_sqm: Mapped[int] = mapped_column(Integer, nullable=False)
    bedrooms: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    living_rooms: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    bathrooms: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    kitchen_type: Mapped[str] = mapped_column(String(32), nullable=False, default="معمولی")
    building_age_years: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    parking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    elevator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    storage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    quality: Mapped[str] = mapped_column(String(32), nullable=False, default="خوب")

    owner_player_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover — debugging aid only
        return (
            f"<House id={self.id} city={self.city!r} "
            f"neighborhood={self.neighborhood!r} area={self.area_sqm} "
            f"owner={self.owner_player_id}>"
        )
