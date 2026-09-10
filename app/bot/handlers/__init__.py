"""Registers all Telegram handlers — the single routing map of the bot."""

from __future__ import annotations

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from app.bot.handlers import admin, labor, main_menu, start
from app.bot.handlers.errors import error_handler
from app.bot.keyboards import callbacks


def register_handlers(application: Application) -> None:
    """Wire all routes.

    Order matters: specific callbacks come first and the unknown-callback
    fallback must be registered last (first match wins inside a group).
    """
    # Public commands
    application.add_handler(CommandHandler("start", start.start_handler))

    # Admin dev commands (protected by ADMIN_IDS inside handlers)
    application.add_handler(CommandHandler("admin_add_xp", admin.admin_add_xp))
    application.add_handler(CommandHandler("admin_remove_xp", admin.admin_remove_xp))
    application.add_handler(CommandHandler("admin_set_level", admin.admin_set_level))
    application.add_handler(CommandHandler("admin_status", admin.admin_status))
    application.add_handler(CommandHandler("admin_xp_history", admin.admin_xp_history))

    # Labor system — text message "کارگری"
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex(f"^{labor.LABOR_TRIGGER}$"), labor.labor_handler)
    )

    # Main menu callbacks
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
