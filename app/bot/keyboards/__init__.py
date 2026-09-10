"""Inline keyboard builders and callback identifiers."""

from app.bot.keyboards import callbacks
from app.bot.keyboards.housing import (
    build_buy_confirmation,
    build_house_info,
    build_housing_menu,
    build_market_list,
    build_my_houses,
    build_my_rents,
    build_rent_confirmation,
    build_rent_options,
    build_rentals_list,
    build_sale_price_options,
)
from app.bot.keyboards.main_menu import (
    BUTTON_HOUSING,
    build_back_to_main,
    build_jobs_list,
    build_jobs_menu,
    build_main_menu,
)

__all__ = [
    "callbacks",
    "build_back_to_main",
    "build_main_menu",
    "build_jobs_menu",
    "build_jobs_list",
    "BUTTON_HOUSING",
    "build_housing_menu",
    "build_market_list",
    "build_rentals_list",
    "build_my_houses",
    "build_my_rents",
    "build_house_info",
    "build_buy_confirmation",
    "build_rent_confirmation",
    "build_sale_price_options",
    "build_rent_options",
]
