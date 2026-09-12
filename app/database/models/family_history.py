"""FamilyHistory ORM model — the append-only story of every family.

One row per notable family event, per player involved, so the future
«تاریخچه خانواده» screens (and admins) can replay what happened: who
married whom, who cheated (and was caught), every child, every divorce.
Rows are never modified — that is the whole point of the table.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base

# Event kinds (strings, so future family features just add one).
EVENT_MARRIAGE: str = "marriage"
EVENT_PROPOSAL: str = "proposal"
EVENT_PROPOSAL_REJECTED: str = "proposal_rejected"
EVENT_RELATIONSHIP: str = "relationship"
EVENT_PREGNANCY: str = "pregnancy"
EVENT_BIRTH: str = "birth"
EVENT_CHEAT: str = "cheat"
EVENT_CHEAT_DISCOVERED: str = "cheat_discovered"
EVENT_FORGIVENESS: str = "forgiveness"
EVENT_DIVORCE_REQUEST: str = "divorce_request"
EVENT_DIVORCE_FORGIVEN: str = "divorce_forgiven"
EVENT_DIVORCE: str = "divorce"
EVENT_CHILD_EXPENSE: str = "child_expense"  # future family-expenses system


class FamilyHistory(Base):
    """One append-only family-history entry.

    Fields:
        id: Primary key.
        player_id: The player this entry belongs to (indexed — their log).
        marriage_id: Related marriage when there is one (nullable).
        event_type: One of the ``EVENT_*`` constants.
        details: Short human-readable Persian text (what happened).
        created_at: When it happened.
    """

    __tablename__ = "family_histories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    player_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    marriage_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("marriages.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    details: Mapped[str] = mapped_column(String(256), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<FamilyHistory id={self.id} player={self.player_id} "
            f"event={self.event_type!r}>"
        )
