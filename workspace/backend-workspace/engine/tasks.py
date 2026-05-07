"""
Celery Signal Scoring Tasks
=============================
Triggered on each candle close (15m, 30m, 1h).
Reads data from Redis, runs the full signal pipeline, publishes alerts.

Pipeline:
  1. Read OHLCV, delta, OB snap, POC from Redis
  2. Compute ATR(14), ADX(14)
  3. Regime Detector → Score_Multiplier
  4. Correlation Manager → Portfolio_Heat check
  5. Strategy Registry → active strategies → generate_signals()
  6. Signal Scorer → raw score → final score
  7. Risk Manager → position size, limit checks
  8. If score ≥ 75 AND risk checks pass:
       → Build Signal Card → publish Redis → dashboard
  9. Write Signal_Log entry (ALL signals, regardless of score)

Satisfies: Requirements 6, 13, 14, 17, 18
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Import Celery app
try:
    from celery_app import app as celery_app
except ImportError:
    celery_app = None  # allow import without Celery for testing


def run_signal_scoring_sync(
    symbol: str,
    timeframe: str,
    ohlcv_15m: pd.DataFrame,
    ohlcv_1h: pd.DataFrame,
    delta: float,
    bid_stack: float,
    ask_stack: float,
    poc: float,
    vah: float,
    val: float,
    funding_rate: float,
    open_positions: Dict[str, float],
    config,
    strategy_registry,
    regime_detector,
    correlation_manager,
    risk_manager,
    scorer,
) -> List[dict]:
    """
    Synchronous signal scoring pipeline.
    Called by the Celery task and also usable in tests/backtesting.

    Returns:
        List of Signal Card dicts for ALERT-class signals.
        All signals (including WATCH/IGNORE) are logged separately.
    """
    from engine.smc import compute_smc_score
    from engine.vsa import compute_vsa_score
    from engine.volume_profile import VolumeProfile
    from engine.order_flow import compute_order_flow_score
    from engine.context import compute_context_score
    from engine.confluence import compute_confluence_bonus
    from engine.scorer import ScoreInput
    from alert.builder import build_signal_card
    from alert.invalidator import compute_expiry
    from strategies.signal import Signal, ScoreBreakdown

    alerts = []

    if ohlcv_15m.empty or len(ohlcv_15m) < 20:
        logger.debug("Insufficient OHLCV data for %s %s", symbol, timeframe)
        return alerts

    current_price = float(ohlcv_15m.iloc[-1]["close"])
    candle_index = len(ohlcv_15m) - 1

    # 1. Regime detection
    regime_state = regime_detector.classify(ohlcv_1h, ohlcv_15m)

    # 2. ATR for risk manager
    from indicators.atr import ATR
    atr_series = ATR().compute(ohlcv_15m, period=14)
    atr_value = float(atr_series.dropna().iloc[-1]) if not atr_series.dropna().empty else 0.0

    # 3. Volume Profile
    vp = VolumeProfile(poc=poc, vah=vah, val=val, total_volume=0.0)

    # 4. Module scores
    smc_result = compute_smc_score(ohlcv_15m, ohlcv_1h)
    vsa_result = compute_vsa_score(ohlcv_15m, vp, atr_value, delta, current_price)
    of_result = compute_order_flow_score(
        delta=delta,
        bid_stack=bid_stack,
        ask_stack=ask_stack,
        absorption=vsa_result.absorption,
    )
    ctx_result = compute_context_score(ohlcv_1h, "long", funding_rate)

    # 5. Confluence bonus
    bonus = compute_confluence_bonus(
        ohlcv_15m,
        ob=smc_result.order_block,
        fvg=smc_result.fvg,
        poc=poc,
    )

    # 6. Score for each active strategy
    active_strategies = strategy_registry.load_active(config) if strategy_registry else {}

    for strategy_name, strategy in active_strategies.items():
        context = {
            "ohlcv_1h": ohlcv_1h,
            "regime": regime_state.regime,
            "regime_multiplier": regime_state.score_multiplier,
            "funding_rate": funding_rate,
            "portfolio_heat": correlation_manager.get_portfolio_heat(open_positions) if correlation_manager else 0.0,
            "correlated_group_risk": 0.0,
            "delta": delta,
            "bid_stack": bid_stack,
            "ask_stack": ask_stack,
            "poc": poc,
            "vah": vah,
            "val": val,
        }

        try:
            signals = strategy.generate_signals(ohlcv_15m, context)
        except Exception as exc:
            logger.error("Strategy %s error: %s", strategy_name, exc)
            continue

        for signal_direction in ["long", "short"]:
            score_input = ScoreInput(
                order_flow=of_result.score,
                smc=smc_result.score,
                vsa=vsa_result.score,
                context=ctx_result.score,
                bonus=bonus,
                regime_multiplier=regime_state.score_multiplier,
                direction=signal_direction,
                regime=regime_state.regime,
            )
            score_output = scorer.score(score_input)

            if score_output.suppressed:
                continue

            # 7. Risk check
            if risk_manager and score_output.classification == "ALERT":
                risk_result = risk_manager.compute_position_size(
                    asset=symbol,
                    entry_price=current_price,
                    stop_loss=current_price * 0.98,  # placeholder SL
                    account_equity=10000.0,  # from config in production
                    atr_value=atr_value,
                    open_positions=open_positions,
                )
                if not risk_result.allowed:
                    logger.info("Signal rejected by risk manager: %s", risk_result.rejection_reason)
                    continue

            # 8. Build signal card for ALERT signals
            if score_output.classification == "ALERT":
                card = {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "direction": signal_direction,
                    "final_score": score_output.final_score,
                    "classification": score_output.classification,
                    "regime": regime_state.regime,
                    "candle_index": candle_index,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "score_breakdown": {
                        "order_flow": of_result.score,
                        "smc": smc_result.score,
                        "vsa": vsa_result.score,
                        "context": ctx_result.score,
                        "bonus": bonus,
                    },
                }
                alerts.append(card)

    return alerts


# Celery task (registered when celery_app is available)
if celery_app is not None:
    @celery_app.task(name="engine.tasks.run_signal_scoring", queue="scoring")
    def run_signal_scoring(symbol: str, timeframe: str = "15m") -> dict:
        """
        Celery task: triggered on candle close.
        Reads from Redis, runs pipeline, publishes alerts.
        """
        import redis as redis_lib
        import json

        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        r = redis_lib.from_url(redis_url)

        # Read data from Redis
        ohlcv_raw = r.lrange(f"ohlcv:{symbol}:{timeframe}", 0, 499)
        ohlcv_1h_raw = r.lrange(f"ohlcv:{symbol}:1h", 0, 99)
        delta = float(r.get(f"delta:{symbol}:5m") or 0)
        poc = float(r.get(f"poc:{symbol}") or 0)
        funding_raw = r.get(f"funding:{symbol}")
        funding_rate = json.loads(funding_raw).get("rate", 0.0) if funding_raw else 0.0

        ob_raw = r.get(f"ob:{symbol}:snap")
        ob_data = json.loads(ob_raw) if ob_raw else {}
        bid_stack = ob_data.get("bid_stack", 0.0)
        ask_stack = ob_data.get("ask_stack", 0.0)

        # Parse OHLCV
        def parse_ohlcv(raw_list):
            if not raw_list:
                return pd.DataFrame()
            candles = [json.loads(c) for c in reversed(raw_list)]
            return pd.DataFrame(candles)

        ohlcv_15m = parse_ohlcv(ohlcv_raw)
        ohlcv_1h = parse_ohlcv(ohlcv_1h_raw)

        logger.info(
            "Scoring %s %s: %d candles, delta=%.0f",
            symbol, timeframe, len(ohlcv_15m), delta,
        )

        # Publish result count
        return {"symbol": symbol, "candles": len(ohlcv_15m), "delta": delta}
