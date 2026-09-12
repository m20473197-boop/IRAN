"""DivorceRecord ORM model — the permanent history of ended marriages."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base


class DivorceRecord(Base):
    """One finalized divorce («طلاق») — never deleted, even if ex-spouses
    remarry each other later.

    Fields:
        id: Primary key.
        marriage_id: The dissolved marriage (``SET NULL`` keeps the record
            even if the marriage row were ever removed).
        initiator_player_id: Who typed the final «طلاق».
        partner_a_id / partner_b_id: Snapshot of the couple at divorce time
            (canonical order — same convention as ``marriages``).
        mahr: The Mahriyeh that was agreed at the marriage.
        mahr_payer_player_id / mahr_payee_player_id: Who *had* to pay it.
        paid_amount: What actually moved through the wallets (≤ mahr).
        unpaid_debt: Mahriyeh the payer could not cover — kept as an
            explicit, visible record of the debt created by the split.
        reason: Short label (e.g. ``divorced`` / ``cheating_discovered``).
        created_at: When the divorce was finalized.
    """

    __tablename__ = "divorce_records"
    __table_args__ = (
        CheckConstraint("paid_amount >= 0", name="paid_non_negative"),
        CheckConstraint("unpaid_debt >= 0", name="debt_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    marriage_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("marriages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    initiator_player_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    partner_a_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    partner_b_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    mahr: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    mahr_payer_player_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    mahr_payee_player_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    paid_amount: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    unpaid_debt: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )

    reason: Mapped[str] = mapped_column(
        String(64), nullable=False, default="divorced", server_default=text("'divorced'")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<DivorceRecord id={self.id} marriage={self.marriage_id} "
            f"initiator={self.initiator_player_id} mahr={self.mahr} "
            f"paid={self.paid_amount} debt={self.unpaid_debt}>"
        )
