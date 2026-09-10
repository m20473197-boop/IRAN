"""Registers all Telegram handlers — the single routing map of the bot."""

from __future__ import annotations

from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from app.bot.handlers import main_menu, start
from app.bot.handlers.errors import error_handler
from app.bot.keyboards import callbacks


def register_handlers(application: Application) -> None:
    """Wire all routes.

    Order matters: specific callbacks come first and the unknown-callback
    fallback must be registered last (first match wins inside a group).
    """
    application.add_handler(CommandHandler("start", start.start_handler))

    application.add_handler(
        CallbackQueryHandler(main_menu.show_profile, pattern=rf"^{callbacks.PROFILE}$")
    )
    application.add_handler(
        CallbackQueryHandler(main_menu.show_status, pattern=rf"^{callbacks.STATUS}$")
    )
    application.add_handler(
        CallbackQueryHandler(
            main_menu.back_to_main, pattern=rf"^{callbacks.BACK_TO_MAIN}$"
        )
    )
    application.add_handler(CallbackQueryHandler(main_menu.unknown_callback))

    application.add_error_handler(error_handler)


__all__ = ["register_handlers"]
