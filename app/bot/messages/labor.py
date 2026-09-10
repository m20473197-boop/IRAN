"""Labor system player-facing texts."""

from __future__ import annotations

from app.bot.messages.formatters import fa_int, money


def labor_success_text(reward: int, balance_after: int) -> str:
    """Simple success message — no motivational fluff."""
    return (
        "کارگری انجام شد.\n"
        f"💰 {money(reward)} به حسابت اضافه شد."
    )


def labor_cooldown_text(remaining_seconds: int) -> str:
    """Cooldown message with remaining time."""
    # Format remaining as minutes
    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60

    if minutes > 0 and seconds > 0:
        time_str = f"{fa_int(minutes)} دقیقه و {fa_int(seconds)} ثانیه"
    elif minutes > 0:
        time_str = f"{fa_int(minutes)} دقیقه"
    else:
        # If less than 60 seconds, show seconds
        if seconds <= 0:
            seconds = 1
        time_str = f"{fa_int(seconds)} ثانیه"

    return (
        "هنوز زمان کارگری نرسیده.\n"
        f"⏳ زمان باقی‌مانده: {time_str}"
    )


def labor_not_registered_text() -> str:
    """When user tries labor without registration."""
    return "هنوز ثبت‌نام نکردی! 🤔\nبا /start شروع کن."


def labor_error_text() -> str:
    """Generic error for labor."""
    return "خطایی پیش اومد، دوباره امتحان کن."
