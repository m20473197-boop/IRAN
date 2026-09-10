"""Registers all Telegram handlers — the single routing map of the bot."""

from __future__ import annotations

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.bot.handlers import admin, admin_panel, housing, job, main_menu, realestate, start
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

    # Admin panel: the "پنل" message opens it; one conversation carries every
    # typed admin value (amounts, names, settings). Registered FIRST in
    # group 0 so a pending admin input always wins over the feature text
    # triggers.
    application.add_handler(
        MessageHandler(
            filters.TEXT
            & filters.Regex(f"^{admin_panel.ADMIN_PANEL_TEXT_TRIGGER}$"),
            admin_panel.admin_command,
        )
    )
    application.add_handler(
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    admin_panel.admin_input_entry,
                    pattern=rf"^{callbacks.ADM_IN_PREFIX}",
                )
            ],
            states={
                admin_panel.ADMIN_INPUT: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        admin_panel.admin_input_received,
                    ),
                    # Tapping any admin button mid-input cancels the input.
                    CallbackQueryHandler(
                        admin_panel.admin_callback, pattern=r"^adm_"
                    ),
                ],
            },
            fallbacks=[
                # No text fallback: "پنل" is plain TEXT, so mid-conversation
                # it is (correctly) treated as the pending input value.
                CallbackQueryHandler(
                    admin_panel.admin_input_cancel,
                    pattern=rf"^{callbacks.ADM_IN_CANCEL}$",
                ),
            ],
            name="admin_input",
            persistent=False,
            allow_reentry=True,
        )
    )

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

    # Land / Construction / Renovation — text messages
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(f"^{realestate.LANDS_MY_TEXT_TRIGGER}$"),
            realestate.lands_my_text_handler,
        )
    )
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(f"^{realestate.LANDS_MARKET_TEXT_TRIGGER}$"),
            realestate.lands_market_text_handler,
        )
    )
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(f"^{realestate.BUILD_TEXT_TRIGGER}$"),
            realestate.build_text_handler,
        )
    )
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(f"^{realestate.STATUS_TEXT_TRIGGER}$"),
            realestate.status_text_handler,
        )
    )
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(f"^{realestate.RENOVATE_TEXT_TRIGGER}$"),
            realestate.renovate_text_handler,
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

    # Land / Construction / Renovation callbacks — BEFORE the unknown fallback.
    application.add_handler(
        CallbackQueryHandler(
            realestate.show_my_lands, pattern=rf"^{callbacks.RE_LANDS_MY}$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            realestate.show_lands_market, pattern=rf"^{callbacks.RE_LANDS_MARKET}$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            realestate.show_land_info, pattern=rf"^{callbacks.RE_LAND_INFO_PREFIX}\d+$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            realestate.show_land_buy_confirmation,
            pattern=rf"^{callbacks.RE_LAND_BUY_PREFIX}\d+$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            realestate.confirm_land_buy,
            pattern=rf"^{callbacks.RE_LAND_BUY_OK_PREFIX}\d+$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            realestate.show_build_menu, pattern=rf"^{callbacks.RE_BUILD_MENU}$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            realestate.show_build_type_picker,
            pattern=rf"^{callbacks.RE_BUILD_LAND_PREFIX}\d+$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            realestate.show_build_step,
            pattern=rf"^{callbacks.RE_BUILD_SPEC_PREFIX}\d+_[av](?:_(?:\d+|[mge])){{0,4}}$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            realestate.show_construction_confirmation,
            pattern=rf"^{callbacks.RE_BUILD_CONFIRM_PREFIX}"
            rf"\d+_[av_0-9mge]+_P[01]E[01]S[01]$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            realestate.confirm_construction,
            pattern=rf"^{callbacks.RE_BUILD_EXEC_PREFIX}"
            rf"\d+_[av_0-9mge]+_P[01]E[01]S[01]$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            realestate.cancel_construction,
            pattern=rf"^{callbacks.RE_BUILD_CANCEL_PREFIX}\d+$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            realestate.show_status, pattern=rf"^{callbacks.RE_STATUS}$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            realestate.show_renov_menu, pattern=rf"^{callbacks.RE_RENOV_MENU}$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            realestate.show_renovation_options,
            pattern=rf"^{callbacks.RE_RENOV_OPTS_PREFIX}\d+$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            realestate.show_renovation_confirmation,
            pattern=rf"^{callbacks.RE_RENOV_CONFIRM_PREFIX}\d+_(?:q|k|ba|r|p|e|s|m)$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            realestate.confirm_renovation,
            pattern=rf"^{callbacks.RE_RENOV_OK_PREFIX}\d+_(?:q|k|ba|r|p|e|s|m)$",
        )
    )

    # Admin panel router — BEFORE the unknown fallback.
    application.add_handler(
        CallbackQueryHandler(admin_panel.admin_callback, pattern=r"^adm_")
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
