"""Business system handlers — «کسب و کار» menu and its inline screens.

Handlers only translate Telegram objects into BusinessService calls and
Persian answers back; no business rules and zero database access here.

Player-facing entry points:
- text «کسب و کار» / «بیزینس»  → the business menu
- biz_menu / biz_list / biz_mine / biz_collect  → the four menu screens
- biz_start_<key> → confirmation, biz_open_<key> → pays and starts
- biz_view_<id> → detail, biz_collect1_<id> → daily income for one business

Employee hiring is intentionally NOT part of this system (disabled for now).
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.game.business.rules import business_day
from app.bot.context import get_services
from app.bot.handlers.guards import player_id_for
from app.bot.keyboards import business as keyboards
from app.bot.keyboards import callbacks
from app.bot.messages import business as biz_messages
from app.bot.messages import errors as error_messages
from app.game.business.rules import catalog_item
from app.game.shared.errors import PlayerNotFoundError
from app.services.business_service import (
    BusinessFundsError,
    BusinessNotFoundError,
    BusinessTypeNotFoundError,
    BusinessUnavailableError,
    NotBusinessOwnerError,
    TooManyBusinessesError,
)

logger = logging.getLogger(__name__)

BUSINESS_TEXT_TRIGGER = "کسب و کار"
BUSINESS_ALIAS_TRIGGER = "بیزینس"


# --- Shared helpers -------------------------------------------------------------


async def _menu_player_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """Resolve the acting Telegram user to a player id (None if unregistered)."""
    services = get_services(context)
    if update.callback_query is not None:
        tg_id = update.callback_query.from_user.id
    elif update.effective_user is not None:
        tg_id = update.effective_user.id
    else:
        return None
    return await player_id_for(services, tg_id)


# --- Text trigger ---------------------------------------------------------------


async def business_text_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """«کسب و کار» / «بیزینس» — open the business menu."""
    if update.message is None or update.effective_user is None:
        return
    text = (update.message.text or "").strip()
    if text not in (BUSINESS_TEXT_TRIGGER, BUSINESS_ALIAS_TRIGGER):
        return

    services = get_services(context)
    player_id = await player_id_for(services, update.effective_user.id)
    if player_id is None:
        await update.message.reply_text(error_messages.NOT_REGISTERED)
        return

    owned = await services.business.count_active_businesses(player_id)
    await update.message.reply_text(
        text=biz_messages.business_menu_text(),
        reply_markup=keyboards.build_business_menu(owned),
    )


# --- Callback screens -------------------------------------------------------------


async def business_menu_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if query is None or query.data != callbacks.BUSINESS_MENU:
        return
    await query.answer()

    services = get_services(context)
    player_id = await _menu_player_id(update, context)
    if player_id is None:
        await query.edit_message_text(text=error_messages.NOT_REGISTERED, reply_markup=None)
        return

    owned = await services.business.count_active_businesses(player_id)
    await query.edit_message_text(
        text=biz_messages.business_menu_text(),
        reply_markup=keyboards.build_business_menu(owned),
    )


async def catalog_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """🏪 لیست کسب‌وکارها — the predefined catalog (the only way to start)."""
    query = update.callback_query
    if query is None or query.data != callbacks.BUSINESS_LIST:
        return
    await query.answer()

    services = get_services(context)
    player_id = await _menu_player_id(update, context)
    if player_id is None:
        await query.edit_message_text(text=error_messages.NOT_REGISTERED, reply_markup=None)
        return

    entries = services.business.get_available_catalog()
    owned = await services.business.count_active_businesses(player_id)
    wallet = await services.money.get_balance(player_id)
    await query.edit_message_text(
        text=biz_messages.business_catalog_text(
            entries, owned, services.business.max_owned(), wallet
        ),
        reply_markup=keyboards.build_business_list(entries),
    )


async def confirm_start_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """biz_start_<key> — show what starting this business costs."""
    query = update.callback_query
    if query is None or not (query.data or "").startswith(callbacks.BUSINESS_START_PREFIX):
        return
    await query.answer()

    key = (query.data or "")[len(callbacks.BUSINESS_START_PREFIX):]
    entry = catalog_item(key)
    if entry is None or not entry.available:
        await query.edit_message_text(
            text=biz_messages.business_invalid_type_text(),
            reply_markup=keyboards.build_business_menu(0),
        )
        return

    services = get_services(context)
    player_id = await _menu_player_id(update, context)
    if player_id is None:
        await query.edit_message_text(text=error_messages.NOT_REGISTERED, reply_markup=None)
        return

    wallet = await services.money.get_balance(player_id)
    await query.edit_message_text(
        text=biz_messages.business_confirm_text(entry, wallet),
        reply_markup=keyboards.build_business_confirm(entry),
    )


async def open_business_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """biz_open_<key> — pay the startup cost (via the wallet service) and start."""
    query = update.callback_query
    if query is None or not (query.data or "").startswith(callbacks.BUSINESS_OPEN_PREFIX):
        return
    await query.answer()

    services = get_services(context)
    player_id = await _menu_player_id(update, context)
    if player_id is None:
        await query.edit_message_text(text=error_messages.NOT_REGISTERED, reply_markup=None)
        return

    key = (query.data or "")[len(callbacks.BUSINESS_OPEN_PREFIX):]
    try:
        result = await services.business.start_business(player_id, key)
    except (BusinessTypeNotFoundError, BusinessUnavailableError):
        await query.edit_message_text(
            text=biz_messages.business_invalid_type_text(),
            reply_markup=keyboards.build_business_menu(0),
        )
        return
    except TooManyBusinessesError as exc:
        await query.edit_message_text(
            text=biz_messages.business_too_many_text(exc.max_owned),
            reply_markup=keyboards.build_business_menu(exc.max_owned),
        )
        return
    except BusinessFundsError as exc:
        owned = await services.business.count_active_businesses(player_id)
        await query.edit_message_text(
            text=biz_messages.business_insufficient_text(
                exc.required, exc.balance, exc.shortfall
            ),
            reply_markup=keyboards.build_business_menu(owned),
        )
        return
    except Exception as exc:
        logger.error("open_business_callback failed for %s", player_id, exc_info=exc)
        await query.edit_message_text(
            text=error_messages.GENERIC, reply_markup=keyboards.build_business_menu(0)
        )
        return

    await query.edit_message_text(
        text=biz_messages.business_started_text(
            result.business.type_name,
            result.paid_startup_cost,
            result.wallet_balance_after,
        ),
        reply_markup=keyboards.build_my_businesses([result.business], any_pending=True),
    )


async def mine_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """💼 کسب‌وکارهای من — balances and income state of everything owned."""
    query = update.callback_query
    if query is None or query.data != callbacks.BUSINESS_MINE:
        return
    await query.answer()

    services = get_services(context)
    player_id = await _menu_player_id(update, context)
    if player_id is None:
        await query.edit_message_text(text=error_messages.NOT_REGISTERED, reply_markup=None)
        return

    try:
        overview = await services.business.get_overview(player_id)
    except PlayerNotFoundError:
        await query.edit_message_text(text=error_messages.NOT_REGISTERED, reply_markup=None)
        return

    any_pending = any(
        b.status == "active" and not b.credited_on(overview.today)
        for b in overview.businesses
    )
    await query.edit_message_text(
        text=biz_messages.my_businesses_text(overview),
        reply_markup=keyboards.build_my_businesses(overview.businesses, any_pending),
    )


async def detail_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """biz_view_<id> — one business: cost, balance, income info."""
    query = update.callback_query
    if query is None or not (query.data or "").startswith(callbacks.BUSINESS_VIEW_PREFIX):
        return
    await query.answer()

    services = get_services(context)
    player_id = await _menu_player_id(update, context)
    if player_id is None:
        await query.edit_message_text(text=error_messages.NOT_REGISTERED, reply_markup=None)
        return

    try:
        business_id = int((query.data or "")[len(callbacks.BUSINESS_VIEW_PREFIX):])
    except ValueError:
        await query.answer(text="شناسه کسب و کار نامعتبر است.", show_alert=True)
        return

    try:
        business = await services.business.get_business(business_id, player_id)
    except BusinessNotFoundError:
        await query.edit_message_text(
            text=biz_messages.business_not_found_text(),
            reply_markup=keyboards.build_business_menu(0),
        )
        return
    except NotBusinessOwnerError:
        await query.edit_message_text(
            text=biz_messages.business_not_yours_text(),
            reply_markup=keyboards.build_business_menu(0),
        )
        return

    today = business_day()
    can_collect = business.status == "active" and not business.credited_on(today)
    await query.edit_message_text(
        text=biz_messages.business_detail_text(business, today),
        reply_markup=keyboards.build_business_detail(business, can_collect),
    )


async def collect_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """🧮 درآمد امروز — grant today's income for every eligible business."""
    query = update.callback_query
    if query is None or query.data != callbacks.BUSINESS_COLLECT:
        return
    await query.answer()

    services = get_services(context)
    player_id = await _menu_player_id(update, context)
    if player_id is None:
        await query.edit_message_text(text=error_messages.NOT_REGISTERED, reply_markup=None)
        return

    try:
        results = await services.business.collect_daily_income(player_id)
        owned = await services.business.list_businesses(player_id)
        await query.edit_message_text(
            text=biz_messages.income_summary_text(results, bool(owned)),
            reply_markup=keyboards.build_business_menu(
                len([b for b in owned if b.status == "active"])
            ),
        )
    except Exception as exc:
        logger.error("collect_callback failed for %s", player_id, exc_info=exc)
        await query.edit_message_text(
            text=error_messages.GENERIC, reply_markup=keyboards.build_business_menu(0)
        )


async def collect_one_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """biz_collect1_<id> — grant today's income for one business."""
    query = update.callback_query
    if query is None or not (query.data or "").startswith(
        callbacks.BUSINESS_COLLECT_ONE_PREFIX
    ):
        return
    await query.answer()

    services = get_services(context)
    player_id = await _menu_player_id(update, context)
    if player_id is None:
        await query.edit_message_text(text=error_messages.NOT_REGISTERED, reply_markup=None)
        return

    try:
        business_id = int(
            (query.data or "")[len(callbacks.BUSINESS_COLLECT_ONE_PREFIX):]
        )
    except ValueError:
        await query.answer(text="شناسه کسب و کار نامعتبر است.", show_alert=True)
        return

    try:
        result = await services.business.collect_business_income(business_id, player_id)
    except BusinessNotFoundError:
        await query.edit_message_text(
            text=biz_messages.business_not_found_text(),
            reply_markup=keyboards.build_business_menu(0),
        )
        return
    except NotBusinessOwnerError:
        await query.edit_message_text(
            text=biz_messages.business_not_yours_text(),
            reply_markup=keyboards.build_business_menu(0),
        )
        return

    owned = await services.business.list_businesses(player_id)
    any_pending = any(
        b.status == "active" and b.id != business_id and not b.credited_on(result.day)
        for b in owned
    )
    await query.edit_message_text(
        text=biz_messages.income_summary_text([result], bool(owned)),
        reply_markup=keyboards.build_my_businesses(owned, any_pending),
    )
