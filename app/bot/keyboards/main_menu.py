"""Inline keyboard builders.

Keyboard construction lives here — never inside handlers — so menus stay
easy to reshape as new systems (jobs, market, ...) come online.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards import callbacks
from app.game.admin import runtime as admin_runtime

BUTTON_PROFILE: str = "👤 پروفایل"
BUTTON_STATUS: str = "📊 وضعیت"
BUTTON_JOBS: str = "💼 خر حمالی"
BUTTON_HOUSING: str = "🏠 خانه"
BUTTON_BACK_TO_MAIN: str = "🔙 منوی اصلی"


def build_main_menu() -> InlineKeyboardMarkup:
    """The main menu — only features that actually exist, nothing fake.

    Systems the admin switched off in ⚙️ Bot Settings are hidden as well
    (their handlers refuse access too, so stale buttons stay safe).
    """
    rows = [
        [
            InlineKeyboardButton(BUTTON_PROFILE, callback_data=callbacks.PROFILE),
            InlineKeyboardButton(BUTTON_STATUS, callback_data=callbacks.STATUS),
        ],
    ]
    if admin_runtime.feature_enabled("jobs"):
        rows.append(
            [
                InlineKeyboardButton(BUTTON_JOBS, callback_data=callbacks.JOBS_MENU),
            ]
        )
    if admin_runtime.feature_enabled("housing"):
        rows.append(
            [
                InlineKeyboardButton(
                    BUTTON_HOUSING, callback_data=callbacks.HOUSING_MENU
                ),
            ]
        )
    return InlineKeyboardMarkup(rows)


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


# --- Job keyboards ---------------------------------------------------------

BUTTON_JOBS_LIST: str = "📋 لیست کارها"
BUTTON_JOBS_MY_JOB: str = "👔 کار من"
BUTTON_JOBS_SETTLE: str = "💰 تسویه با صاحبکار"
BUTTON_JOBS_LEAVE: str = "🚪 ترک کار"
BUTTON_JOBS_HISTORY: str = "📜 تاریخچه تسویه‌ها"


def build_jobs_menu() -> InlineKeyboardMarkup:
    """Jobs main menu."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    BUTTON_JOBS_LIST, callback_data=callbacks.JOBS_LIST
                ),
                InlineKeyboardButton(
                    BUTTON_JOBS_MY_JOB, callback_data=callbacks.JOBS_MY_JOB
                ),
            ],
            [
                InlineKeyboardButton(
                    BUTTON_JOBS_SETTLE, callback_data=callbacks.JOBS_SETTLE
                ),
                InlineKeyboardButton(
                    BUTTON_JOBS_LEAVE, callback_data=callbacks.JOBS_LEAVE
                ),
            ],
            [
                InlineKeyboardButton(
                    BUTTON_JOBS_HISTORY, callback_data=callbacks.JOBS_HISTORY
                ),
            ],
            [
                InlineKeyboardButton(
                    BUTTON_BACK_TO_MAIN, callback_data=callbacks.BACK_TO_MAIN
                ),
            ],
        ]
    )


def build_jobs_list(jobs) -> InlineKeyboardMarkup:
    """Build list of available jobs with apply buttons."""
    rows = []
    for job in jobs:
        # job is JobData
        btn_text = (
            f"{job.name} - {job.hourly_salary:,} تومان/ساعت (لول {job.required_level})"
        )
        # Use callback with job id
        rows.append(
            [
                InlineKeyboardButton(
                    btn_text, callback_data=f"{callbacks.JOBS_APPLY_PREFIX}{job.id}"
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "🔙 بازگشت به منوی خر حمالی", callback_data=callbacks.JOBS_MENU
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                BUTTON_BACK_TO_MAIN, callback_data=callbacks.BACK_TO_MAIN
            )
        ]
    )
    return InlineKeyboardMarkup(rows)
