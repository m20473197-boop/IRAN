"""Family command-handler tests — Telegram layer simulated, real services.

Same convention as ``test_handlers.py``: PTB Update/Message objects are
constructed by hand and the handlers run against the real service/repository/
database stack. The family system has no buttons — everything here is a text
message, exactly like players will send it.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Chat, Message, Update, User

from app.bot.handlers import family
from app.core import constants
from app.game.family.family import FixedRandom


# --- Telegram simulation helpers ------------------------------------------------


def make_user(tg_id: int, first_name: str = "آرش", username: str | None = None) -> User:
    return User(id=tg_id, first_name=first_name, is_bot=False, username=username)


def make_message(user: User, text: str, reply_to: Message | None = None) -> Message:
    return Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=user.id, type=Chat.PRIVATE),
        from_user=user,
        text=text,
        reply_to_message=reply_to,
    )


def make_update(message: Message) -> Update:
    return Update(update_id=1, message=message)


def make_context(services) -> MagicMock:
    context = MagicMock()
    context.application.bot_data = {"services": services}
    context.bot.send_message = AsyncMock()
    return context


@pytest.fixture
def replies(monkeypatch):
    """Capture every reply_text the bot sends in the player's chat."""
    sent: list[tuple[int, dict]] = []

    async def fake_reply_text(self, text=None, **kwargs):
        sent.append((self.chat_id, {"text": text, **kwargs}))
        return None

    monkeypatch.setattr(Message, "reply_text", fake_reply_text)
    return sent


def last_text(sent: list[tuple[int, dict]]) -> str:
    return sent[-1][1]["text"]


def texts_for(sent: list[tuple[int, dict]], chat_id: int) -> list[str]:
    return [payload["text"] for cid, payload in sent if cid == chat_id]


async def register_player(services, tg_id: int, name: str, *, level: int = 5) -> int:
    result = await services.players.register_or_get(
        telegram_user_id=tg_id, username=name, display_name=name
    )
    if level > 1:
        await services.levels.set_level(result.player_id, level)
    return result.player_id


async def marry_via_handlers(services, context, sent, *, a_tg=8101, b_tg=8102, mahr=300_000):
    """Run the real command flow: «ازدواج» (reply) → «قبول» (reply).

    Callers pick the Telegram ids; both players must already be registered.
    """
    a_user = make_user(a_tg, "آرش")
    b_user = make_user(b_tg, "مریم")
    b_msg = make_message(b_user, "سلام بچه‌ها")

    await family.marry_text_handler(
        make_update(
            make_message(a_user, f"ازدواج {mahr}" if mahr else "ازدواج", reply_to=b_msg),
        ),
        context,
    )
    assert any("ثبت شد" in t for t in texts_for(sent, a_tg)), texts_for(sent, a_tg)
    assert any(
        "درخواست ازدواج" in call.kwargs.get("text", "")
        for call in context.bot.send_message.await_args_list
    )

    await family.accept_proposal_text_handler(
        make_update(make_message(b_user, "قبول")), context
    )
    assert any("رسمی شد" in t for t in texts_for(sent, b_tg)), texts_for(sent, b_tg)


# === «ازدواج» → «قبول» ==============================================================


async def test_proposal_accept_flow_through_commands(services, monkeypatch, replies):
    services.family.set_rng(FixedRandom(always="fail"))
    context = make_context(services)
    a_id = await register_player(services, 8101, "آرش")
    await register_player(services, 8102, "مریم")

    await marry_via_handlers(services, context, replies, a_tg=8101, b_tg=8102)

    profile = await services.players.get_profile(8101)
    assert profile.marriage_status == "married"
    assert profile.spouse_display_name == "مریم"
    assert profile.children_count == 0

    # the custom Mahriyeh from «ازدواج 300000» is stored on the marriage
    info = await services.family.get_family_info(a_id)
    assert info.mahr == 300_000
    assert info.married_at is not None


async def test_proposal_auto_registers_reply_target(services, monkeypatch, replies):
    services.family.set_rng(FixedRandom(always="fail"))
    context = make_context(services)
    await register_player(services, 8111, "م" * 3)

    stranger_msg = make_message(make_user(8112, "ناشناس"), "hi")
    await family.marry_text_handler(
        make_update(make_message(make_user(8111, "م" * 3), "ازدواج", reply_to=stranger_msg)),
        context,
    )
    assert any("ثبت شد" in t for t in texts_for(replies, 8111))
    # the target now exists in the player system and received the proposal
    profile = await services.players.get_profile(8112)
    assert profile is not None and profile.display_name == "ناشناس"
    sent_texts = [c.kwargs["text"] for c in context.bot.send_message.await_args_list]
    assert any("درخواست ازدواج داده" in t for t in sent_texts)


async def test_proposal_without_reply_shows_usage(services, replies):
    context = make_context(services)
    await register_player(services, 8121, "م")
    await family.marry_text_handler(
        make_update(make_message(make_user(8121, "م"), "ازدواج")), context
    )
    assert "ریپلای" in last_text(replies)


async def test_self_proposal_message(services, replies):
    context = make_context(services)
    await register_player(services, 8131, "خودی")
    me_msg = make_message(make_user(8131, "خودی"), "سلام")
    await family.marry_text_handler(
        make_update(make_message(make_user(8131, "خودی"), "ازدواج", reply_to=me_msg)), context
    )
    assert "خودت" in last_text(replies)


# === «رد» ==========================================================================


async def test_reject_flow_notifies_proposer(services, replies):
    services.family.set_rng(FixedRandom(always="fail"))
    context = make_context(services)
    await register_player(services, 8141, "م")
    await register_player(services, 8142, "ز")

    b_msg = make_message(make_user(8142, "ز"), "hi")
    await family.marry_text_handler(
        make_update(make_message(make_user(8141, "م"), "ازدواج", reply_to=b_msg)), context
    )
    await family.reject_proposal_text_handler(
        make_update(make_message(make_user(8142, "ز"), "رد")), context
    )
    assert "رد کردی" in last_text(replies)
    proposer_notified = [
        c.kwargs["text"]
        for c in context.bot.send_message.await_args_list
        if c.kwargs["chat_id"] == 8141
    ]
    assert any("رد شد" in t for t in proposer_notified)

    # nothing left to accept afterwards
    await family.accept_proposal_text_handler(
        make_update(make_message(make_user(8142, "ز"), "قبول")), context
    )
    assert "باز نیست" in last_text(replies)


# === Married restrictions ===========================================================


async def test_married_player_cannot_propose_again(services, replies):
    services.family.set_rng(FixedRandom(always="fail"))
    context = make_context(services)
    await register_player(services, 8151, "م")
    await register_player(services, 8152, "ز")
    await register_player(services, 8153, "س")

    await marry_via_handlers(services, context, replies, a_tg=8151, b_tg=8152)

    third_msg = make_message(make_user(8153, "س"), "hello")
    await family.marry_text_handler(
        make_update(make_message(make_user(8151, "م"), "ازدواج", reply_to=third_msg)), context
    )
    assert "متأهلی" in texts_for(replies, 8151)[-1]

    # …and the target being married is reported as such.
    await family.marry_text_handler(
        make_update(
            make_message(
                make_user(8153, "س"), "ازدواج",
                reply_to=make_message(make_user(8151, "م"), "hi"),
            )
        ),
        context,
    )
    assert "متأهله" in texts_for(replies, 8153)[-1]


# === «طلاق» ========================================================================


async def test_divorce_two_step_flow_with_wallet_message(services, replies):
    services.family.set_rng(FixedRandom(always="fail"))
    context = make_context(services)
    await register_player(services, 8161, "م")
    await register_player(services, 8162, "ز")
    a_id = await register_player(services, 8161, "م")
    await services.money.add_money(a_id, 2_000_000)

    await marry_via_handlers(services, context, replies, a_tg=8161, b_tg=8162)

    await family.divorce_text_handler(
        make_update(make_message(make_user(8161, "م"), "طلاق")), context
    )
    assert "درخواست طلاقت" in texts_for(replies, 8161)[-1]
    # the spouse is privately informed about the request
    spouse_notices = [
        c.kwargs["text"]
        for c in context.bot.send_message.await_args_list
        if c.kwargs["chat_id"] == 8162
    ]
    assert any("درخواست طلاق داده" in t for t in spouse_notices)

    await family.divorce_text_handler(
        make_update(make_message(make_user(8161, "م"), "طلاق")), context
    )
    final = texts_for(replies, 8161)[-1]
    assert "طلاق قطعی شد" in final
    assert "مهریه" in final  # + exact wallet movement asserted below

    profile = await services.players.get_profile(8161)
    assert profile.marriage_status == "divorced"
    assert await services.money.get_balance(a_id) == 2_000_000 - 300_000


async def test_divorce_blocked_shows_required_amount(services, replies):
    services.family.set_rng(FixedRandom(always="fail"))
    context = make_context(services)
    await register_player(services, 8171, "م")
    await register_player(services, 8172, "ز")

    b_msg = make_message(make_user(8172, "ز"), "hi")
    await family.marry_text_handler(
        make_update(make_message(make_user(8171, "م"), "ازدواج 5000000", reply_to=b_msg)), context
    )
    await family.accept_proposal_text_handler(
        make_update(make_message(make_user(8172, "ز"), "قبول")), context
    )

    await family.divorce_text_handler(
        make_update(make_message(make_user(8171, "م"), "طلاق")), context
    )
    await family.divorce_text_handler(
        make_update(make_message(make_user(8171, "م"), "طلاق")), context
    )
    text = texts_for(replies, 8171)[-1]
    assert "کم داری" in text and "تومان" in text

    # still married
    profile = await services.players.get_profile(8171)
    assert profile.marriage_status == "married"


async def test_forgive_cancels_divorce_and_notifies_requester(services, replies):
    services.family.set_rng(FixedRandom(always="fail"))
    context = make_context(services)
    await register_player(services, 8181, "م")
    await register_player(services, 8182, "ز")
    await marry_via_handlers(services, context, replies, a_tg=8181, b_tg=8182)

    await family.divorce_text_handler(
        make_update(make_message(make_user(8181, "م"), "طلاق")), context
    )
    await family.forgive_text_handler(
        make_update(make_message(make_user(8182, "ز"), "بخشش")), context
    )
    assert "بخشیدی" in texts_for(replies, 8182)[-1]
    notices = [
        c.kwargs["text"]
        for c in context.bot.send_message.await_args_list
        if c.kwargs["chat_id"] == 8181
    ]
    assert any("بخشیدت" in t for t in notices)
    profile = await services.players.get_profile(8181)
    assert profile.marriage_status == "married"


async def test_divorce_when_single(services, replies):
    context = make_context(services)
    await register_player(services, 8191, "مجرد")
    await family.divorce_text_handler(
        make_update(make_message(make_user(8191, "مجرد"), "طلاق")), context
    )
    assert "متأهل نیستی" in last_text(replies)


# === «خیانت» — secret ===============================================================


async def test_cheat_is_hidden_and_only_author_is_answered(services, replies):
    services.family.set_rng(FixedRandom(always="fail"))
    context = make_context(services)
    await register_player(services, 8201, "م")
    await register_player(services, 8202, "ز")
    await marry_via_handlers(services, context, replies, a_tg=8201, b_tg=8202)
    context.bot.send_message.reset_mock()

    services.family.set_rng(FixedRandom(always="fail"))  # nobody finds out
    await family.cheat_text_handler(
        make_update(make_message(make_user(8201, "م"), "خیانت")), context
    )
    assert "هیچ‌چی" in last_text(replies)
    # secret: no notification was sent to anyone
    context.bot.send_message.assert_not_awaited()


async def test_cheat_discovery_notifies_spouse_privately(services, replies):
    services.family.set_rng(FixedRandom(always="fail"))
    context = make_context(services)
    await register_player(services, 8211, "م")
    await register_player(services, 8212, "ز")
    a_id = await register_player(services, 8211, "م")
    await services.money.add_money(a_id, 1_000_000)
    await marry_via_handlers(services, context, replies, a_tg=8211, b_tg=8212)
    context.bot.send_message.reset_mock()

    services.family.set_rng(FixedRandom(always="success"))  # discovered
    await family.cheat_text_handler(
        make_update(make_message(make_user(8211, "م"), "خیانت")), context
    )
    assert "لو رفتی" in last_text(replies)
    spouse_notices = [
        c.kwargs["text"]
        for c in context.bot.send_message.await_args_list
        if c.kwargs["chat_id"] == 8212
    ]
    assert any("خیانت کرده" in t for t in spouse_notices)
    # wallet penalty went through the wallet system
    assert await services.money.get_balance(a_id) == 1_000_000 - constants.FAMILY_CHEAT_SOCIAL_FINE


async def test_cheat_requires_marriage(services, replies):
    context = make_context(services)
    await register_player(services, 8221, "مجرد")
    await family.cheat_text_handler(
        make_update(make_message(make_user(8221, "مجرد"), "خیانت")), context
    )
    assert "متأهل" in last_text(replies)


# === «رابطه» ==========================================================================


async def test_relationship_with_spouse_reply_creates_child(services, replies):
    context = make_context(services)
    a_id = await register_player(services, 8231, "م")
    await register_player(services, 8232, "ز")
    await marry_via_handlers(services, context, replies, a_tg=8231, b_tg=8232)

    services.family.set_rng(FixedRandom(always="success"))  # pregnancy: yes
    spouse_msg = make_message(make_user(8232, "ز"), "عزیزم")
    await family.relationship_text_handler(
        make_update(make_message(make_user(8231, "م"), "رابطه", reply_to=spouse_msg)), context
    )
    text = texts_for(replies, 8231)[-1]
    assert "فرزندتون به دنیا اومد" in text

    info = await services.family.get_family_info(a_id)
    assert info.children_count == 1

    # the other parent is privately congratulated
    notices = [
        c.kwargs["text"]
        for c in context.bot.send_message.await_args_list
        if c.kwargs["chat_id"] == 8232
    ]
    assert any("به دنیا اومد" in t for t in notices)


async def test_relationship_reply_to_stranger_is_refused(services, replies):
    services.family.set_rng(FixedRandom(always="fail"))
    context = make_context(services)
    await register_player(services, 8241, "م")
    await register_player(services, 8242, "ز")
    await register_player(services, 8243, "غریبه")
    await marry_via_handlers(services, context, replies, a_tg=8241, b_tg=8242)

    stranger_msg = make_message(make_user(8243, "غریبه"), "hi")
    await family.relationship_text_handler(
        make_update(make_message(make_user(8241, "م"), "رابطه", reply_to=stranger_msg)), context
    )
    assert "همسرت" in texts_for(replies, 8241)[-1]


async def test_relationship_requires_marriage(services, replies):
    context = make_context(services)
    await register_player(services, 8251, "مجرد")
    await family.relationship_text_handler(
        make_update(make_message(make_user(8251, "مجرد"), "رابطه")), context
    )
    assert "متأهل نیستی" in last_text(replies)


# === «خانواده» / history screens ======================================================


async def test_family_info_screen(services, replies):
    services.family.set_rng(FixedRandom(always="fail"))
    context = make_context(services)
    await register_player(services, 8261, "م")
    await register_player(services, 8262, "ز")
    await marry_via_handlers(services, context, replies, a_tg=8261, b_tg=8262)

    await family.family_info_text_handler(
        make_update(make_message(make_user(8261, "م"), "خانواده")), context
    )
    text = texts_for(replies, 8261)[-1]
    assert "وضعیت تأهل" in text and "همسر" in text and "مهریه" in text
    assert "۱۴۰" in text  # Solar-Hijri marriage year, not Gregorian

    await family.family_history_text_handler(
        make_update(make_message(make_user(8261, "م"), "تاریخچه خانواده")), context
    )
    assert "ازدواج" in texts_for(replies, 8261)[-1]

    await family.divorce_history_text_handler(
        make_update(make_message(make_user(8261, "م"), "سابقه طلاق")), context
    )
    assert "سابقه طلاقی نداری" in texts_for(replies, 8261)[-1]


async def test_unregistered_player_gets_register_hint(services, replies):
    context = make_context(services)
    await family.divorce_text_handler(
        make_update(make_message(make_user(89_999, "غ"), "طلاق")), context
    )
    assert "ثبت‌نام" in last_text(replies)
