"""Marriage ORM model — one row per marriage (active or dissolved).

A marriage is *the* link between two players. Both directions live in one
row (partner_a / partner_b, ordered by player id) and an active player can
only ever appear in one active row — guaranteed by a partial unique index,
so two accepted proposals can never create a bigamous double marriage.
"""

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

from app.core import constants
from app.database.models.base import Base

# Lifecycle states of a marriage row.
STATUS_ACTIVE: str = "active"
STATUS_DIVORCED: str = "divorced"


class Marriage(Base):
    """An ongoing (or ended) marriage between two players.

    Fields:
        id: Primary key — the marriage id.
        partner_a_id / partner_b_id: FKs to ``players.id``; ``partner_a_id``
            is always the smaller player id (CHECK keeps the pair canonical).
        status: ``active`` | ``divorced`` — history rows are never deleted.
        mahr: The Mahriyeh (مهریه) agreed at the proposal — exact Toman,
            settled through the wallet when the divorce is finalized.
        relationship_points: Health of the relationship (0…100); discovered
            cheating burns it, «رابطه» and «بخشش» heal it.
        cheating_count: Total *discovered* betrayals (drives the Mahriyeh
            liability and the "divorce possibility" consequence).
        cheater_a_count / cheater_b_count: How many times each side was
            discovered — attribution of the Mahriyeh liability.
        last_relationship_at / last_cheat_at: Cooldown anchors for «رابطه»
            and «خیانت».
        divorce_requested_by_player_id / divorce_requested_at: The pending
            divorce request (the spouse may forgive inside the window; a
            second «طلاق» — by either spouse — finalizes the split).
        children_count: Children born from this marriage (denormalized
            mirror of ``children``, updated in the same transaction).
        married_at: When the marriage started (the saved marriage date).
        dissolved_at: When a divorce ended it (``None`` while active).
        created_at / updated_at: Row lifecycle timestamps.
    """

    __tablename__ = "marriages"
    __table_args__ = (
        CheckConstraint("partner_a_id <> partner_b_id", name="partners_differ"),
        CheckConstraint(
            f"relationship_points >= {constants.FAMILY_RELATIONSHIP_MIN_POINTS} "
            f"AND relationship_points <= {constants.FAMILY_RELATIONSHIP_MAX_POINTS}",
            name="points_in_band",
        ),
        # One *active* marriage per player — the database itself forbids
        # bigamy (partial unique index; SQLite 3.8+ / PostgreSQL).
        Index(
            "ux_marriages_partner_a_active",
            "partner_a_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "ux_marriages_partner_b_active",
            "partner_b_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_marriages_active_pair", "partner_a_id", "partner_b_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

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

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=STATUS_ACTIVE,
        server_default=text("'active'"),
    )

    mahr: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=constants.FAMILY_DEFAULT_MAHRIYEH,
        server_default=text(str(constants.FAMILY_DEFAULT_MAHRIYEH)),
    )
    relationship_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=constants.FAMILY_RELATIONSHIP_START_POINTS,
        server_default=text(str(constants.FAMILY_RELATIONSHIP_START_POINTS)),
    )

    cheating_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    cheater_a_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    cheater_b_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    last_relationship_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    last_cheat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    divorce_requested_by_player_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    divorce_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    children_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    married_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    dissolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
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
            f"<Marriage id={self.id} a={self.partner_a_id} b={self.partner_b_id} "
            f"status={self.status!r} mahr={self.mahr} points={self.relationship_points}>"
        )
