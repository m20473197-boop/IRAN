from __future__ import annotations
import logging, os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from app.database.repositories.market_repository import MarketRepository
from app.game.market import MARKET_ASSETS, due
from app.services.market_data_provider import IranianMarketDataProvider, MarketDataProvider, MarketDataError
logger=logging.getLogger(__name__)
class MarketService:
    _lock=None
    def __init__(self, session_factory, provider:MarketDataProvider|None=None):
        self._session_factory=session_factory; self.provider=provider or IranianMarketDataProvider()
        self.interval_days=int(os.getenv('MARKET_UPDATE_INTERVAL_DAYS','3')); self.housing_reference=Decimal(os.getenv('HOUSING_MARKET_REFERENCE','100000000'))
        if MarketService._lock is None:
            import asyncio; MarketService._lock=asyncio.Lock()
    async def ensure_assets(self):
        async with self._session_factory() as s:
            repo=MarketRepository(s); rows=await repo.ensure_assets(MARKET_ASSETS)
            await s.commit(); return rows
    async def assets(self):
        await self.ensure_assets()
        async with self._session_factory() as s: return await MarketRepository(s).list_assets()
    async def get(self,key):
        await self.ensure_assets()
        async with self._session_factory() as s: return await MarketRepository(s).get(key)
    async def update_if_due(self, force=False, now=None):
        now=now or datetime.now(timezone.utc).replace(tzinfo=None)
        async with self._lock:
            async with self._session_factory() as s:
                repo=MarketRepository(s); rows=await repo.ensure_assets(MARKET_ASSETS)
                last=min((r.last_successful_update for r in rows if r.asset_key!='housing' and r.last_successful_update),default=None)
                if not force and not due(last,now,self.interval_days): return False
                await repo.mark_attempt(now); await s.commit()
            try: prices=await self.provider.fetch_prices()
            except MarketDataError: logger.exception('External Iranian market update failed'); return False
            async with self._session_factory() as s:
                repo=MarketRepository(s); rows=await repo.ensure_assets(MARKET_ASSETS); by={r.asset_key:r for r in rows}
                for key in ('usd','gold','coin'): await repo.update_price(by[key],prices[key],now,'iranian_external')
                await repo.update_price(by['housing'],self.housing_reference,now,'housing_reference') if by['housing'].current_price is None else None
                await s.commit(); logger.info('Market prices updated successfully'); return True
    async def details(self,key): return await self.get(key)
    async def history(self,key,limit=50):
        async with self._session_factory() as s: return await MarketRepository(s).history(key,limit)
