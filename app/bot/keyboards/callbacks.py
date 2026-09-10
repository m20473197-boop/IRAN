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
