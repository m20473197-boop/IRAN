"""Player-facing Persian texts of the Marriage & Family system.

Every string the family commands can ever print lives here (the domain
module convention). The family system is command-only: these are replies to
the players' messages — no keyboards are built and no menu is touched.
"""

from __future__ import annotations

from app.bot.messages.formatters import fa_int, fa_year, money
from app.core import constants
from app.game.housing.construction_year import current_iranian_year


def _iranian_year(moment) -> str:
    """Solar-Hijri year of a datetime, in Persian digits (— when missing)."""
    return fa_year(current_iranian_year(moment)) if moment is not None else "—"
from app.game.family.dto import (
    CheatResult,
    DivorceRecordData,
    DivorceRequestResult,
    DivorceResult,
    FamilyHistoryEntry,
    FamilyInfoData,
    ForgiveResult,
    MarriageResult,
    ProposalResult,
    RelationshipResult,
)

# --- Proposals («ازدواج») -------------------------------------------------------


def usage_proposal() -> str:
    return (
        "برای خواستگاری، روی پیام طرف مقابل ریپلای کن و بنویس:\n"
        "«ازدواج»\n"
        "اختیاری — مهریه‌ات رو هم بچسبون: «ازدواج ۵۰۰۰۰۰»"
    )


def proposal_sent(result: ProposalResult) -> str:
    hours = max(1, constants.FAMILY_PROPOSAL_EXPIRY_SECONDS // 3600)
    return (
        f"💍 درخواست ازدواجت برای {result.target_display_name} ثبت شد!\n"
        f"مهریه: {money(result.proposal.mahr)}\n\n"
        f"تا {fa_int(hours)} ساعت منتظر جوابش باش — اگه «قبول» بده، "
        "زندگی مشترکتون شروع می‌شه."
    )


def target_proposal_received(result: ProposalResult) -> str:
    return (
        f"💍 {result.proposer_display_name} درخواست ازدواج داده!\n"
        f"مهریه پیشنهادی: {money(result.proposal.mahr)}\n\n"
        "برای قبول: «قبول»\n"
        "برای رد: «رد»"
    )


def no_pending_proposal() -> str:
    return "درخواست ازدواج بازی برات باز نیست. 🤷"


def proposal_accepted(result: MarriageResult) -> str:
    from app.game.housing.construction_year import current_iranian_year

    year = (
        fa_year(current_iranian_year(result.married_at))
        if result.married_at is not None
        else ""
    )
    xp = fa_int(constants.FAMILY_XP_FOR_MARRIAGE)
    return (
        "💍❤️ ازدواج‌تون رسمی شد!\n"
        f"{result.proposer_display_name} و {result.target_display_name} "
        "حالا زن و شوهر هستن.\n"
        f"تاریخ ازدواج: {year}\n"
        f"مهریه: {money(result.mahr)}\n"
        f"امتیاز رابطه: {fa_int(result.relationship_points)}\n\n"
        f"✨ {xp} XP بابت شروع زندگی مشترک گرفتی"
    )


def target_accepted_copy(partner_name: str) -> str:
    return f"✅ درخواست ازدوالت با {partner_name} قبول شد — حالا متأهل هستید! 💍"


def proposal_rejected(partner_name: str) -> str:
    return f"🙅 درخواست ازدواجت با {partner_name} رد شد."


def proposal_rejection_done() -> str:
    return "🙅 درخواست طرف مقابل رو رد کردی."


def proposal_busy() -> str:
    return "⏳ فعلاً یک درخواست ازدواج بین شما دو نفر باز است — اول جوابش مشخص بشه."


def target_already_married(name: str) -> str:
    return f"😕 {name} متأهله و نمی‌تونه دوباره ازدواج کنه."


def already_married_self() -> str:
    return "تو متأهلی! 🚫 اول باید جدا بشی («طلاق») و بعد می‌تونی ازدواج کنی."


def self_proposal() -> str:
    return "با خودت که نمی‌شه ازدواج کرد! 😅"


def not_registered_target() -> str:
    return "طرف مقابل هنوز ثبت‌نام نکرده — اول باید /start کنه. 🤔"


def level_too_low(name: str, level: int) -> str:
    return (
        f"🔒 برای ازدواج حداقل لول {fa_int(constants.FAMILY_MIN_LEVEL_TO_MARRY)} لازمه.\n"
        f"{name} الان لول {fa_int(level)} است."
    )


# --- Divorce («طلاق» / «بخشش») ----------------------------------------------------


def not_married() -> str:
    return "💔 تو متأهل نیستی که این کار رو بکنی."


def divorce_request_filed(result: DivorceRequestResult) -> str:
    hours = max(1, constants.FAMILY_DIVORCE_COOLDOWN_SECONDS // 3600)
    return (
        f"📄 درخواست طلاقت از {result.spouse_display_name} ثبت شد.\n"
        f"تا {fa_int(hours)} ساعت فرصت هست: ایشون می‌تونه «بخشش» بفرسته،\n"
        "یا هرکدوم دوباره «طلاق» بزنید تا جدایی قطعی بشه.\n"
        f"مهریه‌ای که موقع جدایی رد و بدل می‌شه: {money(result.mahr_required)}"
    )


def divorce_request_incoming(partner_name: str, result: DivorceRequestResult) -> str:
    return (
        f"⚠️ {partner_name} درخواست طلاق داده!\n"
        "می‌تونی «بخشش» بفرستی تا همه‌چی درست بشه،\n"
        "یا «طلاق» بفرستی تا جدایی قطعی بشه.\n"
        f"مهریه: {money(result.mahr_required)}"
    )


def divorce_finalized(result: DivorceResult) -> str:
    lines = [
        (
            f"⚖️ طلاق قطعی شد — {result.initiator_display_name} و "
            f"{result.other_display_name} از هم جدا شدند."
        )
    ]
    if result.mahr_waived:
        lines.append("مهریه‌ای در کار نبود.")
    elif result.cheater_liable:
        lines.append(
            f"به‌خاطر خیانت اثبات‌شده، مهریه {money(result.paid_amount)} "
            "از سمت خاطی پرداخت شد."
        )
        if result.unpaid_debt:
            lines.append(f"باقی‌مانده به‌عنوان بدهی ثبت شد: {money(result.unpaid_debt)}")
    else:
        lines.append(f"💸 مهریه {money(result.paid_amount)} پرداخت شد.")
        if result.unpaid_debt:
            lines.append(f"بدهی مهریه: {money(result.unpaid_debt)}")
    return "\n".join(lines)


def divorce_other_side_copy(result: DivorceResult) -> str:
    if result.payee_player_id == result.other_player_id and result.paid_amount > 0:
        return (
            "⚖️ طلاق شما قطعی شد.\n"
            f"مهریه {money(result.paid_amount)} به حسابت واریز شد."
        )
    if result.payer_player_id == result.other_player_id and result.paid_amount > 0:
        return (
            "⚖️ طلاق شما قطعی شد.\n"
            f"مهریه {money(result.paid_amount)} از حسابت پرداخت شد."
        )
    return "⚖️ طلاق شما قطعی شد."


def insufficient_mahr(mahr: int, balance: int, shortfall: int) -> str:
    return (
        "🚫 برای طلاق باید مهریه رو پرداخت کنی:\n"
        f"مهریه: {money(mahr)}\n"
        f"موجودی تو: {money(balance)}\n"
        f"کم داری: {money(shortfall)} — اول یه کم پول در بیاور! 💼"
    )


def forgiven(result: ForgiveResult) -> str:
    return (
        "🕊 بخشیدی! درخواست طلاق لغو شد.\n"
        f"امتیاز رابطه: {fa_int(result.relationship_points_before)} ← "
        f"{fa_int(result.relationship_points_after)}"
    )


def forgiveness_copy(partner_name: str, result: ForgiveResult) -> str:
    return (
        f"🕊 {partner_name} بخشیدت — درخواست طلاق لغو شد.\n"
        f"امتیاز رابطه الان {fa_int(result.relationship_points_after)} است."
    )


def nothing_to_forgive() -> str:
    return "درخواست طلاقی باز نیست که بخوای ببخشیدی. 🤷"


def cannot_forgive_own() -> str:
    return "نمی‌تونی درخواست طلاق خودت رو ببخشی! 😅"


# --- Cheating («خیانت») -------------------------------------------------------------


def cheat_attempt_result(result: CheatResult) -> str:
    if not result.succeeded and not result.discovered:
        return "🤫 هیچ‌چی از آب درنیومد… فعلاً."
    if result.succeeded and not result.discovered:
        return "🤫 آروم رفت — لو نرفت. (فعلاً)"
    if not result.succeeded and result.discovered:
        lines = ["😱 شک کردن! چیزی ثابت نشد ولی فضا داغ شد."]
    else:
        lines = ["😱 لو رفتی!!!"]
    lines.append(
        f"💔 امتیاز رابطه: {fa_int(result.relationship_points_before)} ← "
        f"{fa_int(result.relationship_points_after)}"
    )
    if result.penalty_money:
        lines.append(f"💸 جریمه اجتماعی: {money(result.penalty_money)}")
    if result.penalty_xp:
        lines.append(f"✨ {fa_int(result.penalty_xp)} XP از اعتبارت رفت")
    if result.divorce_possible:
        lines.append(
            "⚖️ رابطه به تهش رسید — همسرت «طلاق» بده، مهریه گردن توئه!"
        )
    else:
        lines.append("⚖️ همسرت الان می‌تونه «طلاق» بخواد.")
    return "\n".join(lines)


def spouse_cheat_notification(cheater_name: str, result: CheatResult) -> str:
    lines = [
        f"🤫 یه خبر بد بهت رسید… گفته می‌شه {cheater_name} بهت خیانت کرده.",
        f"💔 امتیاز رابطه‌تون: {fa_int(result.relationship_points_after)}",
    ]
    if result.divorce_possible:
        lines.append("با یه «طلاق» می‌تونی جدا بشی — مهریه هم گردن طرف خاطیه.")
    else:
        lines.append("می‌تونی «طلاق» بدی یا اگه ببخشیدیش «بخشش» بفرستی.")
    return "\n".join(lines)


def not_married_cheat() -> str:
    return "🤫 خیانت فقط برای آدم متأهل معنا داره!"


def cheat_too_soon(wait_seconds: int) -> str:
    return f"🕐 فعلاً نه — {fa_int(max(1, wait_seconds // 60))} دقیقه صبر کن."


# --- Relationship («رابطه») ----------------------------------------------------------


def relationship_event(result: RelationshipResult) -> str:
    return (
        f"❤️ یک لحظه دونفره با {result.partner_display_name}.\n"
        f"📈 امتیاز رابطه: {fa_int(result.satisfaction)}"
    )


def relationship_pregnancy(result: RelationshipResult) -> str:
    return (
        f"❤️ یک لحظه دونفره با {result.partner_display_name}.\n"
        f"📈 امتیاز رابطه: {fa_int(result.satisfaction)}\n\n"
        "🍼 خبر بزرگ! همسرت بارداره…"
    )


def relationship_birth(result: RelationshipResult, children_count: int) -> str:
    child = result.child
    assert child is not None  # only called for a birth result
    return (
        f"❤️ یک لحظه دونفره با {result.partner_display_name}.\n"
        f"📈 امتیاز رابطه: {fa_int(result.satisfaction)}\n\n"
        f"🍼🎉 فرزندتون به دنیا اومد: {child.name} "
        f"({'دختر' if child.gender == 'girl' else 'پسر'})\n"
        f"شناسه فرزند: {fa_int(child.id)}\n"
        f"👶 تعداد فرزندان: {fa_int(children_count)}\n"
        f"✨ {fa_int(constants.FAMILY_XP_FOR_CHILD_BIRTH)} XP برای هر دوتون"
    )


def relationship_too_soon(wait_seconds: int) -> str:
    return f"🕐 برای رابطه بعدی {fa_int(max(1, wait_seconds // 60))} دقیقه صبر کن."


def not_spouse_reply() -> str:
    return "😐 برای «رابطه» باید روی پیام همسرت ریپلای کنی."


def partner_copy_birth(child_name: str) -> str:
    return f"🍼 فرزندتون {child_name} به دنیا اومد! تبریک 🎉"


# --- Family info («خانواده») ---------------------------------------------------------

_STATUS_LABELS = {
    "single": "مجرد",
    "married": "متأهل 💍",
    "divorced": "مطلقه 💔",
}


def family_info_text(info: FamilyInfoData) -> str:
    lines = [
        f"👨‍👩‍👧 اطلاعات خانواده — {info.display_name}",
        "━━━━━━━━━━━━━━━",
        f"💍 وضعیت تأهل: {_STATUS_LABELS.get(info.marriage_status, info.marriage_status)}",
    ]
    if info.marriage_status == "married" and info.spouse_display_name:
        since = ""
        if info.married_at is not None:
            from app.game.housing.construction_year import current_iranian_year

            since = f" — از سال {fa_year(current_iranian_year(info.married_at))}"

        lines.append(f"❤️ همسر: {info.spouse_display_name}{since}")
        lines.append(f"💰 مهریه (ثبت‌شده): {money(info.mahr)}")
        lines.append(f"🌡 امتیاز رابطه: {fa_int(info.relationship_points)}")
        if info.cheating_count:
            lines.append(f"🕵 خیانت‌های لو‌رفته: {fa_int(info.cheating_count)}")
    if info.divorce_requested_by_spouse:
        lines.append("⚠️ همسرت درخواست طلاق داده — «طلاق» = قطعی، «بخشش» = بازگشت")
    elif info.divorce_pending_by_me:
        lines.append("📄 درخواست طلاق تو باز است — منتظر «بخشش» یا «طلاق» طرف مقابل")
    lines.append(f"👶 فرزندان: {fa_int(info.children_count)}")
    for child in info.children[:10]:
        birth_year = _iranian_year(child.birth_date)
        lines.append(
            f"  • {child.name} ({'دختر' if child.gender == 'girl' else 'پسر'}) — تولد {birth_year}"
        )
    return "\n".join(lines)


def divorce_history_text(records: list[DivorceRecordData]) -> str:
    if not records:
        return "📜 سابقه طلاقی نداری."
    lines = ["📜 سابقه طلاق‌ها:"]
    for record in records:
        debt = f"، بدهی {money(record.unpaid_debt)}" if record.unpaid_debt else ""
        reason = f" ({record.reason})" if record.reason and record.reason != "divorced" else ""
        lines.append(
            f"• {record.initiator_display_name} ← {record.other_display_name} — "
            f"مهریه {money(record.mahr)}، پرداختی {money(record.paid_amount)}{debt}{reason}"
        )
    return "\n".join(lines)


def family_history_text(entries: list[FamilyHistoryEntry]) -> str:
    if not entries:
        return "📜 هنوز اتفاقی در پرونده خانواده‌ات ثبت نشده."
    lines = ["📜 آخرین رویدادهای خانوادگی:"]
    for entry in entries:
        when = entry.created_at.strftime("%m/%d %H:%M") if entry.created_at else ""
        lines.append(f"• [{when}] {entry.details}")
    return "\n".join(lines)
