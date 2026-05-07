"""
Inside Bar Strategy
====================
Candle[T].high < Candle[T-1].high AND Candle[T].low > Candle[T-1].low
Entry on breakout of the mother bar in the direction of HTF bias.

Satisfies: Requirements 1.2, 1.3, 5.1
"""
from __future__ import annotations
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


@StrategyRegistry.register("inside_bar")
class InsideBarStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "inside_bar"

    def generate_signals(self, ohlcv: pd.DataFrame, context: dict) -> List[Signal]:
        T = len(ohlcv) - 1
        self._check_no_lookahead(ohlcv, T)
        if len(ohlcv) < 10:
            return []

        current = ohlcv.iloc[-1]
        mother = ohlcv.iloc[-2]
        ohlcv_1h = context.get("ohlcv_1h", pd.DataFrame())
        regime = context.get("regime", "RANGING")
        regime_multiplier = context.get("regime_multiplier", 1.0)
        funding_rate = context.get("funding_rate", 0.0)

        # Inside bar condition
        if not (float(current["high"]) < float(mother["high"]) and
                float(current["low"]) > float(mother["low"])):
            return []

        htf_bias = detect_htf_bias(ohlcv_1h) if not ohlcv_1h.empty else "neutral"
        if htf_bias == "neutral":
            return []

        direction = "long" if htf_bias == "bullish" else "short"
        if regime == "PARABOLIC" and direction == "short":
            return []

        ctx_result = compute_context_score(ohlcv_1h, direction, funding_rate)
        scorer = SignalScorer.from_config(self.config) if hasattr(self.config, "strategy") else SignalScorer()
        score_output = scorer.score(ScoreInput(
            order_flow=0, smc=8.0, vsa=0, context=ctx_result.score, bonus=0,
            regime_multiplier=regime_multiplier, direction=direction, regime=regime,
        ))
        if score_output.suppressed:
            return []

        entry = float(current["close"])
        if direction == "long":
            sl = float(mother["low"]) * 0.998
            tp1 = entry + (entry - sl) * 1.5
            tp2 = entry + (entry - sl) * 2.5
        else:
            sl = float(mother["high"]) * 1.002
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
            score_breakdown=ScoreBreakdown(order_flow=0, smc=8.0, vsa=0, context=ctx_result.score, bonus=0),
            classification=score_output.classification, regime=regime,
            regime_multiplier=regime_multiplier, funding_rate=funding_rate,
            portfolio_heat=context.get("portfolio_heat", 0.0),
            correlated_group_risk=context.get("correlated_group_risk", 0.0),
            expires_at_candle=compute_expiry(T, self.time_invalidation_candles),
        )]
