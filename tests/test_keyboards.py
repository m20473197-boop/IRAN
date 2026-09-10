"""Keyboard architecture tests — only real features are exposed."""

from __future__ import annotations

from telegram import InlineKeyboardMarkup

from app.bot.keyboards import callbacks
from app.bot.keyboards.main_menu import (
    BUTTON_BACK_TO_MAIN,
    BUTTON_JOBS,
    BUTTON_PROFILE,
    BUTTON_STATUS,
    build_back_to_main,
    build_main_menu,
)


def _flat_buttons(markup: InlineKeyboardMarkup):
    return [button for row in markup.inline_keyboard for button in row]


def test_main_menu_exposes_only_implemented_features():
    buttons = _flat_buttons(build_main_menu())

    assert {b.text for b in buttons} == {
        BUTTON_PROFILE,
        BUTTON_STATUS,
        BUTTON_JOBS,
    }
    assert {b.callback_data for b in buttons} == {
        callbacks.PROFILE,
        callbacks.STATUS,
        callbacks.JOBS_MENU,
    }
    # No fake buttons for future systems (market, crime, housing, ...).
    # Jobs is now implemented, so "شغل" is allowed.
    labels = " ".join(b.text for b in buttons).lower()
    for banned in ("بازار", "خونه", "جرم", "fromid", "market", "crime", "house"):
        assert banned not in labels


def test_back_button_returns_to_main_menu():
    buttons = _flat_buttons(build_back_to_main())

    assert len(buttons) == 1
    assert buttons[0].callback_data == callbacks.BACK_TO_MAIN
    assert buttons[0].text == BUTTON_BACK_TO_MAIN
