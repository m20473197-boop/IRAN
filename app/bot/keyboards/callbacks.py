"""Callback data identifiers.

Single source of truth for inline-button callback values. Adding a future
screen means adding one constant here, one keyboard builder and one handler
— nothing else in the codebase changes.
"""

PROFILE: str = "profile"
STATUS: str = "status"
BACK_TO_MAIN: str = "back_main"

# Job system
JOBS_MENU: str = "jobs_menu"
JOBS_LIST: str = "jobs_list"
JOBS_MY_JOB: str = "jobs_my_job"
JOBS_SETTLE: str = "jobs_settle"
JOBS_LEAVE: str = "jobs_leave"
JOBS_APPLY_PREFIX: str = "jobs_apply_"  # + job_id
JOBS_HISTORY: str = "jobs_history"

# Housing / Real-estate system
HOUSING_MENU: str = "h_menu"
HOUSES_MY: str = "h_my"                    # my houses / assets
HOUSES_MARKET: str = "h_mkt"               # houses available for purchase
HOUSES_RENTALS: str = "h_rents"            # houses available for rent
HOUSES_MY_RENTS: str = "h_myrents"         # my rental contracts (as tenant)
HOUSE_INFO_PREFIX: str = "h_info_"         # + house_id
HOUSE_BUY_PREFIX: str = "h_buy_"           # + house_id (confirmation screen)
HOUSE_BUY_CONFIRM_PREFIX: str = "h_buyok_"  # + house_id (executes purchase)
HOUSE_SELL_OPTIONS_PREFIX: str = "h_sellopt_"  # + house_id (price presets)
HOUSE_SELL_SET_PREFIX: str = "h_sellset_"  # + house_id + _ + per_mille
HOUSE_SELL_CANCEL_PREFIX: str = "h_sellcancel_"  # + house_id
HOUSE_RENTOUT_OPTIONS_PREFIX: str = "h_rentopt_"  # + house_id (deposit presets)
HOUSE_RENT_SET_PREFIX: str = "h_rentset_"  # + house_id + _ + deposit_percent
HOUSE_RENT_CANCEL_PREFIX: str = "h_rentcancel_"  # + house_id
RENT_CONFIRM_PREFIX: str = "h_rentok_"     # + house_id (executes renting)
RENT_PAY_PREFIX: str = "h_rentpay_"        # + contract_id
RENT_END_PREFIX: str = "h_rentend_"        # + contract_id
