"""Job system player-facing texts — simple, no motivational fluff."""

from __future__ import annotations

from app.bot.messages.formatters import fa_int, money
from app.game.player.dto import JobData, JobHistoryData, PlayerJobData


def jobs_menu_text() -> str:
    return (
        "💼 منوی شغل‌ها:\n\n"
        "از اینجا می‌تونی شغل انتخاب کنی، کار کنی و درآمد بگیری.\n"
        "یک گزینه رو انتخاب کن 👇"
    )


def jobs_list_text(jobs: list[JobData]) -> str:
    if not jobs:
        return "هیچ شغل فعالی موجود نیست."

    lines = ["📋 لیست شغل‌های موجود:\n"]
    for job in jobs:
        lines.append(
            f"• {job.name}\n"
            f"  {job.description}\n"
            f"  💰 حقوق: {money(job.salary)}\n"
            f"  ⏱️ وقفه: {job.cooldown // 60} دقیقه\n"
            f"  ⭐ لول مورد نیاز: {fa_int(job.required_level)}\n"
        )
    lines.append("برای انتخاب شغل، روی دکمه مربوطه بزن 👇")
    return "\n".join(lines)


def my_job_text(player_job: PlayerJobData | None) -> str:
    if player_job is None:
        return "شغلی نداری.\nاز لیست شغل‌ها یکی رو انتخاب کن."

    last_work = "هرگز"
    if player_job.last_work_time:
        last_work = player_job.last_work_time.strftime("%Y-%m-%d %H:%M")

    return (
        f"👔 شغل فعلیت: {player_job.job_name}\n"
        f"📝 {player_job.job_description}\n"
        f"💰 حقوق هر کار: {money(player_job.salary)}\n"
        f"⏱️ وقفه: {player_job.cooldown // 60} دقیقه\n"
        f"📅 شروع: {player_job.started_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"🔨 آخرین کار: {last_work}\n"
        f"💵 کل درآمد از این شغل: {money(player_job.total_earnings)}"
    )


def job_applied_success(job_name: str) -> str:
    return f"شغل {job_name} با موفقیت انتخاب شد."


def job_apply_error(message: str) -> str:
    return f"❌ {message}"


def job_work_success(income: int, balance_after: int) -> str:
    return (
        "کار انجام شد.\n"
        f"💰 درآمد: {money(income)}\n"
        f"💳 موجودی فعلی: {money(balance_after)}"
    )


def job_work_cooldown(remaining_seconds: int) -> str:
    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60
    if minutes > 0 and seconds > 0:
        time_str = f"{fa_int(minutes)} دقیقه و {fa_int(seconds)} ثانیه"
    elif minutes > 0:
        time_str = f"{fa_int(minutes)} دقیقه"
    else:
        time_str = f"{fa_int(seconds if seconds > 0 else 1)} ثانیه"

    return (
        "هنوز زمان کار نرسیده.\n"
        f"⏳ زمان باقی‌مانده: {time_str}"
    )


def job_no_job() -> str:
    return "شغلی نداری.\nاز لیست شغل‌ها یکی رو انتخاب کن."


def job_leave_success(job_name: str, total_earnings: int) -> str:
    return (
        f"شغل {job_name} ترک شد.\n"
        f"💵 کل درآمد از این شغل: {money(total_earnings)}"
    )


def job_history_text(histories: list[JobHistoryData]) -> str:
    if not histories:
        return "تاریخچه درآمد خالیه."

    lines = [f"📜 تاریخچه درآمد (آخرین {len(histories)}):\n"]
    for h in histories:
        lines.append(
            f"• {h.job_name}: {money(h.income)} - {h.created_at.strftime('%Y-%m-%d %H:%M')}"
        )
    return "\n".join(lines)


def job_not_found() -> str:
    return "شغل مورد نظر پیدا نشد."
