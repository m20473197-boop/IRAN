"""Business System service — start businesses, own them, grant daily income.

Responsibilities (the handlers stay thin, the repositories stay dumb):

* expose the predefined catalog (``constants.BUSINESS_CATALOG``) to the bot
  layer — players can only ever start businesses from this list;
* validate a start request: known + available type, the per-player ownership
  cap, and the startup cost paid through the existing MoneyService (the
  wallet is the only place player money ever changes);
* grant each active business its daily income — a random amount inside the
  type's configured band, credited to the *business* balance (never the
  player wallet) and guarded so the same calendar day can never be paid
  twice;
* load a player's businesses with ownership checks for the view screens.

All numbers are exact integer Toman. The RNG is injectable so tests can
script the daily rolls; balancing is pure configuration (``constants``).
"""

from __future__ import annotations

import logging
import random

from datetime import datetime
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import constants
from app.database.models.business import Business
from app.database.repositories.business_repository import BusinessRepository
from app.game.business import rules
from app.game.business.dto import (
    BusinessData,
    BusinessIncomeResult,
    BusinessOverview,
    BusinessStartResult,
)
from app.game.business.rules import CatalogEntry
from app.game.player.dto import MoneyChangeResult
from app.game.shared.errors import (
    DomainError,
    InsufficientFundsError,
)

logger = logging.getLogger(__name__)


class BusinessError(DomainError):
    """Base class for the business system's refusals."""


class BusinessTypeNotFoundError(BusinessError):
    """The requested key is not in the predefined catalog at all."""


class BusinessUnavailableError(BusinessError):
    """The catalog entry exists but is currently switched off."""


class TooManyBusinessesError(BusinessError):
    """The player already owns the maximum number of businesses."""

    def __init__(self, max_owned: int):
        super().__init__(f"player already owns {max_owned} businesses")
        self.max_owned = max_owned


class BusinessFundsError(BusinessError):
    """The player cannot pay the startup cost; carries the full picture."""

    def __init__(self, required: int, balance: int, shortfall: int):
        super().__init__(
            f"startup cost {required} > balance {balance} (short {shortfall})"
        )
        self.required = required
        self.balance = balance
        self.shortfall = shortfall


class BusinessNotFoundError(BusinessError):
    """No business row with this id exists."""


class NotBusinessOwnerError(BusinessError):
    """The viewer is not the owner — the row's existence is never leaked."""


class BusinessService:
    """Complete business service (start / own / daily income)."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        money_service,
        rng: random.Random | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._money = money_service
        self._rng = rng if rng is not None else random.Random()

    def set_rng(self, rng: random.Random) -> None:
        """Swap the income dice (tests script the daily rolls with this)."""
        self._rng = rng

    # --- Catalog -----------------------------------------------------------

    @staticmethod
    def get_available_catalog() -> tuple[CatalogEntry, ...]:
        """The businesses players may start right now, in menu order."""
        return rules.available_catalog()

    @staticmethod
    def max_owned() -> int:
        return int(constants.BUSINESS_MAX_OWNED)

    # --- Starting a business -------------------------------------------------

    async def start_business(
        self, player_id: int, business_key: str
    ) -> BusinessStartResult:
        """Start a predefined business; the startup cost leaves the wallet.

        Raises:
            BusinessTypeNotFoundError: unknown catalog key.
            BusinessUnavailableError: the entry is switched off.
            TooManyBusinessesError: the ownership cap is reached.
            BusinessFundsError: the wallet cannot afford the startup cost.
            PlayerNotFoundError: no such player.
        """
        entry = rules.catalog_item((business_key or "").strip())
        if entry is None:
            raise BusinessTypeNotFoundError(f"unknown business key: {business_key!r}")
        if not entry.available:
            raise BusinessUnavailableError(entry.key)

        async with self._session_factory() as session:
            repo = BusinessRepository(session)
            owned = await repo.count_active_for_owner(player_id)
            if owned >= self.max_owned():
                raise TooManyBusinessesError(self.max_owned())

        # The charge itself goes through the wallet service (atomic
        # sufficiency check inside). Insufficient funds are reported with the
        # exact shortfall so the player sees what is missing.
        # PlayerNotFoundError / unexpected wallet failures propagate as-is —
        # the handler layer maps them to the standard Persian texts.
        try:
            payment: MoneyChangeResult = await self._money.remove_money(
                player_id, entry.startup_cost
            )
        except InsufficientFundsError:
            balance = await self._money.get_balance(player_id)
            raise BusinessFundsError(
                required=entry.startup_cost,
                balance=balance,
                shortfall=max(0, entry.startup_cost - balance),
            ) from None

        try:
            async with self._session_factory() as session:
                repo = BusinessRepository(session)
                business = await repo.create(
                    owner_player_id=player_id,
                    business_key=entry.key,
                    type_name=entry.name,
                    startup_cost=entry.startup_cost,
                )
                await session.commit()
                data = self._to_dto(business)
        except Exception:
            # The money is already gone — never let a player pay for nothing.
            await self._money.add_money(player_id, entry.startup_cost)
            raise

        logger.info(
            "business %s started by player %s for %s",
            data.id,
            player_id,
            entry.startup_cost,
        )
        return BusinessStartResult(
            business=data,
            paid_startup_cost=payment.amount,
            wallet_balance_after=payment.balance_after,
        )

    # --- Ownership / viewing --------------------------------------------------

    async def count_active_businesses(self, player_id: int) -> int:
        """How many businesses the player owns right now (the cap counts these)."""
        async with self._session_factory() as session:
            return await BusinessRepository(session).count_active_for_owner(
                player_id
            )

    async def list_businesses(self, player_id: int) -> List[BusinessData]:
        """Every business of the player (active and closed)."""
        async with self._session_factory() as session:
            rows = await BusinessRepository(session).list_for_owner(player_id)
            return [self._to_dto(row) for row in rows]

    async def get_business(self, business_id: int, viewer_player_id: int) -> BusinessData:
        """Load one business for its owner only.

        Raises:
            BusinessNotFoundError: no such business.
            NotBusinessOwnerError: the viewer does not own it.
        """
        async with self._session_factory() as session:
            row = await BusinessRepository(session).get_by_id(business_id)
            if row is None:
                raise BusinessNotFoundError(f"business_id={business_id} not found")
            if row.owner_player_id != viewer_player_id:
                raise NotBusinessOwnerError(
                    f"business_id={business_id} belongs to another player"
                )
            return self._to_dto(row)

    async def get_overview(
        self, player_id: int, now: Optional[datetime] = None
    ) -> BusinessOverview:
        """Everything the «کسب و کارهای من» screen shows (read-only view)."""
        businesses = await self.list_businesses(player_id)
        wallet = await self._money.get_balance(player_id)
        return BusinessOverview(
            businesses=businesses,
            today=rules.business_day(now),
            max_owned=self.max_owned(),
            wallet_balance=wallet,
        )

    # --- Daily income -----------------------------------------------------------

    async def collect_daily_income(
        self, player_id: int, now: Optional[datetime] = None
    ) -> List[BusinessIncomeResult]:
        """Credit today's income to every active business that missed it.

        Each business rolls its amount once per Iranian calendar day: a day
        already credited is skipped (and the repository guard makes double
        payment impossible even under concurrent taps). The rolled amount
        goes to the *business* balance — never to the player's wallet.
        Missed past days are not backfilled: a business pays for the day it
        is collected on.
        """
        day = rules.business_day(now)
        results: List[BusinessIncomeResult] = []

        async with self._session_factory() as session:
            repo = BusinessRepository(session)
            rows = await repo.list_for_owner(player_id)
            for row in rows:
                if row.status != "active":
                    continue
                if row.last_income_date == day:
                    results.append(
                        BusinessIncomeResult(
                            business_id=row.id,
                            type_name=row.type_name,
                            day=day,
                            amount=0,
                            granted=False,
                            balance_after=row.balance,
                        )
                    )
                    continue
                entry = rules.catalog_item(row.business_key)
                if entry is None:  # catalog entry removed after the start
                    results.append(
                        BusinessIncomeResult(
                            business_id=row.id,
                            type_name=row.type_name,
                            day=day,
                            amount=0,
                            granted=False,
                            balance_after=row.balance,
                        )
                    )
                    continue
                amount = rules.roll_daily_income(self._rng, entry)
                # Snapshot everything needed BEFORE the UPDATE — the repo
                # expires the instance so later loads see fresh data.
                business_id, type_name, pre_balance = (
                    row.id,
                    row.type_name,
                    row.balance,
                )
                granted = await repo.credit_daily_income(business_id, day, amount)
                balance_after = pre_balance + amount if granted else pre_balance
                results.append(
                    BusinessIncomeResult(
                        business_id=business_id,
                        type_name=type_name,
                        day=day,
                        amount=amount if granted else 0,
                        granted=granted,
                        balance_after=balance_after,
                    )
                )
            if any(r.granted for r in results):
                await session.commit()
        return results

    async def collect_business_income(
        self, business_id: int, player_id: int, now: Optional[datetime] = None
    ) -> BusinessIncomeResult:
        """Daily income for one business — owner-checked.

        Raises:
            BusinessNotFoundError / NotBusinessOwnerError like get_business.
        """
        day = rules.business_day(now)
        async with self._session_factory() as session:
            repo = BusinessRepository(session)
            row = await repo.get_by_id(business_id)
            if row is None:
                raise BusinessNotFoundError(f"business_id={business_id} not found")
            if row.owner_player_id != player_id:
                raise NotBusinessOwnerError(
                    f"business_id={business_id} belongs to another player"
                )
            if row.status != "active" or row.last_income_date == day:
                return BusinessIncomeResult(
                    business_id=row.id,
                    type_name=row.type_name,
                    day=day,
                    amount=0,
                    granted=False,
                    balance_after=row.balance,
                )
            entry = rules.catalog_item(row.business_key)
            if entry is None:
                return BusinessIncomeResult(
                    business_id=row.id,
                    type_name=row.type_name,
                    day=day,
                    amount=0,
                    granted=False,
                    balance_after=row.balance,
                )
            amount = rules.roll_daily_income(self._rng, entry)
            business_id, type_name, pre_balance = (  # snapshot before expiry
                row.id,
                row.type_name,
                row.balance,
            )
            granted = await repo.credit_daily_income(business_id, day, amount)
            balance_after = pre_balance + amount if granted else pre_balance
            if granted:
                await session.commit()
            return BusinessIncomeResult(
                business_id=business_id,
                type_name=type_name,
                day=day,
                amount=amount if granted else 0,
                granted=granted,
                balance_after=balance_after,
            )

    # --- Helpers --------------------------------------------------------------

    @staticmethod
    def _to_dto(row: Business) -> BusinessData:
        entry = rules.catalog_item(row.business_key)
        return BusinessData(
            id=row.id,
            owner_player_id=row.owner_player_id,
            business_key=row.business_key,
            type_name=row.type_name,
            description=entry.description if entry is not None else "",
            startup_cost=row.startup_cost,
            balance=row.balance,
            status=row.status,
            created_at=row.created_at,
            last_income_date=row.last_income_date,
            last_income_amount=row.last_income_amount,
            total_income=row.total_income,
            income_days=row.income_days,
        )
