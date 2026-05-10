"""
BTC Spike Guard Filter
=======================
Blocks or reduces Alt signals when BTC has a sudden large move.

Scenarios:
  BTC dump > 2%/15m:  BLOCK all Alt signals (size ×0.0)
  BTC pump > 2%/15m:  Reduce size ×0.5 (or block if relative weakness)
  Cooldown (30 min):  BLOCK all Alt signals

Registered as: "btc_guard"
"""

from __future__ import annotations

import logging

from engine.filters.base import BaseSignalFilter, FilterResult
from engine.filters.registry import FilterRegistry

logger = logging.getLogger(__name__)


@FilterRegistry.register("btc_guard")
class BTCGuardFilter(BaseSignalFilter):
    """
    BTC Volatility Spike Guard Filter.
    Wraps engine.btc_guard logic into the filter pipeline.
    """

    name = "btc_guard"

    def apply(self, context: dict) -> FilterResult:
        """
        Context keys used:
            symbol (str), ohlcv_btc (DataFrame), signal_direction (str)
        """
        try:
            from engine.btc_guard import BTCVolatilityGuard

            symbol = context.get("symbol", "")

            # BTC itself is never filtered by BTC guard
            if symbol == "BTC/USDT":
                return FilterResult.pass_clean(filter_name=self.name)

            ohlcv_btc = context.get("ohlcv_btc")
            if ohlcv_btc is None or ohlcv_btc.empty:
                return FilterResult.pass_clean(filter_name=self.name)

            guard = BTCVolatilityGuard()
            result = guard.check_btc_spike(ohlcv_btc)

            if not result.in_cooldown:
                return FilterResult.pass_clean(filter_name=self.name)

            if result.size_multiplier == 0.0:
                # Dump spike or relative weakness — block completely
                return FilterResult.block(
                    reason=result.block_reason or "BTC_SPIKE_COOLDOWN",
                    filter_name=self.name,
                )
            else:
                # Pump spike — reduce size 50%
                return FilterResult.pass_with_warning(
                    score_adjustment=0.0,
                    size_multiplier=result.size_multiplier,
                    warning=f"⚠ BTC spike {result.direction} — size giảm 50%",
                    filter_name=self.name,
                )

        except Exception as exc:
            logger.warning("BTCGuardFilter error (non-blocking): %s", exc)
            return FilterResult.pass_clean(filter_name=self.name)
