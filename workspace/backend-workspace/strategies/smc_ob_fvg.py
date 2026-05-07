"""
SMC Order Block + Fair Value Gap Strategy
==========================================
Entry triggers:
  - CHoCH aligned with 1H HTF bias
  - Price retesting a valid Order Block
  - FVG confluence within the OB zone

Entry:  Close of the candle that retests the OB/FVG zone
SL:     Below OB low × 0.997 (long) / Above OB high × 1.003 (short)
TP1:    1.5R from entry
TP2:    2.5R from entry

Satisfies: Requirements 1.2, 1.3, 1.4, 1.5, 5.1, 5.2, 5.3
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

import pandas as pd

from strategies.base import BaseStrategy
from strategies.registry import StrategyRegistry
from strategies.signal import Signal, ScoreBreakdown
from engine.smc import (
    compute_smc_score, find_order_block, find_fvg,
    detect_choch, detect_htf_bias,
)
from engine.scorer import SignalScorer, ScoreInput
from engine.context import compute_context_score
from engine.confluence import compute_confluence_bonus
from alert.invalidator import compute_expiry
from indicators.atr import ATR

logger = logging.getLogger(__name__)


@StrategyRegistry.register("smc_ob_fvg")
class SMCOrderBlockFVGStrategy(BaseStrategy):
    """
    Smart Money Concepts: Order Block + Fair Value Gap strategy.

    Requires at minimum:
    - Valid Order Block (not broken)
    - Price retesting the OB zone
    - 1H HTF bias alignment

    FVG confluence is a bonus — not required but increases score.

    Satisfies: Requirements 1.2, 1.3, 1.4, 1.5, 5.1, 5.2, 5.3
    """

    @property
    def name(self) -> str:
        return "smc_ob_fvg"

    def generate_signals(
        self,
        ohlcv: pd.DataFrame,
        context: dict,
    ) -> List[Signal]:
        """
        Generate signals from closed 15m candles.

        Args:
            ohlcv:   DataFrame of CLOSED 15m candles (index 0..T)
            context: Dict with ohlcv_1h, regime, funding_rate, etc.

        Returns:
            List of Signal objects (empty if no valid setup)

        Satisfies: Requirements 5.1, 5.2, 5.3
        """
        T = len(ohlcv) - 1
        self._check_no_lookahead(ohlcv, T)  # Req 5.3

        if len(ohlcv) < 20:
            return []

        ohlcv_1h = context.get("ohlcv_1h", pd.DataFrame())
        regime = context.get("regime", "RANGING")
        regime_multiplier = context.get("regime_multiplier", 1.0)
        funding_rate = context.get("funding_rate", 0.0)
        portfolio_heat = context.get("portfolio_heat", 0.0)
        correlated_group_risk = context.get("correlated_group_risk", 0.0)
        delta = context.get("delta", 0.0)
        poc = context.get("poc", 0.0)

        current_price = float(ohlcv.iloc[-1]["close"])
        candle_index = T

        # --- HTF bias (Req 1.4 — Context Filter) ---
        htf_bias = detect_htf_bias(ohlcv_1h) if not ohlcv_1h.empty else "neutral"
        if htf_bias == "neutral":
            return []  # no clear bias — skip

        # --- Order Block detection ---
        ob = find_order_block(ohlcv)
        if ob is None or not ob.valid:
            return []

        # --- OB must be retesting ---
        if not ob.is_price_retesting(current_price):
            return []

        # --- Direction must align with HTF bias ---
        if ob.type == "bullish" and htf_bias != "bullish":
            return []
        if ob.type == "bearish" and htf_bias != "bearish":
            return []

        direction = "long" if ob.type == "bullish" else "short"

        # --- PARABOLIC: suppress short (Req 13.5) ---
        if regime == "PARABOLIC" and direction == "short":
            return []

        # --- Compute scores ---
        smc_result = compute_smc_score(ohlcv, ohlcv_1h)
        ctx_result = compute_context_score(ohlcv_1h, direction, funding_rate)
        fvg = find_fvg(ohlcv)
        bonus = compute_confluence_bonus(ohlcv, ob=ob, fvg=fvg, poc=poc)

        # Order flow (simplified — use delta as proxy)
        of_score = min(15.0, abs(delta) / 100.0) if delta != 0 else 0.0

        scorer = SignalScorer.from_config(self.config) if hasattr(self.config, "strategy") \
            else SignalScorer()

        score_output = scorer.score(ScoreInput(
            order_flow=of_score,
            smc=smc_result.score,
            vsa=0.0,  # VSA computed separately in full pipeline
            context=ctx_result.score,
            bonus=bonus,
            regime_multiplier=regime_multiplier,
            direction=direction,
            regime=regime,
        ))

        if score_output.suppressed:
            return []

        # --- Build trade levels ---
        entry = current_price
        if direction == "long":
            sl = ob.low * 0.997
            tp1 = entry + (entry - sl) * 1.5
            tp2 = entry + (entry - sl) * 2.5
        else:
            sl = ob.high * 1.003
            tp1 = entry - (sl - entry) * 1.5
            tp2 = entry - (sl - entry) * 2.5

        # Validate R:R
        sl_dist = abs(entry - sl)
        if sl_dist == 0:
            return []

        expires_at = compute_expiry(
            candle_index,
            self.time_invalidation_candles,
        )

        signal = Signal(
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
                order_flow=of_score,
                smc=smc_result.score,
                vsa=0.0,
                context=ctx_result.score,
                bonus=bonus,
            ),
            classification=score_output.classification,
            regime=regime,
            regime_multiplier=regime_multiplier,
            funding_rate=funding_rate,
            portfolio_heat=portfolio_heat,
            correlated_group_risk=correlated_group_risk,
            expires_at_candle=expires_at,
        )

        return [signal]
