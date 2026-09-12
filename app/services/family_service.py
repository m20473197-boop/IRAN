"""Marriage & Family service — the transaction boundary of the system.

Use cases (all driven by Persian text commands — the system adds no
buttons and touches no menus):

* «ازدواج»  — a reply-based marriage proposal with an optional Mahriyeh.
* «قبول» / «رد» — the target accepts (marriage record created, both players
  linked as spouses, marriage date saved, profiles updated) or rejects it.
* «طلاق» — files a divorce request the spouse can forgive («بخشش»); a second
  «طلاق» — by either side — finalizes it. The Mahriyeh moves through the
  exact atomic wallet primitives of the Wallet system, inside the same DB
  transaction as the divorce record, so the ledger can never drift. A payer
  who cannot afford the Mahriyeh is refused with the required amount.
* «خیانت» — a secret attempt with independent success/discovery rolls. When
  discovered: relationship damage, social penalties (fine + reputation XP
  through the existing services) and a real divorce possibility — once the
  relationship is at the floor the betrayed spouse's «طلاق» shifts the
  Mahriyeh onto the proven cheater.
* «رابطه» — a relationship event for married couples with a pregnancy roll;
  a birth creates the child row, bumps every family counter and grants XP
  explicitly through ``LevelService``.

Randomness (cheat rolls, pregnancy, baby names/genders) flows through an
injectable ``RandomSource`` (see ``app/game/family/family.py``) so tests can
script exact outcomes; production uses the stdlib module.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import constants
from app.database.models.child import GENDER_BOY, GENDER_GIRL
from app.database.models.family_history import (
    EVENT_BIRTH,
    EVENT_CHEAT,
    EVENT_CHEAT_DISCOVERED,
    EVENT_DIVORCE,
    EVENT_DIVORCE_FORGIVEN,
    EVENT_DIVORCE_REQUEST,
    EVENT_FORGIVENESS,
    EVENT_MARRIAGE,
    EVENT_PROPOSAL,
    EVENT_PROPOSAL_REJECTED,
    EVENT_RELATIONSHIP,
)
from app.database.models.marriage import Marriage
from app.database.models.marriage_proposal import (
    STATUS_ACCEPTED,
    STATUS_CANCELLED,
    STATUS_EXPIRED,
    STATUS_PENDING,
    STATUS_REJECTED,
    MarriageProposal,
)
from app.database.repositories.child_repository import ChildRepository
from app.database.repositories.divorce_record_repository import (
    DivorceRecordRepository,
)
from app.database.repositories.family_history_repository import (
    FamilyHistoryRepository,
)
from app.database.repositories.marriage_repository import MarriageRepository
from app.database.repositories.player_repository import PlayerRepository
from app.database.repositories.relationship_event_repository import (
    RelationshipEventRepository,
)
from app.game.family import family as family_domain
from app.game.family.dto import (
    DIVORCED,
    MARRIED,
    SINGLE,
    CheatResult,
    ChildData,
    DivorceRecordData,
    DivorceRequestResult,
    DivorceResult,
    FamilyHistoryEntry,
    FamilyInfoData,
    FamilySnapshot,
    ForgiveResult,
    MarriageResult,
    ProposalData,
    ProposalResult,
    RelationshipResult,
)
from app.game.family.family import RandomSource, random_module
from app.game.shared.errors import DomainError, PlayerNotFoundError

logger = logging.getLogger(__name__)

# ``players.marriage_status`` values (kept importable for other layers).
STATUS_SINGLE = SINGLE
STATUS_MARRIED = MARRIED
STATUS_DIVORCED = DIVORCED


# --- Domain errors ------------------------------------------------------------


class AlreadyMarriedError(DomainError):
    """A married player cannot marry another person.

    ``married_side`` tells which side is married (``"sender"`` = the
    proposer, ``"receiver"`` = the target) so the handler can phrase the
    refusal correctly («این کاربر متأهل است»).
    """

    def __init__(self, message: str = "player is already married", *, married_side: str = "sender"):
        super().__init__(message)
        self.married_side = married_side


class NotMarriedError(DomainError):
    """The player has no active marriage for this operation."""


class SelfMarriageError(DomainError):
    """A player cannot marry themselves."""


class LevelTooLowError(DomainError):
    """A player is below ``FAMILY_MIN_LEVEL_TO_MARRY``."""

    def __init__(self, message: str = "level too low", *, player_display_name: str = "", level: int = 0):
        super().__init__(message)
        self.player_display_name = player_display_name
        self.level = level


class NoPendingProposalError(DomainError):
    """There is no open marriage proposal to answer."""


class ProposalBusyError(DomainError):
    """A proposal involving these two players is already pending."""


class NotSpouseError(DomainError):
    """The replied-to player is not this player's spouse."""


class CheatingTooSoonError(DomainError):
    """The secret-attempt cooldown is still active."""

    def __init__(self, message: str = "cooldown", *, wait_seconds: int = 0):
        super().__init__(message)
        self.wait_seconds = wait_seconds


class RelationshipTooSoonError(DomainError):
    """The relationship cooldown is still active."""

    def __init__(self, message: str = "cooldown", *, wait_seconds: int = 0):
        super().__init__(message)
        self.wait_seconds = wait_seconds


class NoDivorcePendingError(DomainError):
    """Nobody filed a divorce, so there is nothing to forgive."""


class CannotForgiveOwnDivorceError(DomainError):
    """You cannot forgive your own divorce request."""


class InsufficientMahriyehError(DomainError):
    """The divorce is blocked until the Mahriyeh can be paid.

    Carries the numbers so the handler can show the required amount.
    """

    def __init__(self, message: str = "not enough money for the Mahriyeh", *, mahr: int = 0, balance: int = 0):
        super().__init__(message)
        self.mahr = mahr
        self.balance = balance
        self.shortfall = max(0, mahr - balance)


# --- Helpers -------------------------------------------------------------------


def _utc_now() -> datetime:
    """Naive-UTC now — the convention the DB stores ``func.now()`` in."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_naive_utc(value: datetime) -> datetime:
    """Any DB datetime → naive UTC, so subtractions never mix offset-aware."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _age_years(birth: datetime, now: datetime) -> int:
    """Whole calendar years since ``birth`` (never negative)."""
    years = now.year - birth.year
    if (now.month, now.day) < (birth.month, birth.day):
        years -= 1
    return max(0, years)


class FamilyService:
    """All marriage / divorce / cheating / relationship / child use cases."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        level_service=None,
        rng: RandomSource | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._level_service = level_service
        self._rng = rng or random_module

    def set_rng(self, rng: RandomSource) -> None:
        """Override the random source (tests script exact outcomes)."""
        self._rng = rng

    # === Proposals («ازدواج» / «رد») ==========================================

    async def create_proposal(
        self,
        *,
        sender_player_id: int,
        receiver_player_id: int,
        mahr: int | None = None,
        note: str = "",
        proposal_message_id: int | None = None,
    ) -> ProposalResult:
        """Register a marriage request from sender to receiver.

        Raises:
            PlayerNotFoundError: Either player is not registered.
            SelfMarriageError: A player proposed to themselves.
            LevelTooLowError: Either side is below ``FAMILY_MIN_LEVEL_TO_MARRY``.
            AlreadyMarriedError: Either side is married (``married_side``
                says who — the handler phrases «target married» vs «you are
                married» from it).
            ProposalBusyError: A pending proposal between them is open.
        """
        clean_mahr = family_domain.sanity_check_mahr(
            constants.FAMILY_DEFAULT_MAHRIYEH if mahr is None else mahr
        )

        async with self._session_factory() as session:
            players = PlayerRepository(session)
            marriages = MarriageRepository(session)

            sender = await players.get_by_id(sender_player_id)
            receiver = await players.get_by_id(receiver_player_id)
            if sender is None:
                raise PlayerNotFoundError(f"player_id={sender_player_id} not found")
            if receiver is None:
                raise PlayerNotFoundError(f"player_id={receiver_player_id} not found")
            if sender.id == receiver.id:
                raise SelfMarriageError("a player cannot marry themselves")

            # The level gate is on the PROPOSER only — being asked in
            # marriage must never fail because the target just joined.
            if sender.level < constants.FAMILY_MIN_LEVEL_TO_MARRY:
                raise LevelTooLowError(
                    f"{sender.display_name} is level {sender.level}",
                    player_display_name=sender.display_name,
                    level=sender.level,
                )
            for player, side in ((sender, "sender"), (receiver, "receiver")):
                if await marriages.get_active_for_player(player.id) is not None:
                    raise AlreadyMarriedError(
                        f"player_id={player.id} is already married", married_side=side
                    )

            now = _utc_now()
            await self._expire_pending_proposals(session, now=now)
            if await marriages.get_pending_between(sender.id, receiver.id) is not None:
                raise ProposalBusyError("proposal already pending between these players")

            proposal = await marriages.create_proposal(
                sender_player_id=sender.id,
                receiver_player_id=receiver.id,
                mahr=clean_mahr,
                note=(note or "").strip()[:140],
                expires_at=now
                + timedelta(seconds=constants.FAMILY_PROPOSAL_EXPIRY_SECONDS),
                proposal_message_id=proposal_message_id,
            )
            FamilyHistoryRepository(session).add(
                player_id=sender.id,
                event_type=EVENT_PROPOSAL,
                details=f"درخواست ازدواج با {receiver.display_name} — مهریه {clean_mahr:,}",
            )
            await session.commit()

            logger.info(
                "Marriage proposal %s created: player %s -> %s (mahr=%s)",
                proposal.id,
                sender.id,
                receiver.id,
                clean_mahr,
            )
            return ProposalResult(
                proposal=self._to_proposal_dto(proposal),
                target_telegram_user_id=receiver.telegram_user_id,
                target_display_name=receiver.display_name,
                proposer_display_name=sender.display_name,
            )

    async def get_pending_proposal_for(self, player_id: int) -> ProposalData | None:
        """The live pending proposal addressed to ``player_id`` (None if none)."""
        async with self._session_factory() as session:
            now = _utc_now()
            await self._expire_pending_proposals(session, now=now)
            proposal = await MarriageRepository(session).get_pending_for_receiver(player_id)
            dto = self._to_proposal_dto(proposal) if proposal is not None else None
            await session.commit()  # persist any expiry sweep done above
            return dto

    async def accept_pending_proposal(
        self, receiver_player_id: int, *, answer_message_id: int | None = None
    ) -> MarriageResult:
        """«قبول» — the receiver accepts the pending proposal: they marry.

        Raises:
            NoPendingProposalError: Nothing open (or it expired).
            AlreadyMarriedError: Either side is married (also raised when a
                concurrent accept hits the DB-level monogamy invariant).
        """
        async with self._session_factory() as session:
            players = PlayerRepository(session)
            marriages = MarriageRepository(session)

            now = _utc_now()
            await self._expire_pending_proposals(session, now=now)
            proposal = await marriages.get_pending_for_receiver(receiver_player_id)
            if proposal is None:
                raise NoPendingProposalError("no pending marriage proposal for this player")

            sender = await players.get_by_id(proposal.sender_player_id)
            receiver = await players.get_by_id(receiver_player_id)
            if sender is None or receiver is None:
                raise PlayerNotFoundError("a proposer no longer exists")

            for player, side in ((sender, "sender"), (receiver, "receiver")):
                if await marriages.get_active_for_player(player.id) is not None:
                    await marriages.resolve_proposal(
                        proposal.id, status=STATUS_REJECTED, answer_message_id=answer_message_id
                    )
                    await session.commit()
                    raise AlreadyMarriedError(
                        f"player_id={player.id} is already married", married_side=side
                    )

            try:
                marriage = await marriages.create(
                    player_a=sender.id,
                    player_b=receiver.id,
                    mahr=proposal.mahr,
                    married_at=now,
                )
            except IntegrityError:
                # Lost a race against a concurrent marriage for one of the
                # two players — the partial unique index is the guarantee.
                await session.rollback()
                logger.warning("Concurrent marriage accept rejected for players %s/%s", sender.id, receiver.id)
                raise AlreadyMarriedError("one of the players married in the meantime") from None

            await marriages.resolve_proposal(
                proposal.id, status=STATUS_ACCEPTED, answer_message_id=answer_message_id
            )
            # Cancel any other open proposal either side still holds —
            # incoming ones (supersede) and outgoing ones (reject).
            for busy_player in (sender.id, receiver.id):
                await marriages.supersede_pending(busy_player)
                for outgoing in await marriages.get_pending_sent_by(busy_player):
                    await marriages.resolve_proposal(outgoing.id, status=STATUS_REJECTED)

            await players.set_family_state(
                sender.id,
                marriage_status=STATUS_MARRIED,
                spouse_player_id=receiver.id,
                married_at=marriage.married_at,
            )
            await players.set_family_state(
                receiver.id,
                marriage_status=STATUS_MARRIED,
                spouse_player_id=sender.id,
                married_at=marriage.married_at,
            )
            history = FamilyHistoryRepository(session)
            history.add(
                player_id=sender.id,
                event_type=EVENT_MARRIAGE,
                marriage_id=marriage.id,
                details=f"ازدواج با {receiver.display_name} — مهریه {marriage.mahr:,}",
            )
            history.add(
                player_id=receiver.id,
                event_type=EVENT_MARRIAGE,
                marriage_id=marriage.id,
                details=f"ازدواج با {sender.display_name} — مهریه {marriage.mahr:,}",
            )
            await session.commit()

            result = MarriageResult(
                marriage_id=marriage.id,
                partner_a_id=marriage.partner_a_id,
                partner_b_id=marriage.partner_b_id,
                mahr=marriage.mahr,
                married_at=marriage.married_at,
                relationship_points=marriage.relationship_points,
                proposer_display_name=sender.display_name,
                target_display_name=receiver.display_name,
                proposer_telegram_user_id=sender.telegram_user_id,
                target_telegram_user_id=receiver.telegram_user_id,
                xp_granted=self._level_service is not None,
            )

        # XP for the wedding — always explicit, through the existing
        # LevelService (audited history, level-up detection included).
        await self._grant_xp(
            result.partner_a_id,
            constants.FAMILY_XP_FOR_MARRIAGE,
            reason=constants.FAMILY_XP_FOR_MARRIAGE_REASON,
        )
        await self._grant_xp(
            result.partner_b_id,
            constants.FAMILY_XP_FOR_MARRIAGE,
            reason=constants.FAMILY_XP_FOR_MARRIAGE_REASON,
        )

        logger.info(
            "Marriage %s: players %s + %s (mahr=%s)",
            result.marriage_id,
            result.partner_a_id,
            result.partner_b_id,
            result.mahr,
        )
        return result

    async def reject_pending_proposal(
        self, receiver_player_id: int, *, answer_message_id: int | None = None
    ) -> ProposalData:
        """«رد» — the receiver declines the open proposal.

        Raises:
            NoPendingProposalError: Nothing open to reject.
        """
        async with self._session_factory() as session:
            players = PlayerRepository(session)
            marriages = MarriageRepository(session)

            now = _utc_now()
            await self._expire_pending_proposals(session, now=now)
            proposal = await marriages.get_pending_for_receiver(receiver_player_id)
            if proposal is None:
                raise NoPendingProposalError("no pending marriage proposal for this player")

            await marriages.resolve_proposal(
                proposal.id, status=STATUS_REJECTED, answer_message_id=answer_message_id
            )
            sender = await players.get_by_id(proposal.sender_player_id)
            receiver = await players.get_by_id(receiver_player_id)
            if sender is not None:
                FamilyHistoryRepository(session).add(
                    player_id=sender.id,
                    event_type=EVENT_PROPOSAL_REJECTED,
                    details=f"درخواست ازدوالت با {receiver.display_name if receiver else '?'} رد شد",
                )
            await session.commit()

            logger.info("Proposal %s rejected by player %s", proposal.id, receiver_player_id)
            return self._to_proposal_dto(proposal)

    async def cancel_open_proposals(self, sender_player_id: int) -> int:
        """Withdraw every open proposal the sender still has; returns count."""
        async with self._session_factory() as session:
            marriages = MarriageRepository(session)
            rows = await marriages.get_pending_sent_by(sender_player_id)
            for row in rows:
                await marriages.resolve_proposal(row.id, status=STATUS_CANCELLED)
            await session.commit()
            return len(rows)

    # === Relationship («رابطه») ===============================================

    async def relationship_event(
        self, initiator_player_id: int, *, partner_hint_player_id: int | None = None
    ) -> RelationshipResult:
        """«رابطه» — one relationship event of a married couple + pregnancy roll.

        ``partner_hint_player_id`` is the player whose message was replied
        to; when given it must be the spouse (only married couples share a
        relationship event).

        Raises:
            NotMarriedError: The initiator is not married.
            NotSpouseError: The replied-to player is not the spouse.
            RelationshipTooSoonError: Cooldown still running.
        """
        async with self._session_factory() as session:
            players = PlayerRepository(session)
            marriages = MarriageRepository(session)

            marriage = await marriages.get_active_for_player(initiator_player_id)
            if marriage is None:
                raise NotMarriedError("only married players can have a relationship event")

            spouse_id = marriage.partner_b_id if marriage.partner_a_id == initiator_player_id else marriage.partner_a_id
            if partner_hint_player_id is not None and partner_hint_player_id != spouse_id:
                raise NotSpouseError("the replied-to player is not your spouse")

            now = _utc_now()
            wait = self._cooldown_wait(marriage.last_relationship_at, now, constants.FAMILY_RELATIONSHIP_COOLDOWN_SECONDS)
            if wait > 0:
                raise RelationshipTooSoonError("relationship cooldown", wait_seconds=wait)

            spouse = await players.get_by_id(spouse_id)
            if spouse is None:  # pragma: no cover — FK cascade makes this impossible
                raise PlayerNotFoundError(f"spouse player_id={spouse_id} not found")

            pregnant, roll = family_domain.roll_pregnancy(self._rng)
            points_after = family_domain.after_relationship_event(marriage.relationship_points)

            events = RelationshipEventRepository(session)
            event = await events.create(
                marriage_id=marriage.id,
                initiator_player_id=initiator_player_id,
                partner_player_id=spouse_id,
                satisfaction=points_after,
                pregnancy_chance_percent=constants.FAMILY_PREGNANCY_CHANCE,
                rolled_percent=roll,
                pregnant=pregnant,
                note="رابطه زناشویی",
            )
            marriage.relationship_points = points_after
            marriage.last_relationship_at = now

            child: ChildData | None = None
            history = FamilyHistoryRepository(session)
            if pregnant:
                child = await self._create_child(session, marriage=marriage, event_id=event.id, now=now)
                history.add(
                    player_id=marriage.partner_a_id,
                    event_type=EVENT_BIRTH,
                    marriage_id=marriage.id,
                    details=f"فرزندت {child.name} به دنیا اومد",
                )
                history.add(
                    player_id=marriage.partner_b_id,
                    event_type=EVENT_BIRTH,
                    marriage_id=marriage.id,
                    details=f"فرزندت {child.name} به دنیا اومد",
                )
            else:
                history.add(
                    player_id=initiator_player_id,
                    event_type=EVENT_RELATIONSHIP,
                    marriage_id=marriage.id,
                    details=f"رابطه زناشویی — بارداری رخ نداد (شانس {constants.FAMILY_PREGNANCY_CHANCE}٪)",
                )
            await session.commit()

            result = RelationshipResult(
                event_id=event.id,
                marriage_id=marriage.id,
                satisfaction=points_after,
                pregnancy_chance_percent=constants.FAMILY_PREGNANCY_CHANCE,
                pregnant=pregnant,
                child=child,
                partner_player_id=spouse.id,
                partner_telegram_user_id=spouse.telegram_user_id,
                partner_display_name=spouse.display_name,
            )

        if child is not None:
            # Both parents are rewarded for the birth — through LevelService.
            await self._grant_xp(
                initiator_player_id,
                constants.FAMILY_XP_FOR_CHILD_BIRTH,
                reason=constants.FAMILY_XP_FOR_CHILD_BIRTH_REASON,
            )
            await self._grant_xp(
                result.partner_player_id,
                constants.FAMILY_XP_FOR_CHILD_BIRTH,
                reason=constants.FAMILY_XP_FOR_CHILD_BIRTH_REASON,
            )

        logger.info(
            "Relationship event %s (marriage %s, pregnant=%s)",
            result.event_id,
            result.marriage_id,
            result.pregnant,
        )
        return result

    async def _create_child(
        self,
        session: AsyncSession,
        *,
        marriage: Marriage,
        event_id: int,
        now: datetime,
    ) -> ChildData:
        """Create the child row and update every family counter (one tx)."""
        is_boy = int(self._rng.randint(0, 1)) == 0
        name = str(
            self._rng.choice(
                list(constants.FAMILY_BOY_NAMES if is_boy else constants.FAMILY_GIRL_NAMES)
            )
        )
        child = await ChildRepository(session).create(
            marriage_id=marriage.id,
            father_player_id=marriage.partner_a_id,
            mother_player_id=marriage.partner_b_id,
            name=name,
            gender=GENDER_BOY if is_boy else GENDER_GIRL,
            birth_date=now,
            relationship_event_id=event_id,
        )
        await RelationshipEventRepository(session).mark_birth(event_id)
        await MarriageRepository(session).add_child(marriage.id)
        players = PlayerRepository(session)
        await players.add_children(marriage.partner_a_id)
        await players.add_children(marriage.partner_b_id)
        logger.info(
            "Child %s (%s) born to players %s + %s",
            child.id,
            name,
            marriage.partner_a_id,
            marriage.partner_b_id,
        )
        return ChildData(
            id=child.id,
            marriage_id=child.marriage_id,
            father_player_id=child.father_player_id,
            mother_player_id=child.mother_player_id,
            name=child.name,
            gender=child.gender,
            birth_date=child.birth_date,
            growth_stage=child.growth_stage,
            education_level=child.education_level,
            expense_total=child.expense_total,
        )

    # === Cheating («خیانت») =====================================================

    async def cheat_attempt(self, player_id: int) -> CheatResult:
        """One secret affair attempt: success roll + discovery roll.

        The result is only ever shown to the cheater. A *discovered* affair:

        * burns relationship points (consequence: damage),
        * applies social penalties — a wallet fine (capped by the balance)
          and a reputation XP loss through the existing LevelService,
        * identifies the spouse so the handler can notify them privately,
        * and — once the relationship hits the floor — makes divorce real:
          the betrayed spouse's «طلاق» will make the cheater pay the
          Mahriyeh (see ``divorce_payer_is_cheater``).

        Raises:
            NotMarriedError: Only married players can use this.
            CheatingTooSoonError: Cooldown still running.
        """
        async with self._session_factory() as session:
            players = PlayerRepository(session)
            marriages = MarriageRepository(session)

            marriage = await marriages.get_active_for_player(player_id)
            if marriage is None:
                raise NotMarriedError("only married players can cheat")

            now = _utc_now()
            wait = self._cooldown_wait(marriage.last_cheat_at, now, constants.FAMILY_CHEAT_COOLDOWN_SECONDS)
            if wait > 0:
                raise CheatingTooSoonError("cheat cooldown", wait_seconds=wait)

            succeeded, discovered, success_roll, discovery_roll = family_domain.roll_cheat_attempt(self._rng)

            spouse_id = marriage.partner_b_id if marriage.partner_a_id == player_id else marriage.partner_a_id
            spouse = await players.get_by_id(spouse_id)
            points_before = marriage.relationship_points
            points_after = points_before
            penalty_money = 0
            penalty_xp = 0

            if discovered:
                points_after = family_domain.after_cheat_discovered(points_before)
                balance = await players.get_money(player_id) or 0
                penalty_money = min(balance, constants.FAMILY_CHEAT_SOCIAL_FINE)
                if penalty_money > 0 and not await players.remove_money_if_enough(player_id, penalty_money):
                    penalty_money = 0  # concurrent spend — fine skipped, never overdraft
                player = await players.get_by_id(player_id)
                if player is not None and self._level_service is not None:
                    penalty_xp = min(player.xp, constants.FAMILY_CHEAT_XP_LOSS)

            marriage.relationship_points = points_after
            await marriages.register_cheat(
                marriage,
                when=now,
                points=points_after,
                discovered=discovered,
                cheater_player_id=player_id,
            )

            history = FamilyHistoryRepository(session)
            if discovered:
                log = (
                    f"رابطه مخفی ({success_roll}/{discovery_roll}) — لو رفت؛ "
                    f"جریمه {penalty_money:,}، XP −{penalty_xp:,}، امتیاز رابطه {points_after}"
                )
                history.add(
                    player_id=player_id,
                    event_type=EVENT_CHEAT_DISCOVERED,
                    marriage_id=marriage.id,
                    details=log,
                )
                if spouse is not None:
                    history.add(
                        player_id=spouse.id,
                        event_type=EVENT_CHEAT_DISCOVERED,
                        marriage_id=marriage.id,
                        details=f"خیانت {player.display_name if player else 'همسرت'} لو رفت",
                    )
            else:
                history.add(
                    player_id=player_id,
                    event_type=EVENT_CHEAT,
                    marriage_id=marriage.id,
                    details=(
                        f"رابطه مخفی ({success_roll}/{discovery_roll}) — لو نرفت"
                        if succeeded
                        else "تلاش برای رابطه مخفی به جایی نرسید"
                    ),
                )

            divorce_possible = discovered and points_after <= constants.FAMILY_RELATIONSHIP_MIN_POINTS
            await session.commit()

            result = CheatResult(
                succeeded=succeeded,
                discovered=discovered,
                success_roll=success_roll,
                discovery_roll=discovery_roll,
                relationship_points_before=points_before,
                relationship_points_after=points_after,
                penalty_money=penalty_money,
                penalty_xp=penalty_xp,
                divorce_possible=divorce_possible,
                marriage_id=marriage.id,
                cheater_player_id=player_id,
                spouse_player_id=spouse.id if spouse else None,
                spouse_telegram_user_id=spouse.telegram_user_id if spouse else None,
                spouse_display_name=spouse.display_name if spouse else None,
                cheater_display_name=(
                    (await players.get_by_id(player_id)).display_name
                ),
            )

        if penalty_xp > 0:
            try:
                # Reputation damage — through the existing XP system so it
                # lands in the transaction history like every other change.
                await self._level_service.remove_xp(  # type: ignore[union-attr]
                    player_id, penalty_xp, reason="خیانت لو رفته"
                )
            except Exception:  # noqa: BLE001 — the XP penalty never blocks the flow
                logger.warning("Could not apply cheat XP penalty to %s", player_id, exc_info=True)

        logger.info(
            "Cheat attempt by player %s: succeeded=%s discovered=%s",
            player_id,
            succeeded,
            discovered,
        )
        return result

    # === Divorce («طلاق» / «بخشش») =============================================

    async def request_or_finalize_divorce(self, player_id: int) -> DivorceRequestResult | DivorceResult:
        """«طلاق» — file a divorce request, or finalize a pending one.

        First use: the spouse is notified and gets the forgiveness window
        (they may send «بخشش»). A second «طلاق» — by *either* spouse —
        finalizes the divorce (the mutual decision) and the Mahriyeh is
        settled through the wallet.

        Returns:
            ``DivorceRequestResult`` when only the request was filed,
            ``DivorceResult`` when the marriage was dissolved.
        """
        async with self._session_factory() as session:
            players = PlayerRepository(session)
            marriages = MarriageRepository(session)

            marriage = await marriages.get_active_for_player(player_id)
            if marriage is None:
                raise NotMarriedError("you are not married")
            spouse_id = marriage.partner_b_id if marriage.partner_a_id == player_id else marriage.partner_a_id
            spouse = await players.get_by_id(spouse_id)
            if spouse is None:  # pragma: no cover
                raise PlayerNotFoundError(f"spouse player_id={spouse_id} not found")

            requester = marriage.divorce_requested_by_player_id
            if requester is not None:
                # A request is already open → this use ends the marriage,
                # whoever types it (mutual consent or stubbornness).
                return await self._finalize_divorce(session, marriage, player_id)

            now = _utc_now()
            await marriages.request_divorce(marriage.id, requester_player_id=player_id, when=now)
            history = FamilyHistoryRepository(session)
            history.add(
                player_id=player_id,
                event_type=EVENT_DIVORCE_REQUEST,
                marriage_id=marriage.id,
                details=f"درخواست طلاق از {spouse.display_name}",
            )
            history.add(
                player_id=spouse.id,
                event_type=EVENT_DIVORCE_REQUEST,
                marriage_id=marriage.id,
                details=f"{(await players.get_by_id(player_id)).display_name} درخواست طلاق داده — «بخشش» برای بازگشت",
            )
            await session.commit()

            logger.info("Divorce requested by player %s in marriage %s", player_id, marriage.id)
            return DivorceRequestResult(
                marriage_id=marriage.id,
                requester_player_id=player_id,
                expires_at=now + timedelta(seconds=constants.FAMILY_DIVORCE_COOLDOWN_SECONDS),
                final=False,
                mahr_required=marriage.mahr,
                spouse_telegram_user_id=spouse.telegram_user_id,
                spouse_display_name=spouse.display_name,
            )

    async def finalize_divorce(self, player_id: int) -> DivorceResult:
        """Force-finalize the divorce (no forgiveness window).

        Kept for admins/tests; the «طلاق» text flow uses
        :meth:`request_or_finalize_divorce`.
        """
        async with self._session_factory() as session:
            marriages = MarriageRepository(session)
            marriage = await marriages.get_active_for_player(player_id)
            if marriage is None:
                raise NotMarriedError("you are not married")
            return await self._finalize_divorce(session, marriage, player_id)

    async def _finalize_divorce(
        self, session: AsyncSession, marriage: Marriage, initiator_player_id: int
    ) -> DivorceResult:
        """Dissolve a marriage and settle the Mahriyeh — one transaction.

        Mahriyeh liability: the initiator pays. Exception (the "divorce
        possibility" consequence of cheating): when the *betrayed* spouse —
        who was never caught themselves — files while the relationship is at
        the floor, the proven cheater pays instead; if the cheater cannot
        cover it, what they have moves and the rest is recorded as an unpaid
        debt (a divorce is never blocked by an unpayable penalty from the
        other side — but an initiator who cannot pay is refused, see
        ``InsufficientMahriyehError``).
        """
        players = PlayerRepository(session)
        marriages = MarriageRepository(session)

        other_id = marriage.partner_b_id if marriage.partner_a_id == initiator_player_id else marriage.partner_a_id
        other = await players.get_by_id(other_id)
        if other is None:  # pragma: no cover
            raise PlayerNotFoundError(f"spouse player_id={other_id} not found")
        initiator = await players.get_by_id(initiator_player_id)
        assert initiator is not None  # marriage existence guarantees it

        initiator_caught = (
            marriage.cheater_a_count
            if initiator_player_id == marriage.partner_a_id
            else marriage.cheater_b_count
        )
        other_caught = (
            marriage.cheater_b_count
            if initiator_player_id == marriage.partner_a_id
            else marriage.cheater_a_count
        )
        cheater_pays = family_domain.divorce_payer_is_cheater(
            initiator_player_id=initiator_player_id,
            other_player_id=other_id,
            initiator_caught_count=initiator_caught,
            other_caught_count=other_caught,
            relationship_points=marriage.relationship_points,
            mahr=marriage.mahr,
        )
        payer_id, payee_id = (other_id, initiator_player_id) if cheater_pays else (initiator_player_id, other_id)

        mahr = marriage.mahr
        paid = 0
        if mahr > 0:
            payer_balance = await players.get_money(payer_id) or 0
            if payer_id == initiator_player_id:
                if not await players.remove_money_if_enough(payer_id, mahr):
                    # The requirement: prevent the divorce, show the amount.
                    balance = await players.get_money(payer_id) or 0
                    await session.rollback()
                    raise InsufficientMahriyehError(
                        f"player {payer_id} cannot pay mahr {mahr} (balance {balance})",
                        mahr=mahr,
                        balance=balance,
                    )
                await players.add_money(payee_id, mahr)
                paid = mahr
            else:
                # The cheater pays (enforced as far as their wallet allows;
                # the shortfall is recorded as debt, never silently waived).
                if payer_balance > 0:
                    transfer = min(payer_balance, mahr)
                    if await players.remove_money_if_enough(payer_id, transfer):
                        await players.add_money(payee_id, transfer)
                        paid = transfer
        unpaid = mahr - paid

        now = _utc_now()
        await marriages.finalize_divorce(marriage.id, when=now)
        await players.set_family_state(
            initiator_player_id,
            marriage_status=STATUS_DIVORCED,
            spouse_player_id=None,
            married_at=None,
        )
        await players.set_family_state(
            other_id,
            marriage_status=STATUS_DIVORCED,
            spouse_player_id=None,
            married_at=None,
        )

        record = await DivorceRecordRepository(session).create(
            marriage_id=marriage.id,
            initiator_player_id=initiator_player_id,
            partner_a_id=marriage.partner_a_id,
            partner_b_id=marriage.partner_b_id,
            mahr=mahr,
            mahr_payer_player_id=payer_id,
            mahr_payee_player_id=payee_id,
            paid_amount=paid,
            unpaid_debt=unpaid,
            reason="cheating_discovered" if cheater_pays else "divorced",
        )

        history = FamilyHistoryRepository(session)
        history.add(
            player_id=initiator_player_id,
            event_type=EVENT_DIVORCE,
            marriage_id=marriage.id,
            details=f"طلاق قطعی از {other.display_name} — مهریه پرداختی {paid:,}",
        )
        history.add(
            player_id=other_id,
            event_type=EVENT_DIVORCE,
            marriage_id=marriage.id,
            details=f"طلاق قطعی با {initiator.display_name} — مهریه دریافتی {paid:,}",
        )
        await session.commit()

        logger.info(
            "Divorce %s finalized: marriage %s (mahr paid=%s unpaid=%s payer=%s)",
            record.id,
            marriage.id,
            paid,
            unpaid,
            payer_id,
        )
        return DivorceResult(
            marriage_id=marriage.id,
            divorce_record_id=record.id,
            initiator_player_id=initiator_player_id,
            other_player_id=other_id,
            mahr=mahr,
            payer_player_id=payer_id,
            payee_player_id=payee_id,
            paid_amount=paid,
            unpaid_debt=unpaid,
            mahr_waived=mahr == 0,
            cheater_liable=cheater_pays,
            initiator_telegram_user_id=initiator.telegram_user_id,
            other_telegram_user_id=other.telegram_user_id,
            initiator_display_name=initiator.display_name,
            other_display_name=other.display_name,
        )

    async def forgive_divorce(self, player_id: int) -> ForgiveResult:
        """«بخشش» — the requested spouse forgives; the divorce is off.

        Raises:
            NotMarriedError: Not married.
            NoDivorcePendingError: No request is open.
            CannotForgiveOwnDivorceError: The pending request is *yours*.
        """
        async with self._session_factory() as session:
            players = PlayerRepository(session)
            marriages = MarriageRepository(session)

            marriage = await marriages.get_active_for_player(player_id)
            if marriage is None:
                raise NotMarriedError("you are not married")
            requester = marriage.divorce_requested_by_player_id
            if requester is None:
                raise NoDivorcePendingError("no divorce request is pending")
            if requester == player_id:
                raise CannotForgiveOwnDivorceError("you cannot forgive your own divorce request")

            points_before = marriage.relationship_points
            points_after = family_domain.after_forgiveness(points_before)
            await marriages.clear_divorce_request(marriage.id)
            marriage.relationship_points = points_after

            requester_player = await players.get_by_id(requester)
            history = FamilyHistoryRepository(session)
            history.add(
                player_id=player_id,
                event_type=EVENT_FORGIVENESS,
                marriage_id=marriage.id,
                details="بخشش — درخواست طلاق لغو شد",
            )
            history.add(
                player_id=requester,
                event_type=EVENT_DIVORCE_FORGIVEN,
                marriage_id=marriage.id,
                details="همسرت بخشیدت — طلاق لغو شد",
            )
            await session.commit()

            logger.info("Divorce in marriage %s forgiven by player %s", marriage.id, player_id)
            return ForgiveResult(
                marriage_id=marriage.id,
                forgiver_player_id=player_id,
                requester_player_id=requester,
                relationship_points_before=points_before,
                relationship_points_after=points_after,
                requester_telegram_user_id=(
                    requester_player.telegram_user_id if requester_player else 0
                ),
            )

    # === Reads ====================================================================

    async def get_family_info(self, player_id: int) -> FamilyInfoData | None:
        """The complete family picture of a player (``None`` if unregistered)."""
        async with self._session_factory() as session:
            players = PlayerRepository(session)
            player = await players.get_by_id(player_id)
            if player is None:
                return None

            marriage = await MarriageRepository(session).get_active_for_player(player_id)
            child_rows = await ChildRepository(session).list_by_parent(player_id)
            now = _utc_now()
            children = tuple(
                ChildData(
                    id=row.id,
                    marriage_id=row.marriage_id,
                    father_player_id=row.father_player_id,
                    mother_player_id=row.mother_player_id,
                    name=row.name,
                    gender=row.gender,
                    birth_date=row.birth_date,
                    age_years=_age_years(_as_naive_utc(row.birth_date), now),
                    education_level=row.education_level,
                    expense_total=row.expense_total,
                )
                for row in child_rows
            )

            spouse = None
            if marriage is not None:
                spouse_id = (
                    marriage.partner_b_id
                    if marriage.partner_a_id == player_id
                    else marriage.partner_a_id
                )
                spouse = await players.get_by_id(spouse_id)

            divorce_age: int | None = None
            if (
                marriage is not None
                and marriage.divorce_requested_at is not None
                and marriage.divorce_requested_by_player_id is not None
            ):
                divorce_age = max(
                    0,
                    int((_as_naive_utc(now) - _as_naive_utc(marriage.divorce_requested_at)).total_seconds()),
                )

            return FamilyInfoData(
                player_id=player.id,
                display_name=player.display_name,
                marriage_status=player.marriage_status or STATUS_SINGLE,
                spouse_player_id=spouse.id if spouse else None,
                spouse_display_name=spouse.display_name if spouse else None,
                spouse_telegram_user_id=spouse.telegram_user_id if spouse else None,
                marriage_id=marriage.id if marriage else None,
                married_at=marriage.married_at if marriage else player.married_at,
                mahr=marriage.mahr if marriage else 0,
                relationship_points=(
                    marriage.relationship_points
                    if marriage
                    else constants.FAMILY_RELATIONSHIP_START_POINTS
                ),
                cheating_count=marriage.cheating_count if marriage else 0,
                children_count=len(children),
                divorce_pending_by_me=bool(
                    marriage and marriage.divorce_requested_by_player_id == player_id
                ),
                divorce_requested_by_spouse=bool(
                    marriage
                    and marriage.divorce_requested_by_player_id is not None
                    and marriage.divorce_requested_by_player_id != player_id
                ),
                divorce_request_age_seconds=divorce_age,
                children=children,
            )

    async def get_family_snapshot(self, player_id: int) -> FamilySnapshot:
        """The small family block the profile screen renders (never raises)."""
        async with self._session_factory() as session:
            players = PlayerRepository(session)
            player = await players.get_by_id(player_id)
            if player is None:
                return FamilySnapshot(marriage_status=STATUS_SINGLE)
            spouse = (
                await players.get_by_id(player.spouse_player_id)
                if player.spouse_player_id
                else None
            )
            return FamilySnapshot(
                marriage_status=player.marriage_status or STATUS_SINGLE,
                spouse_player_id=spouse.id if spouse else None,
                spouse_display_name=spouse.display_name if spouse else None,
                married_at=player.married_at,
                children_count=player.children_count or 0,
            )

    async def get_snapshot_by_telegram_user_id(self, telegram_user_id: int) -> FamilySnapshot | None:
        """Snapshot keyed by Telegram id (profile integration). ``None`` if unregistered."""
        async with self._session_factory() as session:
            player = await PlayerRepository(session).get_by_telegram_user_id(telegram_user_id)
            if player is None:
                return None
            return await self.get_family_snapshot(player.id)

    async def list_divorces_of(self, player_id: int, limit: int = 10) -> list[DivorceRecordData]:
        """Divorce history of a player (newest first, names resolved)."""
        async with self._session_factory() as session:
            players = PlayerRepository(session)
            records = await DivorceRecordRepository(session).list_by_player(player_id, limit)
            out: list[DivorceRecordData] = []
            for record in records:
                other_id = (
                    record.partner_b_id
                    if record.partner_a_id == player_id
                    else record.partner_a_id
                )
                other = await players.get_by_id(other_id)
                initiator = await players.get_by_id(record.initiator_player_id)
                out.append(
                    DivorceRecordData(
                        id=record.id,
                        marriage_id=record.marriage_id,
                        initiator_player_id=record.initiator_player_id,
                        partner_a_id=record.partner_a_id,
                        partner_b_id=record.partner_b_id,
                        mahr=record.mahr,
                        paid_amount=record.paid_amount,
                        unpaid_debt=record.unpaid_debt,
                        reason=record.reason,
                        created_at=record.created_at,
                        initiator_display_name=initiator.display_name if initiator else "?",
                        other_display_name=other.display_name if other else "?",
                    )
                )
            return out

    async def list_history(
        self, player_id: int, limit: int = 15, offset: int = 0
    ) -> list[FamilyHistoryEntry]:
        """The player's family history log (newest first)."""
        async with self._session_factory() as session:
            rows = await FamilyHistoryRepository(session).list_by_player(player_id, limit, offset)
            return [
                FamilyHistoryEntry(
                    id=row.id,
                    player_id=row.player_id,
                    marriage_id=row.marriage_id,
                    event_type=row.event_type,
                    details=row.details,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    async def list_children_of(self, player_id: int) -> list[ChildData]:
        """All children of a player (both parents are covered)."""
        async with self._session_factory() as session:
            rows = await ChildRepository(session).list_by_parent(player_id)
            now = _utc_now()
            return [
                ChildData(
                    id=row.id,
                    marriage_id=row.marriage_id,
                    father_player_id=row.father_player_id,
                    mother_player_id=row.mother_player_id,
                    name=row.name,
                    gender=row.gender,
                    birth_date=row.birth_date,
                    age_years=_age_years(_as_naive_utc(row.birth_date), now),
                    education_level=row.education_level,
                    expense_total=row.expense_total,
                )
                for row in rows
            ]

    # === Internals ==================================================================

    @staticmethod
    def _cooldown_wait(last: datetime | None, now: datetime, seconds: int) -> int:
        """Seconds still to wait (0 = free to go)."""
        if last is None:
            return 0
        elapsed = (_as_naive_utc(now) - _as_naive_utc(last)).total_seconds()
        return max(0, int(seconds - elapsed))

    async def _expire_pending_proposals(self, session: AsyncSession, *, now: datetime) -> None:
        """Flip lapsed pending proposals to ``expired`` (idempotent sweep)."""
        await session.execute(
            update(MarriageProposal)
            .where(
                MarriageProposal.status == STATUS_PENDING,
                MarriageProposal.expires_at.is_not(None),
                MarriageProposal.expires_at < now,
            )
            .values(status=STATUS_EXPIRED, answered_at=now),
            execution_options={"synchronize_session": False},
        )

    async def _grant_xp(self, player_id: int, amount: int, *, reason: str) -> None:
        """Family XP goes through the existing LevelService — never implicit,
        always with a reason, and it never blocks the game flow."""
        if self._level_service is None or amount <= 0:
            return
        try:
            await self._level_service.add_xp(player_id, amount, reason=reason)
        except Exception:  # noqa: BLE001 — XP never blocks a family event
            logger.warning("Could not grant family XP to player %s", player_id, exc_info=True)

    @staticmethod
    def _to_proposal_dto(proposal: MarriageProposal) -> ProposalData:
        return ProposalData(
            id=proposal.id,
            sender_player_id=proposal.sender_player_id,
            receiver_player_id=proposal.receiver_player_id,
            mahr=proposal.mahr,
            created_at=proposal.created_at,
            expires_at=proposal.expires_at,
        )
