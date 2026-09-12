"""RelationshipEvent ORM model — every «رابطه» between two spouses."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core import constants
from app.database.models.base import Base

# Outcomes of a relationship event (kept as strings so future systems —
# romance dates, gifts, arguments — can add kinds without a migration).
OUTCOME_EVENT: str = "event"
OUTCOME_PREGNANCY: str = "pregnancy"
OUTCOME_BIRTH: str = "birth"


class RelationshipEvent(Base):
    """One intimacy event of a married couple and its pregnancy roll.

    The pregnancy chance was evaluated by the family domain at event time;
    the outcome is stored so the couple's history can be replayed exactly.

    Fields:
        id: Primary key.
        marriage_id: FK to ``marriages.id``.
        initiator_player_id: Who triggered the event.
        partner_player_id: The other spouse.
        satisfaction: Relationship points after the event heal (+heal).
        pregnancy_chance_percent / rolled_percent: The dice, recorded.
        outcome: ``event`` | ``pregnancy`` | ``birth``.
        note: Optional human text for history screens.
        created_at: When the event happened.
    """

    __tablename__ = "relationship_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    marriage_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("marriages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    initiator_player_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    partner_player_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    satisfaction: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=constants.FAMILY_RELATIONSHIP_START_POINTS,
        server_default=text(str(constants.FAMILY_RELATIONSHIP_START_POINTS)),
    )
    pregnancy_chance_percent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=constants.FAMILY_PREGNANCY_CHANCE,
        server_default=text(str(constants.FAMILY_PREGNANCY_CHANCE)),
    )
    rolled_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    outcome: Mapped[str] = mapped_column(
        String(16), nullable=False, default=OUTCOME_EVENT, server_default=text("'event'")
    )
    note: Mapped[str] = mapped_column(String(140), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<RelationshipEvent id={self.id} marriage={self.marriage_id} "
            f"outcome={self.outcome!r} roll={self.rolled_percent}>"
        )
