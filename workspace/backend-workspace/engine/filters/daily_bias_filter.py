"""
Daily Bias Filter
==================
Reduces position size when Daily timeframe is bearish.

Logic:
  Daily BEAR + long signal → size ×0.75 (25% reduction)
  Daily BULL or NEUTRAL    → no change

Registered as: "daily_bias"
"""

from __future__ import annotations

import logging

from engine.filters.base import BaseSignalFilter, FilterResult
from engine.filters.registry import FilterRegistry

logger = logging.getLogger(__name__)


@FilterRegistry.register("daily_bias")
class DailyBiasFilter(BaseSignalFilter):
    """
    Daily Macro Bias Filter.
    Wraps engine.mtf_bias.get_daily_size_multiplier into the filter pipeline.
    """

    name = "daily_bias"

    def apply(self, context: dict) -> FilterResult:
        """
        Context keys used:
            ohlcv_daily (DataFrame), signal_direction (str)
        """
        try:
            from engine.mtf_bias import detect_daily_bias, get_daily_size_multiplier

            ohlcv_daily = context.get("ohlcv_daily")
            signal_direction = context.get("signal_direction", "long")

            if ohlcv_daily is None or ohlcv_daily.empty:
                return FilterResult.pass_clean(filter_name=self.name)

            daily_bias = detect_daily_bias(ohlcv_daily)
            size_mult, warning = get_daily_size_multiplier(daily_bias, signal_direction)

            if size_mult < 1.0 and warning:
                return FilterResult.pass_with_warning(
                    score_adjustment=0.0,
                    size_multiplier=size_mult,
                    warning=warning,
                    filter_name=self.name,
                )

            return FilterResult.pass_clean(filter_name=self.name)

        except Exception as exc:
            logger.warning("DailyBiasFilter error (non-blocking): %s", exc)
            return FilterResult.pass_clean(filter_name=self.name)
