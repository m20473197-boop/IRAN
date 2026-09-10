"""Inline keyboard builders.

Keyboard construction lives here — never inside handlers — so menus stay
easy to reshape as new systems (jobs, market, ...) come online.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards import callbacks

BUTTON_PROFILE: str = "👤 پروفایل"
BUTTON_STATUS: str = "📊 وضعیت"
BUTTON_BACK_TO_MAIN: str = "🔙 منوی اصلی"


def build_main_menu() -> InlineKeyboardMarkup:
    """The main menu — only features that actually exist, nothing fake."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(BUTTON_PROFILE, callback_data=callbacks.PROFILE),
                InlineKeyboardButton(BUTTON_STATUS, callback_data=callbacks.STATUS),
            ]
        ]
    )


def build_back_to_main() -> InlineKeyboardMarkup:
    """A single button that returns to the main menu."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    BUTTON_BACK_TO_MAIN, callback_data=callbacks.BACK_TO_MAIN
                )
            ]
        ]
    )
