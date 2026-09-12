from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timedelta, timezone
MARKET_ASSETS=(('usd','💵 دلار'),('gold','🪙 طلا'),('coin','🪙 سکه'),('housing','🏠 مسکن'))
@dataclass(frozen=True)
class MarketPrice:
    key:str; name:str; price:Decimal|None; previous:Decimal|None; updated_at:datetime|None

def due(last:datetime|None, now:datetime, interval_days:int=3):
    return last is None or now-last >= timedelta(days=interval_days)
def direction(change:Decimal): return '📈' if change>0 else '📉' if change<0 else '➖'
