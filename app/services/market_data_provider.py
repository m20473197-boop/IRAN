from __future__ import annotations
import asyncio, json, logging, os, urllib.request
from decimal import Decimal, InvalidOperation
from typing import Protocol
logger=logging.getLogger(__name__)
class MarketDataError(RuntimeError): pass
class MarketDataProvider(Protocol):
    async def fetch_prices(self)->dict[str,Decimal]: ...
class IranianMarketDataProvider:
    """Replaceable adapter. Endpoint must return USD/gold/coin fields (or nested data)."""
    def __init__(self, endpoint=None, timeout=None):
        self.endpoint=endpoint or os.getenv('IRAN_MARKET_DATA_URL','https://api.tgju.org/v1/market/price')
        self.timeout=float(timeout or os.getenv('MARKET_API_TIMEOUT','10'))
    async def fetch_prices(self):
        try: raw=await asyncio.wait_for(asyncio.to_thread(self._get),self.timeout)
        except Exception as exc: raise MarketDataError(f'market provider failed: {type(exc).__name__}') from exc
        try:
            data=json.loads(raw); data=data.get('data',data)
            out={k:Decimal(str(data[k])) for k in ('usd','gold','coin')}
            if any(v<=0 for v in out.values()): raise ValueError('non-positive price')
            return out
        except (KeyError,TypeError,ValueError,InvalidOperation) as exc: raise MarketDataError('invalid or incomplete market response') from exc
    def _get(self):
        req=urllib.request.Request(self.endpoint,headers={'User-Agent':'LIR-market/1.0'})
        with urllib.request.urlopen(req,timeout=self.timeout) as r: return r.read().decode()
