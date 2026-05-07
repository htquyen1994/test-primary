"""
Engulfing Strategy
===================
Two-candle reversal pattern where the second candle's body fully contains
the first candle's body.

Mathematical logic (Req 1.2):
  Bullish engulfing:
    candle[T].close > candle[T].open  (bullish)
    candle[T-1].close < candle[T-1].open  (bearish)
    candle[T].open <= candle[T-1].close  (opens at or below prior close)
    candle[T].close >= candle[T-1].open  (closes at or above prior open)

  Bearish engulfing: mirror conditions

Entry:  Close of the engulfing candle
SL:     Below/above the engulfed candle's wick
TP1:    1.5R, TP2: 2.5R

Context Filter (Req 1.4): Requires 1H HTF bias alignment.

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
from engine.smc import detect_htf_bias
from engine.scorer import SignalScorer, ScoreInput
from engine.context import compute_context_score
from alert.invalidator import compute_expiry
from indicators.candle import body_length, is_bullish, is_bearish

logger = logging.getLogger(__name__)


@StrategyRegistry.register("engulfing")
class EngulfingStrategy(BaseStrategy):
    """
    Bullish/Bearish Engulfing reversal strategy.

    Satisfies: Requirements 1.2, 1.3, 1.4, 1.5, 5.1, 5.2
    """

    @property
    def name(self) -> str:
        return "engulfing"

    def generate_signals(
        self,
        ohlcv: pd.DataFrame,
        context: dict,
    ) -> List[Signal]:
        T = len(ohlcv) - 1
        self._check_no_lookahead(ohlcv, T)

        if len(ohlcv) < 10:
            return []

        ohlcv_1h = context.get("ohlcv_1h", pd.DataFrame())
        regime = context.get("regime", "RANGING")
        regime_multiplier = context.get("regime_multiplier", 1.0)
        funding_rate = context.get("funding_rate", 0.0)
        portfolio_heat = context.get("portfolio_heat", 0.0)
        correlated_group_risk = context.get("correlated_group_risk", 0.0)

        current = ohlcv.iloc[-1]
        previous = ohlcv.iloc[-2]
        candle_index = T

        # --- Detect engulfing pattern ---
        direction = self._detect_engulfing(current, previous)
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

        # --- Score ---
        ctx_result = compute_context_score(ohlcv_1h, direction, funding_rate)
        scorer = SignalScorer.from_config(self.config) if hasattr(self.config, "strategy") \
            else SignalScorer()

        score_output = scorer.score(ScoreInput(
            order_flow=0.0,
            smc=10.0,   # engulfing at key level = SMC-like signal
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
        entry = float(current["close"])
        if direction == "long":
            # SL below the engulfed candle's low wick
            sl = float(previous["low"]) * 0.998
            tp1 = entry + (entry - sl) * 1.5
            tp2 = entry + (entry - sl) * 2.5
        else:
            sl = float(previous["high"]) * 1.002
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
                order_flow=0.0, smc=10.0, vsa=0.0,
                context=ctx_result.score, bonus=0.0,
            ),
            classification=score_output.classification,
            regime=regime,
            regime_multiplier=regime_multiplier,
            funding_rate=funding_rate,
            portfolio_heat=portfolio_heat,
            correlated_group_risk=correlated_group_risk,
            expires_at_candle=expires_at,
        )]

    def _detect_engulfing(self, current, previous) -> str | None:
        """
        Returns "long", "short", or None.

        Bullish engulfing:
          current is bullish, previous is bearish,
          current.open <= previous.close AND current.close >= previous.open

        Bearish engulfing: mirror conditions.

        Satisfies: Requirement 1.2 (Engulfing mathematical logic)
        """
        c_open = float(current["open"])
        c_close = float(current["close"])
        p_open = float(previous["open"])
        p_close = float(previous["close"])

        # Bullish engulfing
        if (is_bullish(current) and is_bearish(previous) and
                c_open <= p_close and c_close >= p_open):
            return "long"

        # Bearish engulfing
        if (is_bearish(current) and is_bullish(previous) and
                c_open >= p_close and c_close <= p_open):
            return "short"

        return None
