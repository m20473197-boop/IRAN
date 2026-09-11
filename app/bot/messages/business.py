"""Business system player-facing texts — natural, casual Persian.

Money amounts use the shared formatters; dates are shown as
``۱۴۰۴/۰۶/۲۱``-style strings (Persian digits, zero-padded).
"""

from __future__ import annotations

from datetime import date

from app.bot.messages.formatters import fa_int, money
from app.game.business.dto import (
    BusinessData,
    BusinessIncomeResult,
    BusinessOverview,
)
from app.game.business.rules import CatalogEntry

_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

# Buttons only make sense for open businesses.
_STATUS_LABELS = {"active": "🟢 باز", "closed": "⚪ تعطیل"}


def fa_date(day: date) -> str:
    return f"{day.year:04d}/{day.month:02d}/{day.day:02d}".translate(_DIGITS)


def business_menu_text() -> str:
    return (
        "🏪 کسب و کار:\n\n"
        "از این لیست یه مغازه یا کار انتخاب کن، سرمایه‌ش رو بدی و شروعش کنی.\n"
        "هر روز یه درآمد داره؛ درآمد می‌ره توی حسابِ خودِ کسب و کار، نه جیب تو!\n"
        "هر وقت سر زدی، «درآمد امروز» رو بزن تا درآمد روزت ثبت بشه 👇"
    )


def _catalog_line(entry: CatalogEntry) -> str:
    return (
        f"• {entry.name} — {entry.description}\n"
        f"  💵 هزینه شروع: {money(entry.startup_cost)}\n"
        f"  📈 درآمد روزانه: بین {money(entry.min_daily_income)} "
        f"تا {money(entry.max_daily_income)} (هر روز فرق می‌کنه)"
    )


def business_catalog_text(
    entries: tuple[CatalogEntry, ...],
    owned_count: int,
    max_owned: int,
    wallet_balance: int,
) -> str:
    lines = [f"🏪 کسب‌وکارهای موجود ({fa_int(owned_count)} از {fa_int(max_owned)} تا مال تو):\n"]
    if not entries:
        lines.append("الان هیچ کسب‌وکاری فعال نیست. 😕")
    for entry in entries:
        lines.append(_catalog_line(entry))
        lines.append("")
    lines.append(f"💳 موجودی تو: {money(wallet_balance)}")
    lines.append("روی اسم هر کاری که دلت می‌خواد بزن تا شروعش کنی 👇")
    return "\n".join(lines)


def business_confirm_text(entry: CatalogEntry, wallet_balance: int) -> str:
    short = max(0, entry.startup_cost - wallet_balance)
    lines = [
        f"❔ مطمئنی «{entry.name}» رو شروع می‌کنی؟",
        "",
        f"💵 باید همین الان {money(entry.startup_cost)} بدی.",
        f"📈 درآمدش هم روزی بین {money(entry.min_daily_income)} "
        f"تا {money(entry.max_daily_income)} — می‌ره تو حساب خودِ مغازه.",
        f"💳 موجودی فعلی تو: {money(wallet_balance)}",
    ]
    if short > 0:
        lines.append(f"⚠️ {money(short)} کم داری؛ نمی‌کشه. 😅")
    else:
        lines.append("✅ پولت می‌رسه.")
    return "\n".join(lines)


def business_started_text(entry_name: str, paid: int, wallet_balance_after: int) -> str:
    return (
        f"🎉 تبریک! «{entry_name}» راه افتاد.\n"
        f"💸 {money(paid)} از کیف پولت کم شد.\n"
        f"💳 موجودی فعلی‌ت: {money(wallet_balance_after)}\n"
        "هر روز یه سر بزن، درآمدش رو بگیر و ببین حسابت چقدر پر شده. 👌"
    )


def business_insufficient_text(required: int, balance: int, shortfall: int) -> str:
    return (
        "❌ پولت به این کسب و کار نمی‌رسه.\n\n"
        f"💵 هزینه شروع: {money(required)}\n"
        f"💳 موجودی تو: {money(balance)}\n"
        f"🧮 کم داری: {money(shortfall)}\n\n"
        "یه مدتی خر حمالی کن (💼) یا درآمد پس‌اندازت رو جمع کن و برگرد. 💪"
    )


def business_too_many_text(max_owned: int) -> str:
    return (
        f"⚠️ حداکثر {fa_int(max_owned)} تا کسب و کار می‌تونی داشته باشی.\n"
        "اول یکی رو ببند (بعداً اضافه می‌شه) یا با همونا ادامه بده."
    )


def business_invalid_type_text() -> str:
    return (
        "🤨 همچین کسب و کاری تو لیست نیست.\n"
        "فقط می‌تونی از همین گزینه‌های آماده انتخاب کنی."
    )


def _business_line(business: BusinessData, today: date | None) -> str:
    credited = today is not None and business.last_income_date == today
    last_bit = (
        f"آخرین درآمد: {money(business.last_income_amount)} "
        f"({fa_date(business.last_income_date)})"
        if business.last_income_date is not None
        else "هنوز درآمدی ثبت نشده"
    )
    lines = [
        f"🏪 {business.type_name} — {_STATUS_LABELS.get(business.status, business.status)}",
        f"  🏦 موجودی کسب و کار: {money(business.balance)}",
        f"  💵 هزینه شروع: {money(business.startup_cost)}",
        f"  📅 تاریخ شروع: {fa_date(business.created_at.date())}",
        f"  {last_bit}",
        f"  🧾 درآمد امروز: {'✅ اضافه شده' if credited else '⏳ هنوز گرفته نشده'}",
    ]
    return "\n".join(lines)


def my_businesses_text(overview: BusinessOverview) -> str:
    businesses = overview.businesses
    if not businesses:
        return (
            "💼 هنوز هیچ کسب و کاری نداری.\n"
            "از لیست کسب‌وکارها یکی رو انتخاب کن تا بهت پیشنهاد بدم 👇"
        )

    lines = [
        f"💼 کسب‌وکارهای من ({fa_int(len(businesses))} از {fa_int(overview.max_owned)} تا):\n"
    ]
    for business in businesses:
        lines.append(_business_line(business, overview.today))
        lines.append("")
    lines.append(f"🏦 جمع موجودی کسب‌وکارها: {money(overview.total_balance)}")
    if overview.today is not None and overview.today_income > 0:
        lines.append(
            f"🧮 درآمد امروزت (مجموع): {money(overview.today_income)}"
        )
    lines.append(f"💳 موجودی کیف پولت: {money(overview.wallet_balance)}")
    return "\n".join(lines)


def business_detail_text(business: BusinessData, today: date | None) -> str:
    lines = [_business_line(business, today)]
    if business.income_days > 0:
        lines.append(
            f"\n📊 مجموع درآمد این تا اینجا: {money(business.total_income)} "
            f"({fa_int(business.income_days)} روزِ پردرآمد)"
        )
    if business.description:
        lines.append(f"\n📝 {business.description}")
    lines.append("⚠️ فعلاً استخدام و حقوق پرسنل غیرفعاله — کسب و کار خودت می‌چرخه.")
    return "\n".join(lines)


def income_summary_text(results: list[BusinessIncomeResult], any_owned: bool) -> str:
    granted = [r for r in results if r.granted]
    already = [r for r in results if not r.granted]

    if not results:
        if not any_owned:
            return "💼 اول یه کسب و کار بزن، بعد درآمدش رو بگیر 😉"
        return "هیچ کسب و کار فعالی نداری که امروز درآمد بده. ⚪"

    lines: list[str] = []
    if granted:
        total = sum(r.amount for r in granted)
        lines.append(f"🧮 درآمد امروز {fa_int(len(granted))} کسب و کار اضافه شد:\n")
        for r in granted:
            lines.append(
                f"🏪 {r.type_name}: +{money(r.amount)} "
                f"(موجودی الان: {money(r.balance_after)})"
            )
        lines.append(f"\n💰 جمع امروز: {money(total)} — تو حساب کسب‌وکارهاست، نه جیبت!")
    if already:
        for r in already:
            lines.append(f"⏳ {r.type_name}: درآمد امروزش قبلاً ثبت شده.")
    if not granted and already:
        lines.insert(0, "🔁 درآمد امروز رو گرفتی! فردا دوباره سر بزن. 😉")
    return "\n".join(lines)


def business_not_found_text() -> str:
    return "این کسب و کار پیدا نشد 🤷‍♂️"


def business_not_yours_text() -> str:
    return "⛔ این کسب و کار مال تو نیست!"
