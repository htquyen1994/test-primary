"""
MTF Bias Filter
================
Filters signals based on 4H and Daily timeframe bias.

Scenarios:
  A — Aligned (4H same direction as signal): score +10, size ×1.0
  B — Diverging (4H ranging):                score -10, size ×0.5, warning
  C — Opposing (4H against signal):          BLOCK

Registered as: "mtf_bias"
"""

from __future__ import annotations

import logging

from engine.filters.base import BaseSignalFilter, FilterResult
from engine.filters.registry import FilterRegistry

logger = logging.getLogger(__name__)


@FilterRegistry.register("mtf_bias")
class MTFBiasFilter(BaseSignalFilter):
    """
    Multi-Timeframe Bias Filter.
    Wraps engine.mtf_bias logic into the filter pipeline.
    """

    name = "mtf_bias"

    def apply(self, context: dict) -> FilterResult:
        """
        Context keys used:
            ohlcv_4h (DataFrame), signal_direction (str),
            htf_bias_1h (str from SMC result)
        """
        try:
            from engine.mtf_bias import detect_4h_bias, get_mtf_alignment

            ohlcv_4h = context.get("ohlcv_4h")
            signal_direction = context.get("signal_direction", "long")
            htf_bias_1h = context.get("htf_bias_1h", "neutral")

            if ohlcv_4h is None or ohlcv_4h.empty:
                # No 4H data — pass with neutral result
                return FilterResult.pass_clean(filter_name=self.name)

            bias_4h = detect_4h_bias(ohlcv_4h)
            mtf = get_mtf_alignment(bias_4h, htf_bias_1h, signal_direction)

            if mtf.scenario == "C":
                return FilterResult.block(
                    reason=mtf.rejection_reason or "4H_OPPOSING_TREND",
                    filter_name=self.name,
                )
            elif mtf.scenario == "B":
                return FilterResult.pass_with_warning(
                    score_adjustment=mtf.score_adjustment,
                    size_multiplier=mtf.size_multiplier,
                    warning=mtf.warning_message or "4H không xác nhận — size giảm 50%",
                    filter_name=self.name,
                )
            else:  # Scenario A
                return FilterResult.pass_clean(
                    score_adjustment=mtf.score_adjustment,
                    filter_name=self.name,
                )

        except Exception as exc:
            logger.warning("MTFBiasFilter error (non-blocking): %s", exc)
            return FilterResult.pass_clean(filter_name=self.name)
