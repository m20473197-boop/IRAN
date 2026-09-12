"""Business system inline keyboards.

Keyboard construction lives here — never inside handlers — like the other
systems. All callback values come from the central registry (callbacks.py)
so the router stays the single source of truth.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards import callbacks
from app.bot.messages.formatters import fa_int
from app.game.business.rules import CatalogEntry

_MAX_BUTTON_LEN = 64


def _fit(text: str) -> str:
    return text if len(text) <= _MAX_BUTTON_LEN else text[: _MAX_BUTTON_LEN - 1] + "…"


def build_business_menu(owned_count: int = 0) -> InlineKeyboardMarkup:
    """Business main menu."""
    rows = [
        [
            InlineKeyboardButton(
                "🏪 لیست کسب‌وکارها", callback_data=callbacks.BUSINESS_LIST
            ),
            InlineKeyboardButton(
                f"💼 کسب‌وکارهای من ({fa_int(owned_count)})",
                callback_data=callbacks.BUSINESS_MINE,
            ),
        ],
        [
            InlineKeyboardButton(
                "🧮 درآمد امروز", callback_data=callbacks.BUSINESS_COLLECT
            ),
        ],
        [
            InlineKeyboardButton(
                "🔙 منوی اصلی", callback_data=callbacks.BACK_TO_MAIN
            ),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def build_business_list(entries: tuple[CatalogEntry, ...]) -> InlineKeyboardMarkup:
    """The predefined catalog — one start-button per business."""
    rows = []
    for entry in entries:
        rows.append(
            [
                InlineKeyboardButton(
                    _fit(f"🏪 {entry.name} • {fa_int(entry.startup_cost)} تومان"),
                    callback_data=f"{callbacks.BUSINESS_START_PREFIX}{entry.key}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "🔙 بازگشت به منوی کسب‌وکار", callback_data=callbacks.BUSINESS_MENU
            ),
            InlineKeyboardButton(
                "🔙 منوی اصلی", callback_data=callbacks.BACK_TO_MAIN
            ),
        ]
    )
    return InlineKeyboardMarkup(rows)


def build_business_confirm(entry: CatalogEntry) -> InlineKeyboardMarkup:
    """Confirmation screen before paying the startup cost."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _fit(f"✅ بزن بریم! شروع «{entry.name}»"),
                    callback_data=f"{callbacks.BUSINESS_OPEN_PREFIX}{entry.key}",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 بی‌خیال، برگرد به لیست", callback_data=callbacks.BUSINESS_LIST
                )
            ],
        ]
    )


def build_my_businesses(
    businesses: list, any_pending: bool
) -> InlineKeyboardMarkup:
    """One button per owned business (+ a collect button when income waits)."""
    rows = []
    for business in businesses:
        rows.append(
            [
                InlineKeyboardButton(
                    _fit(f"🏪 {business.type_name} • موجودی {fa_int(business.balance)}"),
                    callback_data=f"{callbacks.BUSINESS_VIEW_PREFIX}{business.id}",
                )
            ]
        )
    if any_pending:
        rows.append(
            [
                InlineKeyboardButton(
                    "🧮 گرفتن درآمد همه‌شون",
                    callback_data=callbacks.BUSINESS_COLLECT,
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "🏪 لیست کسب‌وکارها", callback_data=callbacks.BUSINESS_LIST
            ),
            InlineKeyboardButton(
                "🔙 منوی اصلی", callback_data=callbacks.BACK_TO_MAIN
            ),
        ]
    )
    return InlineKeyboardMarkup(rows)


def build_business_detail(business, can_collect: bool) -> InlineKeyboardMarkup:
    """Detail screen for one business."""
    rows = []
    if can_collect:
        rows.append(
            [
                InlineKeyboardButton(
                    "🧮 گرفتن درآمد امروز",
                    callback_data=f"{callbacks.BUSINESS_COLLECT_ONE_PREFIX}{business.id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "💼 کسب‌وکارهای من", callback_data=callbacks.BUSINESS_MINE
            ),
            InlineKeyboardButton(
                "🔙 منوی اصلی", callback_data=callbacks.BACK_TO_MAIN
            ),
        ]
    )
    return InlineKeyboardMarkup(rows)
