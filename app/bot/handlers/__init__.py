"""Registers all Telegram handlers — the single routing map of the bot."""

from __future__ import annotations

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from app.bot.handlers import admin, housing, job, main_menu, start
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

    # Job system — text messages
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex(f"^{job.JOBS_TEXT_TRIGGER}$"), job.jobs_text_handler)
    )
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex(f"^{job.MY_JOB_TEXT_TRIGGER}$"), job.my_job_text_handler)
    )
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(f"^{job.LEAVE_JOB_TEXT_TRIGGER}$"), job.leave_job_text_handler
        )
    )
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(f"^{job.APPLY_JOB_TEXT_TRIGGER}.*$"), job.apply_job_text_handler
        )
    )

    # Housing system — text messages («خانه» / «مسکن» open the housing menu)
    application.add_handler(
        MessageHandler(
            filters.TEXT
            & filters.Regex(
                f"^({housing.HOUSING_TEXT_TRIGGER}|{housing.HOUSING_MENU_TEXT_TRIGGER})$"
            ),
            housing.housing_text_handler,
        )
    )

    # Job callbacks
    application.add_handler(
        CallbackQueryHandler(job.show_jobs_menu, pattern=rf"^{callbacks.JOBS_MENU}$")
    )
    application.add_handler(
        CallbackQueryHandler(job.show_jobs_list, pattern=rf"^{callbacks.JOBS_LIST}$")
    )
    application.add_handler(
        CallbackQueryHandler(job.show_my_job, pattern=rf"^{callbacks.JOBS_MY_JOB}$")
    )
    application.add_handler(
        CallbackQueryHandler(job.settle_job_callback, pattern=rf"^{callbacks.JOBS_SETTLE}$")
    )
    application.add_handler(
        CallbackQueryHandler(job.leave_job_callback, pattern=rf"^{callbacks.JOBS_LEAVE}$")
    )
    application.add_handler(
        CallbackQueryHandler(job.show_job_history, pattern=rf"^{callbacks.JOBS_HISTORY}$")
    )
    application.add_handler(
        CallbackQueryHandler(
            job.apply_job_callback, pattern=rf"^{callbacks.JOBS_APPLY_PREFIX}\d+$"
        )
    )

    # Housing callbacks — all must be registered BEFORE the unknown fallback.
    application.add_handler(
        CallbackQueryHandler(
            housing.show_housing_menu, pattern=rf"^{callbacks.HOUSING_MENU}$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(housing.show_my_houses, pattern=rf"^{callbacks.HOUSES_MY}$")
    )
    application.add_handler(
        CallbackQueryHandler(housing.show_market, pattern=rf"^{callbacks.HOUSES_MARKET}$")
    )
    application.add_handler(
        CallbackQueryHandler(housing.show_rentals, pattern=rf"^{callbacks.HOUSES_RENTALS}$")
    )
    application.add_handler(
        CallbackQueryHandler(housing.show_my_rents, pattern=rf"^{callbacks.HOUSES_MY_RENTS}$")
    )
    application.add_handler(
        CallbackQueryHandler(
            housing.show_buy_confirmation,
            pattern=rf"^{callbacks.HOUSE_BUY_PREFIX}\d+$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            housing.confirm_buy,
            pattern=rf"^{callbacks.HOUSE_BUY_CONFIRM_PREFIX}\d+$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            housing.show_sale_options,
            pattern=rf"^{callbacks.HOUSE_SELL_OPTIONS_PREFIX}\d+$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            housing.confirm_sell,
            pattern=rf"^{callbacks.HOUSE_SELL_SET_PREFIX}\d+_\d+$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            housing.cancel_sale,
            pattern=rf"^{callbacks.HOUSE_SELL_CANCEL_PREFIX}\d+$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            housing.show_rentout_options,
            pattern=rf"^{callbacks.HOUSE_RENTOUT_OPTIONS_PREFIX}\d+$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            housing.confirm_rent_out,
            pattern=rf"^{callbacks.HOUSE_RENT_SET_PREFIX}\d+_\d+$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            housing.cancel_rent,
            pattern=rf"^{callbacks.HOUSE_RENT_CANCEL_PREFIX}\d+$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            housing.show_rent_confirmation,
            pattern=rf"^{callbacks.RENT_CONFIRM_PREFIX}\d+$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            housing.pay_rent, pattern=rf"^{callbacks.RENT_PAY_PREFIX}\d+$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            housing.end_rent_contract, pattern=rf"^{callbacks.RENT_END_PREFIX}\d+$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            housing.show_house_info, pattern=rf"^{callbacks.HOUSE_INFO_PREFIX}\d+$"
        )
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
