"""
Pinbar Strategy
================
Detects pin bar candles at key S/R levels (OB zone or FVG midpoint).

Mathematical logic (Req 1.2):
  tail_length >= 2 × body_length
  Long pinbar:  lower tail >= 2× body, close in upper 30% of range
  Short pinbar: upper tail >= 2× body, close in lower 30% of range

Entry:  Close of the pinbar candle
SL:     Beyond the tail tip (low for long, high for short)
TP1:    1.5R, TP2: 2.5R

Context Filter (Req 1.4): Requires 1H HTF bias alignment.
Failure Scenario (Req 1.5): Invalidated if price closes beyond the tail tip.

Satisfies: Requirements 1.2, 1.3, 1.4, 1.5, 5.1, 5.2
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

import pandas as pd

from strategies.base import BaseStrategy
from strategies.registry import StrategyRegistry
from strategies.signal import Signal, ScoreBreakdown
from engine.smc import find_order_block, find_fvg, detect_htf_bias
from engine.scorer import SignalScorer, ScoreInput
from engine.context import compute_context_score
from alert.invalidator import compute_expiry
from indicators.candle import (
    body_length, lower_wick, upper_wick, candle_range, body_position,
)

logger = logging.getLogger(__name__)

# Pinbar thresholds
TAIL_TO_BODY_RATIO = 2.0    # tail >= 2× body
BODY_POSITION_LONG = 0.70   # body in upper 70% of range (close near high)
BODY_POSITION_SHORT = 0.30  # body in lower 30% of range (close near low)
MIN_RANGE_ATR_RATIO = 0.5   # candle range must be >= 50% of ATR (avoid tiny candles)


@StrategyRegistry.register("pinbar")
class PinbarStrategy(BaseStrategy):
    """
    Pin Bar reversal strategy at key S/R levels.

    Satisfies: Requirements 1.2, 1.3, 1.4, 1.5, 5.1, 5.2
    """

    @property
    def name(self) -> str:
        return "pinbar"

    def generate_signals(
        self,
        ohlcv: pd.DataFrame,
        context: dict,
    ) -> List[Signal]:
        T = len(ohlcv) - 1
        self._check_no_lookahead(ohlcv, T)

        if len(ohlcv) < 15:
            return []

        ohlcv_1h = context.get("ohlcv_1h", pd.DataFrame())
        regime = context.get("regime", "RANGING")
        regime_multiplier = context.get("regime_multiplier", 1.0)
        funding_rate = context.get("funding_rate", 0.0)
        portfolio_heat = context.get("portfolio_heat", 0.0)
        correlated_group_risk = context.get("correlated_group_risk", 0.0)

        candle = ohlcv.iloc[-1]
        candle_index = T

        # --- Detect pinbar type ---
        direction = self._detect_pinbar(candle)
        if direction is None:
            return []

        # --- PARABOLIC: suppress short ---
        if regime == "PARABOLIC" and direction == "short":
            return []

        # --- Context Filter: HTF bias alignment (Req 1.4) ---
        htf_bias = detect_htf_bias(ohlcv_1h) if not ohlcv_1h.empty else "neutral"
        if htf_bias == "neutral":
            return []
        if direction == "long" and htf_bias != "bullish":
            return []
        if direction == "short" and htf_bias != "bearish":
            return []

        # --- Must be at a key S/R level (OB zone or FVG midpoint) ---
        current_price = float(candle["close"])
        ob = find_order_block(ohlcv)
        fvg = find_fvg(ohlcv)

        at_key_level = (
            (ob and ob.valid and ob.is_price_retesting(current_price)) or
            (fvg and not fvg.filled and fvg.is_price_at_midpoint(current_price))
        )
        if not at_key_level:
            return []

        # --- Score ---
        ctx_result = compute_context_score(ohlcv_1h, direction, funding_rate)
        scorer = SignalScorer.from_config(self.config) if hasattr(self.config, "strategy") \
            else SignalScorer()

        score_output = scorer.score(ScoreInput(
            order_flow=0.0,
            smc=10.0 if ob and ob.valid else 0.0,  # OB presence
            vsa=0.0,
            context=ctx_result.score,
            bonus=0.0,
            regime_multiplier=regime_multiplier,
            direction=direction,
            regime=regime,
        ))

        if score_output.suppressed:
            return []

        # --- Trade levels ---
        entry = current_price
        if direction == "long":
            sl = float(candle["low"]) * 0.998   # just below the tail tip
            tp1 = entry + (entry - sl) * 1.5
            tp2 = entry + (entry - sl) * 2.5
        else:
            sl = float(candle["high"]) * 1.002
            tp1 = entry - (sl - entry) * 1.5
            tp2 = entry - (sl - entry) * 2.5

        if abs(entry - sl) == 0:
            return []

        expires_at = compute_expiry(candle_index, self.time_invalidation_candles)

        return [Signal(
            strategy_name=self.name,
            asset=context.get("asset", "UNKNOWN"),
            timeframe=context.get("timeframe", "15m"),
            direction=direction,
            candle_index=candle_index,
            candle_timestamp=datetime.now(timezone.utc),
            entry_price=entry,
            stop_loss=sl,
            take_profit_1=tp1,
            take_profit_2=tp2,
            raw_score=score_output.raw_score,
            final_score=score_output.final_score,
            score_breakdown=ScoreBreakdown(
                order_flow=0.0,
                smc=10.0 if ob and ob.valid else 0.0,
                vsa=0.0,
                context=ctx_result.score,
                bonus=0.0,
            ),
            classification=score_output.classification,
            regime=regime,
            regime_multiplier=regime_multiplier,
            funding_rate=funding_rate,
            portfolio_heat=portfolio_heat,
            correlated_group_risk=correlated_group_risk,
            expires_at_candle=expires_at,
        )]

    def _detect_pinbar(self, candle) -> str | None:
        """
        Returns "long", "short", or None.

        Long pinbar:  lower_wick >= 2× body AND body in upper 70% of range
        Short pinbar: upper_wick >= 2× body AND body in lower 30% of range

        Satisfies: Requirement 1.2 (Pinbar mathematical logic)
        """
        body = body_length(candle)
        rng = candle_range(candle)

        if rng == 0:
            return None

        # Avoid tiny candles (doji-like)
        if body == 0:
            body = rng * 0.01  # treat as near-zero body

        lw = lower_wick(candle)
        uw = upper_wick(candle)
        bp = body_position(candle)

        # Long pinbar: long lower tail, body near top
        if lw >= TAIL_TO_BODY_RATIO * body and bp >= BODY_POSITION_LONG:
            return "long"

        # Short pinbar: long upper tail, body near bottom
        if uw >= TAIL_TO_BODY_RATIO * body and bp <= BODY_POSITION_SHORT:
            return "short"

        return None
