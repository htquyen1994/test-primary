"""
RSI Momentum Strategy
======================
Long:  RSI(14) crosses above 50 from below while price > EMA(50)
Short: RSI(14) crosses below 50 from above while price < EMA(50)

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
from indicators.rsi import RSI
from indicators.ema import EMA


@StrategyRegistry.register("rsi_momentum")
class RSIMomentumStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "rsi_momentum"

    def generate_signals(self, ohlcv: pd.DataFrame, context: dict) -> List[Signal]:
        T = len(ohlcv) - 1
        self._check_no_lookahead(ohlcv, T)
        if len(ohlcv) < 55:
            return []

        ohlcv_1h = context.get("ohlcv_1h", pd.DataFrame())
        regime = context.get("regime", "RANGING")
        regime_multiplier = context.get("regime_multiplier", 1.0)
        funding_rate = context.get("funding_rate", 0.0)

        rsi_series = RSI().compute(ohlcv, period=14)
        ema_series = EMA().compute(ohlcv, period=50)

        if rsi_series.dropna().empty or ema_series.dropna().empty:
            return []

        rsi_now = float(rsi_series.iloc[-1])
        rsi_prev = float(rsi_series.iloc[-2])
        ema_now = float(ema_series.iloc[-1])
        price_now = float(ohlcv.iloc[-1]["close"])

        # Long: RSI crosses above 50 AND price > EMA(50)
        if rsi_prev < 50 and rsi_now >= 50 and price_now > ema_now:
            direction = "long"
        # Short: RSI crosses below 50 AND price < EMA(50)
        elif rsi_prev > 50 and rsi_now <= 50 and price_now < ema_now:
            direction = "short"
        else:
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
            order_flow=0, smc=0, vsa=0, context=ctx_result.score, bonus=0,
            regime_multiplier=regime_multiplier, direction=direction, regime=regime,
        ))
        if score_output.suppressed:
            return []

        entry = price_now
        atr_approx = abs(float(ohlcv.iloc[-1]["high"]) - float(ohlcv.iloc[-1]["low"]))
        sl = entry - atr_approx * 1.5 if direction == "long" else entry + atr_approx * 1.5
        tp1 = entry + atr_approx * 2.25 if direction == "long" else entry - atr_approx * 2.25
        tp2 = entry + atr_approx * 3.75 if direction == "long" else entry - atr_approx * 3.75

        if abs(entry - sl) == 0:
            return []

        return [Signal(
            strategy_name=self.name, asset=context.get("asset", "UNKNOWN"),
            timeframe=context.get("timeframe", "15m"), direction=direction,
            candle_index=T, candle_timestamp=datetime.now(timezone.utc),
            entry_price=entry, stop_loss=sl, take_profit_1=tp1, take_profit_2=tp2,
            raw_score=score_output.raw_score, final_score=score_output.final_score,
            score_breakdown=ScoreBreakdown(order_flow=0, smc=0, vsa=0, context=ctx_result.score, bonus=0),
            classification=score_output.classification, regime=regime,
            regime_multiplier=regime_multiplier, funding_rate=funding_rate,
            portfolio_heat=context.get("portfolio_heat", 0.0),
            correlated_group_risk=context.get("correlated_group_risk", 0.0),
            expires_at_candle=compute_expiry(T, self.time_invalidation_candles),
        )]
