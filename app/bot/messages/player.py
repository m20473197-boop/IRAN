"""Player-facing texts for the player domain (welcome, profile, status)."""

from __future__ import annotations

from app.bot.messages.formatters import fa_int, money
from app.game.player.dto import ProfileData, StatusData


def welcome_new_player(profile: ProfileData) -> str:
    """First-time ``/start`` greeting."""
    return (
        f"سلام {profile.display_name} جان! 🎉\n"
        "به شهر خوش اومدی! زندگی دومت از همین‌جا شروع می‌شه 😎\n\n"
        "یه پروفایل تازه هم برات ساختم؛ همه‌چی از صفر شروع می‌شه.\n"
        "از منوی پایین یه گزینه انتخاب کن 👇"
    )


def welcome_back_player(profile: ProfileData) -> str:
    """Greeting for returning players (no duplicate profile is created)."""
    return (
        f"سلام {profile.display_name}! 👋\n"
        "خوش برگشتی، جا برایت خالی بود 😄\n\n"
        "از منوی پایین ادامه بده 👇"
    )


def profile_text(profile: ProfileData) -> str:
    """The profile screen."""
    return (
        f"👤 پروفایل {profile.display_name}\n"
        "━━━━━━━━━━━━━━━\n"
        f"⭐ لول: {fa_int(profile.level)}\n"
        f"✨ XP: {fa_int(profile.xp)}\n"
        f"💰 موجودی: {money(profile.money)}\n"
        "━━━━━━━━━━━━━━━\n"
        f"{level_comment(profile.level)}"
    )


def status_text(status: StatusData) -> str:
    """The status screen (kept separate from Profile for future stats)."""
    return (
        "📊 وضعیت فعلیت:\n\n"
        f"⭐ لول: {fa_int(status.level)}\n"
        f"✨ XP: {fa_int(status.xp)}\n"
        f"💰 موجودی: {money(status.money)}"
    )


def level_comment(level: int) -> str:
    """A touch of flavour so the profile feels alive, not robotic."""
    if level < 3:
        return "هنوز اول راهی، ولی شروع خوبی بوده 😎"
    if level < 6:
        return "داری کم‌کم یه رونق حسابی راه می‌ندازی 👏"
    if level < 11:
        return "این شهر کم‌کم اسمت رو می‌شنوه 🔥"
    return "تو دیگه از چهره‌های همیشگی این شهری 👑"
