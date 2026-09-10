"""Market conditions — the shared economy factor of the whole real-estate market.

Land prices, construction costs and renovation costs are all multiplied by
this factor, so a single economic change (inflation, recession, a boom) moves
every price in the game at once. Nothing anywhere is a fixed price.

The future Economy/Inflation system integrates by either:
* updating ``constants.ECONOMY_MARKET_CONDITIONS`` (e.g. from a scheduled
  job that follows a real Iranian market index), or
* passing an explicit ``market_factor`` into the pricing functions.

The housing pricing engine (``app/game/housing/pricing.py``) accepts the same
``market_factor`` argument, so one knob drives both markets.
"""

from __future__ import annotations

from app.core import constants


def current_market_factor() -> float:
    """The live market/economy multiplier applied to all real-estate prices."""
    return constants.ECONOMY_MARKET_CONDITIONS
