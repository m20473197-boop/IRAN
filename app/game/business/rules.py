"""Business System (کسب و کار) — pure domain rules, no DB, no Telegram.

Shared helpers living here:

* :func:`business_day` — the Iranian calendar day a business income belongs
  to. Income is granted once per *this* day (fixed UTC+3:30 offset, Iran
  has no DST), never per rolling 24 hours, so "today" stays identical for
  every player and survives server restarts.
* :func:`roll_daily_income` — the variable daily income. Every day lands
  somewhere inside the business' configured ``[min, max]`` band; a business
  never earns a fixed amount because the roll is drawn from an RNG
  (``random.Random`` in production, a scripted one in tests).
* :func:`catalog_item` — access to the predefined business list from
  ``constants.BUSINESS_CATALOG`` (the single configurable source of truth:
  prices and income ranges are tuned there, never in code).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from app.core import constants


@dataclass(frozen=True)
class CatalogEntry:
    """A validated view of one ``BUSINESS_CATALOG`` entry."""

    key: str
    name: str
    description: str
    startup_cost: int
    min_daily_income: int
    max_daily_income: int
    available: bool


def tehran_timezone() -> timezone:
    """The fixed Iran Standard Time zone (UTC+3:30 — no DST since 1402)."""
    return timezone(
        timedelta(minutes=constants.BUSINESS_TEHARAN_UTC_OFFSET_MINUTES)
    )


def business_day(now: datetime | None = None) -> date:
    """The Iranian business day (a plain ``date``) that ``now`` falls in.

    ``now`` defaults to the current UTC time; naive datetimes are treated as
    UTC (the storage convention of this project). Tests pass an explicit
    ``now`` for determinism.
    """
    moment = now if now is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(tehran_timezone()).date()


def catalog() -> tuple[CatalogEntry, ...]:
    """All predefined businesses, in menu order (even unavailable ones)."""
    return tuple(
        CatalogEntry(
            key=str(item["key"]),
            name=str(item["name"]),
            description=str(item.get("description", "")),
            startup_cost=int(item["startup_cost"]),
            min_daily_income=int(item["min_daily_income"]),
            max_daily_income=int(item["max_daily_income"]),
            available=bool(item.get("available", True)),
        )
        for item in constants.BUSINESS_CATALOG
    )


def available_catalog() -> tuple[CatalogEntry, ...]:
    """The businesses players can actually start right now."""
    return tuple(entry for entry in catalog() if entry.available)


def catalog_item(key: str) -> CatalogEntry | None:
    """The predefined business with this key — ``None`` if it does not exist."""
    for entry in catalog():
        if entry.key == key:
            return entry
    return None


def roll_daily_income(rng: random.Random, entry: CatalogEntry) -> int:
    """Draw the income of ``entry`` for one day (exact integer Toman).

    Always inside the inclusive band ``[min_daily_income, max_daily_income]``;
    the spread between the bounds is what makes some days better and some
    days worse. An unusable band is a configuration bug — fail loudly.
    """
    low, high = entry.min_daily_income, entry.max_daily_income
    if low < 0 or high < low:
        raise ValueError(
            f"bad income band for business {entry.key!r}: {low}..{high}"
        )
    return rng.randint(low, high)
