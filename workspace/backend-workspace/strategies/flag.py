"""
Flag / Pennant Strategy
========================
Strong impulse move followed by 3–7 candles of consolidation with declining volume.
Entry on breakout of the flag channel in the direction of the impulse.

Satisfies: Requirements 1.2, 1.3, 5.1
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import List
import numpy as np
import pandas as pd
from strategies.base import BaseStrategy
from strategies.registry import StrategyRegistry
from strategies.signal import Signal, ScoreBreakdown
from engine.smc import detect_htf_bias
from engine.scorer import SignalScorer, ScoreInput
from engine.context import compute_context_score
from alert.invalidator import compute_expiry
from indicators.atr import ATR

FLAG_IMPULSE_ATR_MULT = 1.5   # impulse body >= 1.5 × ATR
FLAG_MIN_CANDLES = 3
FLAG_MAX_CANDLES = 7


@StrategyRegistry.register("flag")
class FlagStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "flag"

    def generate_signals(self, ohlcv: pd.DataFrame, context: dict) -> List[Signal]:
        T = len(ohlcv) - 1
        self._check_no_lookahead(ohlcv, T)
        if len(ohlcv) < 20:
            return []

        ohlcv_1h = context.get("ohlcv_1h", pd.DataFrame())
        regime = context.get("regime", "RANGING")
        regime_multiplier = context.get("regime_multiplier", 1.0)
        funding_rate = context.get("funding_rate", 0.0)

        result = self._detect_flag(ohlcv)
        if result is None:
            return []

        direction, impulse_idx = result
        if regime == "PARABOLIC" and direction == "short":
            return []

        htf_bias = detect_htf_bias(ohlcv_1h) if not ohlcv_1h.empty else "neutral"
        if htf_bias == "neutral":
            return []
        if direction == "long" and htf_bias != "bullish":
            return []
        if direction == "short" and htf_bias != "bearish":
            return []

        ctx_result = compute_context_score(ohlcv_1h, direction, funding_rate)
        scorer = SignalScorer.from_config(self.config) if hasattr(self.config, "strategy") else SignalScorer()
        score_output = scorer.score(ScoreInput(
            order_flow=0, smc=10.0, vsa=5.0, context=ctx_result.score, bonus=0,
            regime_multiplier=regime_multiplier, direction=direction, regime=regime,
        ))
        if score_output.suppressed:
            return []

        entry = float(ohlcv.iloc[-1]["close"])
        flag_high = float(ohlcv.iloc[impulse_idx + 1:]["high"].max())
        flag_low = float(ohlcv.iloc[impulse_idx + 1:]["low"].min())

        if direction == "long":
            sl = flag_low * 0.998
            tp1 = entry + (entry - sl) * 1.5
            tp2 = entry + (entry - sl) * 2.5
        else:
            sl = flag_high * 1.002
            tp1 = entry - (sl - entry) * 1.5
            tp2 = entry - (sl - entry) * 2.5

        if abs(entry - sl) == 0:
            return []

        return [Signal(
            strategy_name=self.name, asset=context.get("asset", "UNKNOWN"),
            timeframe=context.get("timeframe", "15m"), direction=direction,
            candle_index=T, candle_timestamp=datetime.now(timezone.utc),
            entry_price=entry, stop_loss=sl, take_profit_1=tp1, take_profit_2=tp2,
            raw_score=score_output.raw_score, final_score=score_output.final_score,
            score_breakdown=ScoreBreakdown(order_flow=0, smc=10.0, vsa=5.0, context=ctx_result.score, bonus=0),
            classification=score_output.classification, regime=regime,
            regime_multiplier=regime_multiplier, funding_rate=funding_rate,
            portfolio_heat=context.get("portfolio_heat", 0.0),
            correlated_group_risk=context.get("correlated_group_risk", 0.0),
            expires_at_candle=compute_expiry(T, self.time_invalidation_candles),
        )]

    def _detect_flag(self, ohlcv: pd.DataFrame):
        """Returns (direction, impulse_candle_index) or None."""
        n = len(ohlcv)
        if n < 20:
            return None

        atr_series = ATR().compute(ohlcv, period=14)
        atr_val = atr_series.dropna().iloc[-1] if not atr_series.dropna().empty else 0
        if atr_val == 0:
            return None

        # Look for impulse candle in the last 10 candles (excluding last FLAG_MAX_CANDLES)
        for i in range(n - FLAG_MAX_CANDLES - 1, n - FLAG_MAX_CANDLES - 6, -1):
            if i < 0:
                break
            candle = ohlcv.iloc[i]
            body = abs(float(candle["close"]) - float(candle["open"]))
            if body < FLAG_IMPULSE_ATR_MULT * atr_val:
                continue

            # Check consolidation after impulse
            flag_candles = ohlcv.iloc[i + 1:]
            n_flag = len(flag_candles)
            if n_flag < FLAG_MIN_CANDLES:
                continue

            # Volume should be declining in flag
            vols = flag_candles["volume"].values
            if len(vols) >= 2 and vols[-1] < vols[0]:
                direction = "long" if float(candle["close"]) > float(candle["open"]) else "short"
                return direction, i

        return None
