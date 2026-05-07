"""
Quasimodo (QM) Strategy
========================
Reversal pattern: HH → LH → LL → return to prior S/R zone.

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


@StrategyRegistry.register("quasimodo")
class QuasimodoStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "quasimodo"

    def generate_signals(self, ohlcv: pd.DataFrame, context: dict) -> List[Signal]:
        T = len(ohlcv) - 1
        self._check_no_lookahead(ohlcv, T)
        if len(ohlcv) < 20:
            return []

        ohlcv_1h = context.get("ohlcv_1h", pd.DataFrame())
        regime = context.get("regime", "RANGING")
        regime_multiplier = context.get("regime_multiplier", 1.0)
        funding_rate = context.get("funding_rate", 0.0)

        direction = self._detect_qm(ohlcv)
        if direction is None:
            return []

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
            order_flow=0, smc=15.0, vsa=0, context=ctx_result.score, bonus=0,
            regime_multiplier=regime_multiplier, direction=direction, regime=regime,
        ))
        if score_output.suppressed:
            return []

        entry = float(ohlcv.iloc[-1]["close"])
        recent_lows = ohlcv.iloc[-10:]["low"].values
        recent_highs = ohlcv.iloc[-10:]["high"].values

        if direction == "long":
            sl = float(np.min(recent_lows)) * 0.997
            tp1 = entry + (entry - sl) * 1.5
            tp2 = entry + (entry - sl) * 2.5
        else:
            sl = float(np.max(recent_highs)) * 1.003
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
            score_breakdown=ScoreBreakdown(order_flow=0, smc=15.0, vsa=0, context=ctx_result.score, bonus=0),
            classification=score_output.classification, regime=regime,
            regime_multiplier=regime_multiplier, funding_rate=funding_rate,
            portfolio_heat=context.get("portfolio_heat", 0.0),
            correlated_group_risk=context.get("correlated_group_risk", 0.0),
            expires_at_candle=compute_expiry(T, self.time_invalidation_candles),
        )]

    def _detect_qm(self, ohlcv: pd.DataFrame) -> str | None:
        """
        Simplified QM detection: HH → LH → LL sequence in recent candles.
        Returns "long" (bullish QM) or "short" (bearish QM) or None.
        """
        if len(ohlcv) < 8:
            return None
        highs = ohlcv["high"].values[-8:].astype(float)
        lows = ohlcv["low"].values[-8:].astype(float)

        # Bearish QM: HH → LH → LL (price returns to prior resistance)
        if highs[-4] > highs[-6] and highs[-2] < highs[-4] and lows[-1] < lows[-3]:
            return "short"
        # Bullish QM: LL → HL → HH (price returns to prior support)
        if lows[-4] < lows[-6] and lows[-2] > lows[-4] and highs[-1] > highs[-3]:
            return "long"
        return None
