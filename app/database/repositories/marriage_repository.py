"""Repository for ``marriages`` + ``marriage_proposals`` (the couple graph).

Both tables are managed here because every marriage transition also settles
its pending proposals — keeping them in one repository means the invariant
"an accepted proposal always resolves inside the marriage transaction" cannot
be broken by forgetting a second update elsewhere.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.marriage import STATUS_ACTIVE, STATUS_DIVORCED, Marriage
from app.database.models.marriage_proposal import (
    STATUS_ACCEPTED,
    STATUS_PENDING,
    STATUS_REJECTED,
    MarriageProposal,
)


def _utc_now() -> datetime:
    """Naive-UTC now — the convention the DB layer uses (matches
    ``CURRENT_TIMESTAMP`` read back from SQLite)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ordered_pair(player_a: int, player_b: int) -> tuple[int, int]:
    """Canonical (smaller, larger) ordering — same convention as marriages."""
    return (player_a, player_b) if player_a < player_b else (player_b, player_a)


class MarriageRepository:
    """Database access for marriages and their proposals."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Marriages: reads ---------------------------------------------------

    async def get_active_for_player(self, player_id: int) -> Marriage | None:
        statement = (
            select(Marriage)
            .where(
                Marriage.status == STATUS_ACTIVE,
                (Marriage.partner_a_id == player_id)
                | (Marriage.partner_b_id == player_id),
            )
            .limit(1)
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def get_active_between(self, player_a: int, player_b: int) -> Marriage | None:
        low, high = ordered_pair(player_a, player_b)
        statement = select(Marriage).where(
            Marriage.status == STATUS_ACTIVE,
            Marriage.partner_a_id == low,
            Marriage.partner_b_id == high,
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def get_by_id(self, marriage_id: int) -> Marriage | None:
        return await self._session.get(Marriage, marriage_id)

    async def count_active(self) -> int:
        statement = select(Marriage.id).where(Marriage.status == STATUS_ACTIVE)
        return len((await self._session.execute(statement)).scalars().all())

    async def list_marriages_of(self, player_id: int) -> list[Marriage]:
        """All marriages of a player (active and dissolved, oldest first)."""
        statement = (
            select(Marriage)
            .where(
                (Marriage.partner_a_id == player_id)
                | (Marriage.partner_b_id == player_id)
            )
            .order_by(Marriage.id)
        )
        return list((await self._session.execute(statement)).scalars().all())

    # --- Marriages: writes ---------------------------------------------------

    async def create(
        self, *, player_a: int, player_b: int, mahr: int, married_at: datetime | None = None
    ) -> Marriage:
        low, high = ordered_pair(player_a, player_b)
        kwargs = {}
        if married_at is not None:
            kwargs["married_at"] = married_at
        marriage = Marriage(
            partner_a_id=low,
            partner_b_id=high,
            status=STATUS_ACTIVE,
            mahr=mahr,
            **kwargs,
        )
        self._session.add(marriage)
        await self._session.flush()
        return marriage

    async def set_relationship_points(self, marriage_id: int, points: int) -> None:
        await self._session.execute(
            update(Marriage)
            .where(Marriage.id == marriage_id)
            .values(relationship_points=points),
            execution_options={"synchronize_session": False},
        )

    async def touch_relationship(self, marriage_id: int, when: datetime) -> None:
        await self._session.execute(
            update(Marriage)
            .where(Marriage.id == marriage_id)
            .values(last_relationship_at=when),
            execution_options={"synchronize_session": False},
        )

    async def register_cheat(
        self,
        marriage: Marriage,
        *,
        when: datetime,
        points: int,
        discovered: bool,
        cheater_player_id: int,
    ) -> None:
        """Record a cheating attempt on an existing (loaded) marriage row.

        A *discovered* betrayal also counts up — in total and on the
        cheater's own side (``cheater_a_count`` / ``cheater_b_count``), which
        is what the Mahriyeh liability looks at on divorce. Counters live on
        the loaded instance; the service commits the session.
        """
        marriage.last_cheat_at = when
        marriage.relationship_points = points
        if discovered:
            marriage.cheating_count = marriage.cheating_count + 1
            if cheater_player_id == marriage.partner_a_id:
                marriage.cheater_a_count = marriage.cheater_a_count + 1
            else:
                marriage.cheater_b_count = marriage.cheater_b_count + 1

    async def request_divorce(
        self, marriage_id: int, *, requester_player_id: int, when: datetime
    ) -> None:
        await self._session.execute(
            update(Marriage)
            .where(Marriage.id == marriage_id)
            .values(divorce_requested_by_player_id=requester_player_id, divorce_requested_at=when),
            execution_options={"synchronize_session": False},
        )

    async def clear_divorce_request(self, marriage_id: int) -> None:
        await self._session.execute(
            update(Marriage)
            .where(Marriage.id == marriage_id)
            .values(divorce_requested_by_player_id=None, divorce_requested_at=None),
            execution_options={"synchronize_session": False},
        )

    async def finalize_divorce(self, marriage_id: int, *, when: datetime) -> None:
        """Mark the marriage as dissolved and clear the pending request."""
        await self._session.execute(
            update(Marriage)
            .where(Marriage.id == marriage_id)
            .values(
                status=STATUS_DIVORCED,
                dissolved_at=when,
                divorce_requested_by_player_id=None,
                divorce_requested_at=None,
            ),
            execution_options={"synchronize_session": False},
        )

    async def add_child(self, marriage_id: int) -> None:
        await self._session.execute(
            update(Marriage)
            .where(Marriage.id == marriage_id)
            .values(children_count=Marriage.children_count + 1),
            execution_options={"synchronize_session": False},
        )

    # --- Proposals: reads ---------------------------------------------------

    async def get_pending_for_receiver(self, player_id: int) -> MarriageProposal | None:
        statement = (
            select(MarriageProposal)
            .where(
                MarriageProposal.receiver_player_id == player_id,
                MarriageProposal.status == STATUS_PENDING,
            )
            .order_by(MarriageProposal.id.desc())
            .limit(1)
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def get_pending_between(
        self, player_a: int, player_b: int
    ) -> MarriageProposal | None:
        """A pending proposal in either direction (dedupe before creating)."""
        statement = (
            select(MarriageProposal)
            .where(
                MarriageProposal.status == STATUS_PENDING,
                (
                    (MarriageProposal.sender_player_id == player_a)
                    & (MarriageProposal.receiver_player_id == player_b)
                )
                | (
                    (MarriageProposal.sender_player_id == player_b)
                    & (MarriageProposal.receiver_player_id == player_a)
                ),
            )
            .order_by(MarriageProposal.id.desc())
            .limit(1)
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def get_pending_sent_by(self, player_id: int) -> list[MarriageProposal]:
        statement = select(MarriageProposal).where(
            MarriageProposal.sender_player_id == player_id,
            MarriageProposal.status == STATUS_PENDING,
        )
        return list((await self._session.execute(statement)).scalars().all())

    # --- Proposals: writes ---------------------------------------------------

    async def create_proposal(
        self,
        *,
        sender_player_id: int,
        receiver_player_id: int,
        mahr: int,
        note: str = "",
        expires_at: datetime | None = None,
        proposal_message_id: int | None = None,
    ) -> MarriageProposal:
        proposal = MarriageProposal(
            sender_player_id=sender_player_id,
            receiver_player_id=receiver_player_id,
            status=STATUS_PENDING,
            mahr=mahr,
            note=note,
            expires_at=expires_at,
            proposal_message_id=proposal_message_id,
        )
        self._session.add(proposal)
        await self._session.flush()
        return proposal

    async def supersede_pending(self, receiver_player_id: int, *, except_id: int | None = None) -> None:
        """Cancel older pending proposals aimed at ``receiver_player_id``."""
        conditions = [
            MarriageProposal.receiver_player_id == receiver_player_id,
            MarriageProposal.status == STATUS_PENDING,
        ]
        if except_id is not None:
            conditions.append(MarriageProposal.id != except_id)
        await self._session.execute(
            update(MarriageProposal)
            .where(*conditions)
            .values(status="cancelled", answered_at=_utc_now()),
            execution_options={"synchronize_session": False},
        )

    async def resolve_proposal(
        self, proposal_id: int, *, status: str, answer_message_id: int | None = None
    ) -> None:
        values: dict[str, object] = {"status": status, "answered_at": _utc_now()}
        if answer_message_id is not None:
            values["answer_message_id"] = answer_message_id
        await self._session.execute(
            update(MarriageProposal)
            .where(MarriageProposal.id == proposal_id)
            .values(**values),
            execution_options={"synchronize_session": False},
        )

    # Aliases used by the service (readability at call sites).
    async def accept(self, proposal_id: int) -> None:
        await self.resolve_proposal(proposal_id, status=STATUS_ACCEPTED)

    async def reject(self, proposal_id: int) -> None:
        await self.resolve_proposal(proposal_id, status=STATUS_REJECTED)
