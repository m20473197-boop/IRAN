"""MarriageProposal ORM model — «ازدواج» requests waiting for an answer."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core import constants
from app.database.models.base import Base

# Proposal lifecycle.
STATUS_PENDING: str = "pending"
STATUS_ACCEPTED: str = "accepted"
STATUS_REJECTED: str = "rejected"
STATUS_CANCELLED: str = "cancelled"
STATUS_EXPIRED: str = "expired"


class MarriageProposal(Base):
    """A marriage request from one player to another.

    Created when the sender replies to the target's message with «ازدواج»;
    answered by the target with «قبول» / «رد». Only one *pending* proposal may
    wait for the same receiver at a time (partial unique index).

    Fields:
        id: Primary key.
        sender_player_id / receiver_player_id: FKs to ``players.id``.
        status: ``pending`` | ``accepted`` | ``rejected`` | ``cancelled``.
        mahr: Mahriyeh offered by the sender (exact Toman, ≥ 0).
        note: Optional free text typed with the command.
        proposal_message_id / answer_message_id: Telegram message ids of the
            bot's request card and of the answer (audit only, nullable).
        expires_at: When the pending proposal lapses (expired by rule).
        created_at / answered_at: Lifecycle timestamps.
    """

    __tablename__ = "marriage_proposals"
    __table_args__ = (
        CheckConstraint("sender_player_id <> receiver_player_id", name="not_self"),
        CheckConstraint("mahr >= 0", name="mahr_non_negative"),
        Index(
            "ux_proposals_pending_receiver",
            "receiver_player_id",
            unique=True,
            sqlite_where=text("status = 'pending'"),
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_proposals_pending_sender", "sender_player_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    sender_player_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    receiver_player_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=STATUS_PENDING,
        server_default=text("'pending'"),
    )
    mahr: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=constants.FAMILY_DEFAULT_MAHRIYEH,
        server_default=text(str(constants.FAMILY_DEFAULT_MAHRIYEH)),
    )
    note: Mapped[str] = mapped_column(String(140), nullable=False, default="")

    proposal_message_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, default=None
    )
    answer_message_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, default=None
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<MarriageProposal id={self.id} {self.sender_player_id}->"
            f"{self.receiver_player_id} status={self.status!r} mahr={self.mahr}>"
        )
