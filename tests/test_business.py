"""Business System tests — predefined catalog, wallet-paid starts, daily income.

Covers: viewing the catalog, starting valid/invalid businesses, insufficient
funds, exact startup-cost deduction through the wallet, ownership rules,
variable once-per-day income credited to the business balance, and the
handlers behind the inline menu. Employee hiring is intentionally absent —
a test asserts the system keeps working without it.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User

from app.bot.handlers import business as business_handlers
from app.core import constants
from app.database.models.business import Business
from app.database.repositories.business_repository import BusinessRepository
from app.game.business import rules
from app.services.business_service import (
    BusinessFundsError,
    BusinessNotFoundError,
    BusinessTypeNotFoundError,
    BusinessUnavailableError,
    BusinessService,
    NotBusinessOwnerError,
    TooManyBusinessesError,
)

# Fixed "now" far from any Tehran midnight — the business day is unambiguous.
DAY1 = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
DAY2 = DAY1 + timedelta(days=1)
DAY3 = DAY1 + timedelta(days=2)


class ConstRng:
    """Scripted dice: always picks the low/high/middle of the rolled band."""

    def __init__(self, pick: str = "low"):
        self.pick = pick

    def randint(self, a: int, b: int) -> int:
        if self.pick == "low":
            return a
        if self.pick == "high":
            return b
        return (a + b) // 2


async def _fund(services, player_id: int, amount: int) -> None:
    await services.money.add_money(player_id, amount)


def _entry(key: str):
    return rules.catalog_item(key)


# --- The predefined catalog -----------------------------------------------------


async def test_available_catalog_is_the_predefined_list(services):
    entries = services.business.get_available_catalog()
    by_key = {e.key: e for e in entries}
    assert set(by_key) == {item["key"] for item in constants.BUSINESS_CATALOG}
    for item in constants.BUSINESS_CATALOG:
        entry = by_key[item["key"]]
        assert entry.name == item["name"]
        assert entry.startup_cost == item["startup_cost"]
        assert (entry.min_daily_income, entry.max_daily_income) == (
            item["min_daily_income"],
            item["max_daily_income"],
        )
        assert entry.available is True
        # meaningful pricing, not an arbitrary 10M placeholder
        assert 10_000 <= entry.startup_cost <= 10_000_000


async def test_unavailable_businesses_are_hidden_and_blocked(services, register, monkeypatch):
    catalog = [dict(item) for item in constants.BUSINESS_CATALOG]
    catalog[0]["available"] = False
    monkeypatch.setattr(constants, "BUSINESS_CATALOG", tuple(catalog))

    hidden_key = catalog[0]["key"]
    entries = services.business.get_available_catalog()
    assert hidden_key not in {e.key for e in entries}

    player = await register(tg_id=9101)
    await _fund(services, player.player_id, 50_000_000)
    with pytest.raises(BusinessUnavailableError):
        await services.business.start_business(player.player_id, hidden_key)


# --- Starting a business ----------------------------------------------------------


async def test_start_business_creates_row_and_pays_wallet(services, register):
    player = await register(tg_id=9102)
    await _fund(services, player.player_id, 1_000_000)
    entry = _entry("fruit_stand")

    result = await services.business.start_business(player.player_id, "fruit_stand")

    assert result.paid_startup_cost == entry.startup_cost
    assert result.wallet_balance_after == 1_000_000 - entry.startup_cost
    assert await services.money.get_balance(player.player_id) == result.wallet_balance_after

    business = result.business
    assert business.owner_player_id == player.player_id
    assert business.business_key == "fruit_stand"
    assert business.type_name == entry.name
    assert business.startup_cost == entry.startup_cost
    assert business.balance == 0
    assert business.status == "active"
    assert business.created_at is not None
    assert business.last_income_date is None
    assert business.id > 0


async def test_start_rejects_unknown_or_custom_businesses(services, register):
    player = await register(tg_id=9103)
    await _fund(services, player.player_id, 50_000_000)

    for bogus in ("space_station", "MEHVA-FROOŠI", "", "  ", "کافه ایناستاگرام"):
        with pytest.raises(BusinessTypeNotFoundError):
            await services.business.start_business(player.player_id, bogus)

    # Nothing was charged, nothing was created.
    assert await services.money.get_balance(player.player_id) == 50_000_000
    assert await services.business.list_businesses(player.player_id) == []


async def test_start_rejected_when_wallet_cannot_pay(services, register):
    player = await register(tg_id=9104)
    entry = _entry("coffee_shop")
    await _fund(services, player.player_id, entry.startup_cost - 1)

    with pytest.raises(BusinessFundsError) as excinfo:
        await services.business.start_business(player.player_id, "coffee_shop")

    err = excinfo.value
    assert err.required == entry.startup_cost
    assert err.balance == entry.startup_cost - 1
    assert err.shortfall == 1
    # money untouched, no business row
    assert await services.money.get_balance(player.player_id) == entry.startup_cost - 1
    assert await services.business.list_businesses(player.player_id) == []


async def test_failed_start_after_payment_refunds_the_wallet(services, register, monkeypatch):
    player = await register(tg_id=9105)
    await _fund(services, player.player_id, 1_000_000)

    async def boom(self, *args, **kwargs):  # simulate a DB hiccup mid-create
        raise RuntimeError("db exploded")

    monkeypatch.setattr(BusinessRepository, "create", boom)
    with pytest.raises(RuntimeError):
        await services.business.start_business(player.player_id, "fruit_stand")
    monkeypatch.undo()

    assert await services.money.get_balance(player.player_id) == 1_000_000


async def test_ownership_cap_is_configurable(services, register, monkeypatch):
    player = await register(tg_id=9106)
    await _fund(services, player.player_id, 60_000_000)

    assert await services.business.count_active_businesses(player.player_id) == 0

    await services.business.start_business(player.player_id, "fruit_stand")
    await services.business.start_business(player.player_id, "bakery")
    assert await services.business.count_active_businesses(player.player_id) == 2

    with pytest.raises(TooManyBusinessesError) as excinfo:
        await services.business.start_business(player.player_id, "supermarket")
    assert excinfo.value.max_owned == constants.BUSINESS_MAX_OWNED == 2

    # Raise the cap in config -> the third start succeeds without touching code.
    monkeypatch.setattr(constants, "BUSINESS_MAX_OWNED", 3)
    result = await services.business.start_business(player.player_id, "supermarket")
    assert result.business.type_name == "سوپرمارکت"
    assert await services.business.count_active_businesses(player.player_id) == 3


# --- Ownership views ---------------------------------------------------------------


async def test_only_the_owner_sees_a_business(services, register):
    owner = await register(tg_id=9107)
    stranger = await register(tg_id=9108)
    await _fund(services, owner.player_id, 10_000_000)
    started = await services.business.start_business(owner.player_id, "fruit_stand")

    mine = await services.business.get_business(started.business.id, owner.player_id)
    assert mine.type_name == "میوه‌فروشی"

    with pytest.raises(NotBusinessOwnerError):
        await services.business.get_business(started.business.id, stranger.player_id)
    with pytest.raises(BusinessNotFoundError):
        await services.business.get_business(424242, owner.player_id)

    assert await services.business.list_businesses(stranger.player_id) == []


# --- Daily income -------------------------------------------------------------------


async def test_daily_income_credits_business_balance_not_wallet(services, register):
    player = await register(tg_id=9109)
    await _fund(services, player.player_id, 1_000_000)
    started = await services.business.start_business(player.player_id, "fruit_stand")
    entry = _entry("fruit_stand")
    services.business.set_rng(ConstRng("high"))  # deterministic: always max

    wallet_before = await services.money.get_balance(player.player_id)
    results = await services.business.collect_daily_income(player.player_id, now=DAY1)

    assert len(results) == 1
    income = results[0]
    assert income.granted is True
    assert income.amount == entry.max_daily_income
    assert income.day == rules.business_day(DAY1)
    assert income.balance_after == entry.max_daily_income

    business = await services.business.get_business(started.business.id, player.player_id)
    assert business.balance == entry.max_daily_income
    assert business.total_income == entry.max_daily_income
    assert business.income_days == 1
    assert business.last_income_date == rules.business_day(DAY1)
    assert business.last_income_amount == entry.max_daily_income

    # The player's wallet did NOT move — the money sits in the business.
    assert await services.money.get_balance(player.player_id) == wallet_before


async def test_daily_income_cannot_be_granted_twice_same_day(services, register):
    player = await register(tg_id=9110)
    await _fund(services, player.player_id, 1_000_000)
    started = await services.business.start_business(player.player_id, "fruit_stand")
    services.business.set_rng(ConstRng("low"))

    first = await services.business.collect_daily_income(player.player_id, now=DAY1)
    assert first[0].granted is True

    # Later the same day — even with more money rolls queued, nothing happens.
    again = await services.business.collect_daily_income(player.player_id, now=DAY1 + timedelta(hours=8))
    assert again[0].granted is False
    assert again[0].amount == 0

    business = await services.business.get_business(started.business.id, player.player_id)
    assert business.income_days == 1
    entry = _entry("fruit_stand")
    assert business.balance == entry.min_daily_income

    # Also the single-business endpoint is guarded.
    solo = await services.business.collect_business_income(
        started.business.id, player.player_id, now=DAY1
    )
    assert solo.granted is False

    # The next day pays again.
    services.business.set_rng(ConstRng("high"))
    second_day = await services.business.collect_daily_income(player.player_id, now=DAY2)
    assert second_day[0].granted is True
    business = await services.business.get_business(started.business.id, player.player_id)
    assert business.balance == entry.min_daily_income + entry.max_daily_income
    assert business.income_days == 2


async def test_repository_guard_blocks_double_credit_directly(services, db, register):
    """The once-per-day rule is enforced by the UPDATE itself."""
    player = await register(tg_id=9111)
    await _fund(services, player.player_id, 10_000_000)
    started = await services.business.start_business(player.player_id, "bakery")

    day = rules.business_day(DAY1)
    async with db.session_factory() as session:
        repo = BusinessRepository(session)
        assert await repo.credit_daily_income(started.business.id, day, 1000) is True
        # Second credit for the same day: matched zero rows.
        assert await repo.credit_daily_income(started.business.id, day, 1000) is False
        await session.commit()

    async with db.session_factory() as session:
        row = await session.get(Business, started.business.id)
        assert row.balance == 1000


async def test_income_is_variable_within_band(services, register):
    player = await register(tg_id=9112)
    await _fund(services, player.player_id, 10_000_000)
    await services.business.start_business(player.player_id, "coffee_shop")
    entry = _entry("coffee_shop")

    # Real dice, many days: amounts stay in the band and are NOT all equal.
    services.business.set_rng(random.Random(20260912))
    seen: list[int] = []
    for offset in range(30):
        now = DAY1 + timedelta(days=offset)
        results = await services.business.collect_daily_income(player.player_id, now=now)
        assert len(results) == 1 and results[0].granted is True
        amount = results[0].amount
        assert entry.min_daily_income <= amount <= entry.max_daily_income
        seen.append(amount)
    assert len(set(seen)) > 1  # some days less, some days more — never fixed


async def test_each_business_uses_its_own_configured_band(services, register):
    player = await register(tg_id=9113)
    await _fund(services, player.player_id, 60_000_000)
    await services.business.start_business(player.player_id, "fruit_stand")
    await services.business.start_business(player.player_id, "coffee_shop")

    fruit = _entry("fruit_stand")
    coffee = _entry("coffee_shop")
    assert fruit.max_daily_income < coffee.min_daily_income  # disjoint bands

    services.business.set_rng(random.Random(7))
    totals = {"میوه‌فروشی": 0, "کافیشاپ": 0}
    for offset in range(15):
        results = await services.business.collect_daily_income(
            player.player_id, now=DAY1 + timedelta(days=offset)
        )
        assert len(results) == 2
        for r in results:
            assert r.granted is True
            if r.type_name == "میوه‌فروشی":
                assert fruit.min_daily_income <= r.amount <= fruit.max_daily_income
            else:
                assert coffee.min_daily_income <= r.amount <= coffee.max_daily_income
            totals[r.type_name] += r.amount

    assert totals["میوه‌فروشی"] < totals["کافیشاپ"]  # 15 fruit-days beat 3 coffee-days


async def test_closed_business_does_not_earn(services, db, register):
    from app.database.models.business import STATUS_CLOSED

    player = await register(tg_id=9114)
    await _fund(services, player.player_id, 10_000_000)
    started = await services.business.start_business(player.player_id, "fruit_stand")
    async with db.session_factory() as session:
        await BusinessRepository(session).set_status(started.business.id, STATUS_CLOSED)
        await session.commit()

    results = await services.business.collect_daily_income(player.player_id, now=DAY1)
    assert results == []  # closed rows are skipped entirely


async def test_collect_one_requires_ownership(services, register):
    owner = await register(tg_id=9115)
    stranger = await register(tg_id=9116)
    await _fund(services, owner.player_id, 10_000_000)
    started = await services.business.start_business(owner.player_id, "fruit_stand")

    with pytest.raises(NotBusinessOwnerError):
        await services.business.collect_business_income(
            started.business.id, stranger.player_id, now=DAY1
        )


async def test_overview_reports_balances_and_today(services, register):
    player = await register(tg_id=9117)
    await _fund(services, player.player_id, 10_000_000)
    await services.business.start_business(player.player_id, "fruit_stand")
    services.business.set_rng(ConstRng("mid"))
    await services.business.collect_daily_income(player.player_id, now=DAY1)

    overview = await services.business.get_overview(player.player_id, now=DAY1)
    entry = _entry("fruit_stand")
    mid = (entry.min_daily_income + entry.max_daily_income) // 2
    assert overview.today == rules.business_day(DAY1)
    assert overview.max_owned == 2
    assert overview.total_balance == mid
    assert overview.today_income == mid
    assert overview.wallet_balance == 10_000_000 - entry.startup_cost


# --- Business day (Tehran calendar) ---------------------------------------------


def test_business_day_uses_tehran_calendar():
    # 20:00 UTC is 23:30 in Tehran (same day); 21:00 UTC is 00:30 the NEXT day.
    evening = datetime(2026, 9, 12, 20, 0, tzinfo=timezone.utc)
    past_midnight = datetime(2026, 9, 12, 21, 0, tzinfo=timezone.utc)
    assert rules.business_day(evening).isoformat() == "2026-09-12"
    assert rules.business_day(past_midnight).isoformat() == "2026-09-13"


def test_income_roll_requires_valid_band():
    entry = _entry("fruit_stand")
    assert rules.roll_daily_income(random.Random(1), entry) in range(
        entry.min_daily_income, entry.max_daily_income + 1
    )
    broken = rules.CatalogEntry(
        key="x", name="x", description="", startup_cost=1,
        min_daily_income=10, max_daily_income=5, available=True,
    )
    with pytest.raises(ValueError):
        rules.roll_daily_income(random.Random(1), broken)


# --- Employee hiring stays out ------------------------------------------------------


async def test_business_system_has_no_employee_hiring(services):
    """Hiring/staffing is explicitly disabled: the service exposes no such API
    and starting a business never creates workforce rows."""
    for banned in ("hire", "employee", "staff", "workforce", "recruit"):
        assert not any(banned in name.lower() for name in dir(services.business))
    assert not any(
        banned in name.lower()
        for name in dir(BusinessService)
        for banned in ("hire", "employee", "staff")
    )


# --- Handler layer (text trigger + inline buttons) ------------------------------------


def _make_user(tg_id: int) -> User:
    return User(id=tg_id, first_name="آرش", is_bot=False)


def _make_message(user: User, text: str) -> Message:
    return Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=user.id, type=Chat.PRIVATE),
        from_user=user,
        text=text,
    )


def _make_context(services) -> MagicMock:
    context = MagicMock()
    context.application.bot_data = {"services": services}
    return context


async def _tap(services, tg_id: int, data: str):
    """Fire a callback query through the business handlers router-ish helper."""
    edits: list[dict] = []

    async def edit_message_text(text=None, reply_markup=None, **kwargs):
        edits.append({"text": text, "reply_markup": reply_markup})

    query = MagicMock(spec=CallbackQuery)
    query.from_user = _make_user(tg_id)
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock(side_effect=edit_message_text)
    update = Update(update_id=1, callback_query=query)
    return update, edits


async def _route(update, context) -> None:
    """Dispatch like PTB would: try every business handler."""
    for handler in (
        business_handlers.business_menu_callback,
        business_handlers.catalog_callback,
        business_handlers.mine_callback,
        business_handlers.collect_callback,
        business_handlers.confirm_start_callback,
        business_handlers.open_business_callback,
        business_handlers.detail_callback,
        business_handlers.collect_one_callback,
    ):
        await handler(update, context)


async def test_text_trigger_opens_business_menu(services, register, monkeypatch):
    await register(tg_id=9118)
    sent: list[dict] = []

    async def fake_reply_text(self, text=None, reply_markup=None, **kwargs):
        sent.append({"text": text, "reply_markup": reply_markup})

    monkeypatch.setattr(Message, "reply_text", fake_reply_text)
    update = Update(update_id=1, message=_make_message(_make_user(9118), "کسب و کار"))
    await business_handlers.business_text_handler(update, _make_context(services))
    assert sent and "کسب و کار" in sent[0]["text"]
    assert sent[0]["reply_markup"] is not None  # inline menu attached


async def test_callback_flow_start_and_collect(services, register):
    player = await register(tg_id=9119)
    await _fund(services, player.player_id, 1_000_000)
    context = _make_context(services)
    tg_id = 9119

    update, edits = await _tap(services, tg_id, "biz_list")
    await _route(update, context)
    assert any("کسب‌وکارهای موجود" in e["text"] for e in edits)
    buttons = edits[0]["reply_markup"].inline_keyboard
    labels = [b.text for row in buttons for b in row]
    assert any("میوه‌فروشی" in label for label in labels)

    update, edits = await _tap(services, tg_id, "biz_start_fruit_stand")
    await _route(update, context)
    assert any("مطمئنی" in e["text"] for e in edits)  # confirmation screen

    update, edits = await _tap(services, tg_id, "biz_open_fruit_stand")
    await _route(update, context)
    assert any("تبریک" in e["text"] for e in edits)

    update, edits = await _tap(services, tg_id, "biz_mine")
    await _route(update, context)
    assert any("هنوز درآمدی ثبت نشده" in e["text"] for e in edits)

    update, edits = await _tap(services, tg_id, "biz_collect")
    await _route(update, context)
    assert any("اضافه شد" in e["text"] for e in edits)

    # Second collect the same day: everything already credited.
    update, edits = await _tap(services, tg_id, "biz_collect")
    await _route(update, context)
    assert any("قبلاً ثبت شده" in e["text"] for e in edits)


async def test_callback_invalid_business_is_refused(services, register):
    await register(tg_id=9120)
    context = _make_context(services)
    update, edits = await _tap(services, 9120, "biz_open_pegasus_imports")
    await _route(update, context)
    assert any("تو لیست نیست" in e["text"] for e in edits)


async def test_business_income_never_touches_wallet_via_handlers(services, register):
    player = await register(tg_id=9121)
    await _fund(services, player.player_id, 1_000_000)
    context = _make_context(services)
    update, _ = await _tap(services, 9121, "biz_open_fruit_stand")
    await _route(update, context)
    wallet_after_start = await services.money.get_balance(player.player_id)

    update, _ = await _tap(services, 9121, "biz_collect")
    await _route(update, context)
    assert await services.money.get_balance(player.player_id) == wallet_after_start
