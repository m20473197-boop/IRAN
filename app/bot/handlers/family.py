"""Marriage & Family handlers — the complete system, command-only.

The family system deliberately has **no menus and no buttons**: every action
is a Persian text message (mirroring how the job/housing systems accept text
triggers), and the two-sided flows («ازدواج» → «قبول»/«رد») are addressed by
*replying* to the other player's message.

All rules live in :class:`app.services.family_service.FamilyService`; these
handlers only translate Telegram objects into service calls, map domain
errors to friendly Persian texts and deliver the private notifications the
service says are warranted.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.context import get_services
from app.bot.handlers.guards import player_id_for
from app.bot.messages import errors as error_messages
from app.bot.messages import family as family_messages
from app.game.family.dto import DivorceRequestResult, DivorceResult
from app.game.shared.errors import PlayerNotFoundError
from app.services.family_service import (
    AlreadyMarriedError,
    CannotForgiveOwnDivorceError,
    CheatingTooSoonError,
    InsufficientMahriyehError,
    LevelTooLowError,
    NoDivorcePendingError,
    NoPendingProposalError,
    NotMarriedError,
    NotSpouseError,
    ProposalBusyError,
    RelationshipTooSoonError,
    SelfMarriageError,
)

logger = logging.getLogger(__name__)

# --- Text triggers (exact-match Persian commands) -----------------------------

MARRY_TEXT_TRIGGER = "ازدواج"
ACCEPT_TEXT_TRIGGER = "قبول"
REJECT_TEXT_TRIGGER = "رد"
DIVORCE_TEXT_TRIGGER = "طلاق"
FORGIVE_TEXT_TRIGGER = "بخشش"
CHEAT_TEXT_TRIGGER = "خیانت"
RELATIONSHIP_TEXT_TRIGGER = "رابطه"
FAMILY_INFO_TEXT_TRIGGER = "خانواده"
DIVORCE_HISTORY_TEXT_TRIGGER = "سابقه طلاق"
FAMILY_HISTORY_TEXT_TRIGGER = "تاریخچه خانواده"


# --- Telegram helpers -------------------------------------------------------------


async def _reply_target(services, update: Update):
    """The Player row of the replied-to message (auto-registered), else None.

    Unregistered Telegram users are registered on the fly when they are
    *targeted* by a family command, so a proposal never dead-ends on a
    missing profile for somebody the players are talking about.
    """
    message = update.message
    if (
        message is None
        or message.reply_to_message is None
        or message.reply_to_message.from_user is None
    ):
        return None
    target = message.reply_to_message.from_user
    if target.is_bot:
        return None

    from app.database.repositories.player_repository import PlayerRepository

    result = await services.players.register_or_get(
        telegram_user_id=target.id,
        username=target.username,
        display_name=target.full_name,
    )
    async with services.players._session_factory() as session:  # type: ignore[attr-defined]
        return await PlayerRepository(session).get_by_id(result.player_id)


async def _display_name(services, telegram_user_id: int) -> str:
    profile = await services.players.get_profile(telegram_user_id)
    return profile.display_name if profile is not None else "همسر"


async def _send_private(context: ContextTypes.DEFAULT_TYPE, tg_id: int, text: str) -> None:
    """Deliver a private family notification (never breaks the main flow)."""
    try:
        await context.bot.send_message(chat_id=tg_id, text=text)
    except Exception as exc:  # noqa: BLE001 — the spouse may have blocked the bot
        logger.info("Family notification to %s not delivered: %s", tg_id, exc)


# === «ازدواج» — propose ==============================================================


async def marry_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«ازدواج» — reply to someone's message to propose marriage.

    Optional argument = the offered Mahriyeh («مهریه»), e.g. «ازدواج ۵۰۰۰۰۰».
    """
    message = update.message
    if message is None or update.effective_user is None:
        return

    services = get_services(context)
    player_id = await player_id_for(services, update.effective_user.id)
    if player_id is None:
        await message.reply_text(error_messages.NOT_REGISTERED)
        return

    arg = (message.text or "").strip()[len(MARRY_TEXT_TRIGGER):].strip()
    mahr: int | None = None
    if arg:
        from app.game.admin.parsing import parse_admin_int

        parsed = parse_admin_int(arg)
        if parsed is None or parsed < 0:
            await message.reply_text(
                f"مهریه نامعتبر است 🤔 — عدد بفرست: «{MARRY_TEXT_TRIGGER} ۵۰۰۰۰۰»"
            )
            return
        mahr = parsed

    target = await _reply_target(services, update)
    if target is None:
        await message.reply_text(family_messages.usage_proposal())
        return
    if target.id == player_id:
        await message.reply_text(family_messages.self_proposal())
        return

    try:
        result = await services.family.create_proposal(
            sender_player_id=player_id,
            receiver_player_id=target.id,
            mahr=mahr,
        )
    except SelfMarriageError:
        await message.reply_text(family_messages.self_proposal())
        return
    except LevelTooLowError as exc:
        await message.reply_text(
            family_messages.level_too_low(exc.player_display_name, exc.level)
        )
        return
    except AlreadyMarriedError as exc:
        if exc.married_side == "receiver":
            await message.reply_text(
                family_messages.target_already_married(target.display_name)
            )
        else:
            await message.reply_text(family_messages.already_married_self())
        return
    except ProposalBusyError:
        await message.reply_text(family_messages.proposal_busy())
        return
    except PlayerNotFoundError:
        await message.reply_text(family_messages.not_registered_target())
        return
    except Exception as exc:  # noqa: BLE001 — never leak a traceback into chat
        logger.error("marry_text_handler failed for %s", update.effective_user.id, exc_info=exc)
        await message.reply_text(family_messages.usage_proposal())
        return

    await message.reply_text(family_messages.proposal_sent(result))
    # The proposal card is delivered to the target privately.
    await _send_private(
        context,
        result.target_telegram_user_id,
        family_messages.target_proposal_received(result),
    )


# === «قبول» / «رد» — answer a proposal ============================================


async def accept_proposal_text_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """«قبول» — accept the pending marriage proposal aimed at you."""
    message = update.message
    if message is None or update.effective_user is None:
        return

    services = get_services(context)
    player_id = await player_id_for(services, update.effective_user.id)
    if player_id is None:
        await message.reply_text(error_messages.NOT_REGISTERED)
        return

    try:
        result = await services.family.accept_pending_proposal(player_id)
    except NoPendingProposalError:
        await message.reply_text(family_messages.no_pending_proposal())
        return
    except AlreadyMarriedError as exc:
        if exc.married_side == "receiver":
            await message.reply_text(family_messages.already_married_self())
        else:
            await message.reply_text("😕 طرف مقابل الان متأهله — درخواستش رد شد.")
        return
    except Exception as exc:  # noqa: BLE001
        logger.error("accept_proposal failed for %s", update.effective_user.id, exc_info=exc)
        await message.reply_text(error_messages.GENERIC)
        return

    await message.reply_text(family_messages.proposal_accepted(result))
    await _send_private(
        context,
        result.proposer_telegram_user_id,
        family_messages.target_accepted_copy(result.target_display_name),
    )


async def reject_proposal_text_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """«رد» — reject the pending marriage proposal aimed at you."""
    message = update.message
    if message is None or update.effective_user is None:
        return

    services = get_services(context)
    player_id = await player_id_for(services, update.effective_user.id)
    if player_id is None:
        await message.reply_text(error_messages.NOT_REGISTERED)
        return

    try:
        proposal = await services.family.reject_pending_proposal(player_id)
    except NoPendingProposalError:
        await message.reply_text(family_messages.no_pending_proposal())
        return
    except Exception as exc:  # noqa: BLE001
        logger.error("reject_proposal failed for %s", update.effective_user.id, exc_info=exc)
        await message.reply_text(error_messages.GENERIC)
        return

    my_name = await _display_name(services, update.effective_user.id)
    await message.reply_text(family_messages.proposal_rejection_done())
    proposer_tg_id = await _telegram_id_of(services, proposal.sender_player_id)
    if proposer_tg_id:
        await _send_private(
            context, proposer_tg_id, family_messages.proposal_rejected(my_name)
        )


async def _telegram_id_of(services, player_id: int) -> int | None:
    from app.database.repositories.player_repository import PlayerRepository

    async with services.players._session_factory() as session:  # type: ignore[attr-defined]
        player = await PlayerRepository(session).get_by_id(player_id)
        return player.telegram_user_id if player is not None else None


# === «طلاق» / «بخشش» — divorce =======================================================


async def divorce_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«طلاق» — file a divorce; a second «طلاق» (either side) finalizes it."""
    message = update.message
    if message is None or update.effective_user is None:
        return

    services = get_services(context)
    player_id = await player_id_for(services, update.effective_user.id)
    if player_id is None:
        await message.reply_text(error_messages.NOT_REGISTERED)
        return

    try:
        result = await services.family.request_or_finalize_divorce(player_id)
    except NotMarriedError:
        await message.reply_text(family_messages.not_married())
        return
    except InsufficientMahriyehError as exc:
        await message.reply_text(
            family_messages.insufficient_mahr(exc.mahr, exc.balance, exc.shortfall)
        )
        return
    except Exception as exc:  # noqa: BLE001
        logger.error("divorce_text_handler failed for %s", update.effective_user.id, exc_info=exc)
        await message.reply_text(error_messages.GENERIC)
        return

    if isinstance(result, DivorceResult):
        await message.reply_text(family_messages.divorce_finalized(result))
        await _send_private(
            context,
            result.other_telegram_user_id,
            family_messages.divorce_other_side_copy(result),
        )
        return

    assert isinstance(result, DivorceRequestResult)
    await message.reply_text(family_messages.divorce_request_filed(result))
    my_name = await _display_name(services, update.effective_user.id)
    await _send_private(
        context,
        result.spouse_telegram_user_id,
        family_messages.divorce_request_incoming(my_name, result),
    )


async def forgive_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«بخشش» — forgive the spouse's divorce request; the marriage survives."""
    message = update.message
    if message is None or update.effective_user is None:
        return

    services = get_services(context)
    player_id = await player_id_for(services, update.effective_user.id)
    if player_id is None:
        await message.reply_text(error_messages.NOT_REGISTERED)
        return

    try:
        result = await services.family.forgive_divorce(player_id)
    except NotMarriedError:
        await message.reply_text(family_messages.not_married())
        return
    except NoDivorcePendingError:
        await message.reply_text(family_messages.nothing_to_forgive())
        return
    except CannotForgiveOwnDivorceError:
        await message.reply_text(family_messages.cannot_forgive_own())
        return
    except Exception as exc:  # noqa: BLE001
        logger.error("forgive_text_handler failed for %s", update.effective_user.id, exc_info=exc)
        await message.reply_text(error_messages.GENERIC)
        return

    await message.reply_text(family_messages.forgiven(result))
    my_name = await _display_name(services, update.effective_user.id)
    if result.requester_telegram_user_id:
        await _send_private(
            context,
            result.requester_telegram_user_id,
            family_messages.forgiveness_copy(my_name, result),
        )


# === «خیانت» — secret cheating =========================================================


async def cheat_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«خیانت» — a *hidden* affair attempt: only the author sees the result.

    When the attempt is discovered, the spouse is notified privately and the
    consequences (relationship damage, social penalties, a real divorce
    possibility) are applied by the service.
    """
    message = update.message
    if message is None or update.effective_user is None:
        return

    services = get_services(context)
    player_id = await player_id_for(services, update.effective_user.id)
    if player_id is None:
        await message.reply_text(error_messages.NOT_REGISTERED)
        return

    try:
        result = await services.family.cheat_attempt(player_id)
    except NotMarriedError:
        await message.reply_text(family_messages.not_married_cheat())
        return
    except CheatingTooSoonError as exc:
        await message.reply_text(family_messages.cheat_too_soon(exc.wait_seconds))
        return
    except Exception as exc:  # noqa: BLE001
        logger.error("cheat_text_handler failed for %s", update.effective_user.id, exc_info=exc)
        await message.reply_text(error_messages.GENERIC)
        return

    await message.reply_text(family_messages.cheat_attempt_result(result))
    if result.discovered and result.spouse_telegram_user_id:
        await _send_private(
            context,
            result.spouse_telegram_user_id,
            family_messages.spouse_cheat_notification(
                result.cheater_display_name or "همسرت", result
            ),
        )


# === «رابطه» — relationship ============================================================


async def relationship_text_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """«رابطه» — reply to your spouse's message to share a relationship event.

    Only married players can use it; each event carries a pregnancy chance —
    a birth creates the child record, updates the family counters and grants
    XP to both parents (through the existing LevelService).
    """
    message = update.message
    if message is None or update.effective_user is None:
        return

    services = get_services(context)
    player_id = await player_id_for(services, update.effective_user.id)
    if player_id is None:
        await message.reply_text(error_messages.NOT_REGISTERED)
        return

    spouse_hint: int | None = None
    if (
        message.reply_to_message is not None
        and message.reply_to_message.from_user is not None
        and not message.reply_to_message.from_user.is_bot
    ):
        target = await _reply_target(services, update)
        if target is None:
            await message.reply_text(family_messages.not_spouse_reply())
            return
        spouse_hint = target.id

    try:
        result = await services.family.relationship_event(
            player_id, partner_hint_player_id=spouse_hint
        )
    except NotMarriedError:
        await message.reply_text(family_messages.not_married())
        return
    except NotSpouseError:
        await message.reply_text(family_messages.not_spouse_reply())
        return
    except RelationshipTooSoonError as exc:
        await message.reply_text(family_messages.relationship_too_soon(exc.wait_seconds))
        return
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "relationship_text_handler failed for %s", update.effective_user.id, exc_info=exc
        )
        await message.reply_text(error_messages.GENERIC)
        return

    if result.child is not None:
        info = await services.family.get_family_info(player_id)
        children_count = info.children_count if info is not None else 0
        await message.reply_text(family_messages.relationship_birth(result, children_count))
        await _send_private(
            context,
            result.partner_telegram_user_id,
            family_messages.partner_copy_birth(result.child.name),
        )
    elif result.pregnant:
        await message.reply_text(family_messages.relationship_pregnancy(result))
    else:
        await message.reply_text(family_messages.relationship_event(result))


# === Info screens («خانواده» …) — plain text, no menus ==============================


async def family_info_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«خانواده» — marriage status, spouse, marriage date, Mahriyeh, children."""
    message = update.message
    if message is None or update.effective_user is None:
        return

    services = get_services(context)
    player_id = await player_id_for(services, update.effective_user.id)
    if player_id is None:
        await message.reply_text(error_messages.NOT_REGISTERED)
        return

    info = await services.family.get_family_info(player_id)
    if info is None:
        await message.reply_text(error_messages.NOT_REGISTERED)
        return
    await message.reply_text(family_messages.family_info_text(info))


async def divorce_history_text_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """«سابقه طلاق» — the stored divorce records of this player."""
    message = update.message
    if message is None or update.effective_user is None:
        return

    services = get_services(context)
    player_id = await player_id_for(services, update.effective_user.id)
    if player_id is None:
        await message.reply_text(error_messages.NOT_REGISTERED)
        return

    records = await services.family.list_divorces_of(player_id)
    await message.reply_text(family_messages.divorce_history_text(records))


async def family_history_text_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """«تاریخچه خانواده» — the append-only family log."""
    message = update.message
    if message is None or update.effective_user is None:
        return

    services = get_services(context)
    player_id = await player_id_for(services, update.effective_user.id)
    if player_id is None:
        await message.reply_text(error_messages.NOT_REGISTERED)
        return

    entries = await services.family.list_history(player_id, limit=15)
    await message.reply_text(family_messages.family_history_text(entries))


__all__ = [
    "MARRY_TEXT_TRIGGER",
    "ACCEPT_TEXT_TRIGGER",
    "REJECT_TEXT_TRIGGER",
    "DIVORCE_TEXT_TRIGGER",
    "FORGIVE_TEXT_TRIGGER",
    "CHEAT_TEXT_TRIGGER",
    "RELATIONSHIP_TEXT_TRIGGER",
    "FAMILY_INFO_TEXT_TRIGGER",
    "DIVORCE_HISTORY_TEXT_TRIGGER",
    "FAMILY_HISTORY_TEXT_TRIGGER",
    "marry_text_handler",
    "accept_proposal_text_handler",
    "reject_proposal_text_handler",
    "divorce_text_handler",
    "forgive_text_handler",
    "cheat_text_handler",
    "relationship_text_handler",
    "family_info_text_handler",
    "divorce_history_text_handler",
    "family_history_text_handler",
]
