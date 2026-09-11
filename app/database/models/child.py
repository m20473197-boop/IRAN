"""Child ORM model — one row per child born to a married couple."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
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

GENDER_BOY: str = "boy"
GENDER_GIRL: str = "girl"


class Child(Base):
    """A child of two players («فرزند»).

    ``birth_date`` is the real birth timestamp. The last three columns are the
    prepared structure for the future Child-growth / Education / Family
    expenses systems — today they simply stay at their defaults and every
    future update writes them through this row.

    Fields:
        id: Primary key — the child id.
        marriage_id: FK to the parents' marriage (``CASCADE`` keeps the
            genealogy consistent with the marriage row).
        relationship_event_id: The event whose pregnancy roll produced this
            child (``SET NULL`` — a child never disappears with its event).
        father_player_id / mother_player_id: FKs to ``players.id`` — the
            parents keep their own rows; either spouse can be father or
            mother (same-sex couples are stored by player id, names are
            never duplicated).
        name: Display name chosen at birth (Persian).
        gender: ``boy`` | ``girl``.
        birth_date: When the child was born.
        growth_stage: Reserved (0 = infant … future: toddler/child/teen).
        education_level: Reserved for the Education system (0 = none).
        expense_total: Reserved for Family expenses (Toman, exact integer).
        created_at / updated_at: Row lifecycle timestamps.
    """

    __tablename__ = "children"
    __table_args__ = (
        CheckConstraint(
            "father_player_id <> mother_player_id", name="parents_differ"
        ),
        Index("ix_children_marriage", "marriage_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    marriage_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("marriages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_event_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("relationship_events.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        unique=True,
    )

    father_player_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mother_player_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(48), nullable=False, default="نوزاد")
    gender: Mapped[str] = mapped_column(
        String(8), nullable=False, default=GENDER_BOY, server_default=text("'boy'")
    )

    birth_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # --- Prepared for future systems (growth / education / expenses) --------
    growth_stage: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    education_level: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    expense_total: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
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

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Child id={self.id} marriage={self.marriage_id} "
            f"father={self.father_player_id} mother={self.mother_player_id} "
            f"name={self.name!r}>"
        )
