"""Keyboard architecture tests — only real features are exposed."""

from __future__ import annotations

from telegram import InlineKeyboardMarkup

from app.bot.keyboards import callbacks
from app.bot.keyboards.main_menu import (
    BUTTON_BACK_TO_MAIN,
    BUTTON_PROFILE,
    BUTTON_STATUS,
    build_back_to_main,
    build_main_menu,
)


def _flat_buttons(markup: InlineKeyboardMarkup):
    return [button for row in markup.inline_keyboard for button in row]


def test_main_menu_exposes_only_implemented_features():
    buttons = _flat_buttons(build_main_menu())

    assert {b.text for b in buttons} == {BUTTON_PROFILE, BUTTON_STATUS}
    assert {b.callback_data for b in buttons} == {callbacks.PROFILE, callbacks.STATUS}
    # No fake buttons for future systems (jobs, market, crime, ...).
    labels = " ".join(b.text for b in buttons).lower()
    for banned in ("job", "شغل", "بازار", "خونه", "جرم", "fromid"):
        assert banned not in labels


def test_back_button_returns_to_main_menu():
    buttons = _flat_buttons(build_back_to_main())

    assert len(buttons) == 1
    assert buttons[0].callback_data == callbacks.BACK_TO_MAIN
    assert buttons[0].text == BUTTON_BACK_TO_MAIN
