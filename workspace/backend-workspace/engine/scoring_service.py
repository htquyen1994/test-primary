"""
Scoring Service
================
Listens for candle_close events from Redis pub/sub.
Runs the full signal scoring pipeline on each closed candle.
Publishes results to logs:channel and alerts:channel.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timezone

from trading_core.cache import get_redis, RedisKeys

logger = logging.getLogger(__name__)


class ScoringService:
    """
    Subscribes to candle_close events and runs the full scoring pipeline.
    Runs in a background thread to avoid blocking the event loop.
    """

    def __init__(self) -> None:
        self._loop = None

    def _get_redis(self):
        return get_redis()

    async def start(self) -> None:
        """Start the scoring trigger in a background thread."""
        self._loop = asyncio.get_event_loop()
        r = self._get_redis()
        pubsub = r.pubsub()
        pubsub.subscribe(RedisKeys.Channels.CANDLE_CLOSE)
        logger.info("ScoringService listening on %s channel...", RedisKeys.Channels.CANDLE_CLOSE)

        def listen():
            for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                    symbol = data["symbol"]
                    timeframe = data["timeframe"]
                    close = data["close"]
                    logger.info(
                        "Candle closed: %s %s @ %.4f — scoring...",
                        symbol, timeframe, close,
                    )
                    asyncio.run_coroutine_threadsafe(
                        self._run_cycle(symbol, timeframe),
                        self._loop,
                    )
                except Exception as exc:
                    logger.error("Scoring trigger error: %s", exc)

        t = threading.Thread(target=listen, daemon=True, name="scoring-trigger")
        t.start()

        # Keep alive
        while True:
            await asyncio.sleep(60)

    async def _run_cycle(self, symbol: str, timeframe: str) -> None:
        """Run one full scoring cycle for a symbol/timeframe."""
        import pandas as pd
        from indicators.atr import ATR
        from indicators.adx import ADX
        from engine.regime_detector import RegimeDetector
        from engine.smc import compute_smc_score
        from engine.vsa import compute_vsa_score
        from engine.volume_profile import compute_volume_profile
        from engine.order_flow import compute_order_flow_score
        from engine.context import compute_context_score
        from engine.confluence import compute_confluence_bonus
        from engine.scorer import SignalScorer, ScoreInput
        from engine.log_publisher import build_log_entry, publish_log
        from engine.mtf_bias import detect_daily_bias
        from engine.btc_guard import BTCVolatilityGuard
        from engine.filters import FilterRegistry

        r = self._get_redis()

        # --- Read inputs from Redis ---
        raw = r.lrange(RedisKeys.ohlcv(symbol, timeframe), 0, 499)
        if len(raw) < 20:
            logger.debug("Not enough candles for %s %s (%d)", symbol, timeframe, len(raw))
            return

        ohlcv = pd.DataFrame([json.loads(c) for c in reversed(raw)])

        raw_1h = r.lrange(RedisKeys.ohlcv(symbol, "1h"), 0, 99)
        ohlcv_1h = pd.DataFrame([json.loads(c) for c in reversed(raw_1h)]) if raw_1h else pd.DataFrame()

        raw_4h = r.lrange(RedisKeys.ohlcv(symbol, "4h"), 0, 199)
        ohlcv_4h = pd.DataFrame([json.loads(c) for c in reversed(raw_4h)]) if raw_4h else pd.DataFrame()

        raw_daily = r.lrange(RedisKeys.ohlcv(symbol, "1d"), 0, 249)
        ohlcv_daily = pd.DataFrame([json.loads(c) for c in reversed(raw_daily)]) if raw_daily else pd.DataFrame()

        ob_raw = r.get(RedisKeys.ob_snap(symbol))
        ob_data = json.loads(ob_raw) if ob_raw else {}
        bid_stack = ob_data.get("bid_stack", 0.0)
        ask_stack = ob_data.get("ask_stack", 0.0)
        bid_dominant = ob_data.get("bid_dominant", False)

        # Compute actual age from updated_at timestamp
        import time as _time
        updated_at = ob_data.get("updated_at", 0)
        ob_age = (_time.time() - updated_at) if updated_at else 999
        if ob_age > 30:
            logger.warning("OB data stale for %s (%.0fs old) — using with caution", symbol, ob_age)

        # Task 30.4: detect when Order Book is completely unavailable
        order_book_available = not (bid_stack == 0.0 and ask_stack == 0.0)
        if not order_book_available:
            logger.warning(
                "Order Book unavailable for %s — bid_stack=0 ask_stack=0 — score will be capped at 60",
                symbol,
            )

        delta = float(r.get(RedisKeys.delta(symbol)) or 0)

        # Snapshot delta to history BEFORE resetting (Task 34.2)
        delta_history_raw = r.lrange(RedisKeys.delta_history(symbol), 0, -1)
        delta_history = [float(v) for v in delta_history_raw if v]
        r.rpush(RedisKeys.delta_history(symbol), str(delta))
        r.ltrim(RedisKeys.delta_history(symbol), -96, -1)
        r.expire(RedisKeys.delta_history(symbol), 25 * 3600)

        # Compute dynamic threshold (Task 34.3)
        from engine.order_flow import compute_dynamic_delta_threshold
        dynamic_threshold = compute_dynamic_delta_threshold(delta_history)

        # Reset delta after reading — measure pressure within each candle
        r.set(RedisKeys.delta(symbol), "0", ex=300)

        funding_raw = r.get(RedisKeys.funding(symbol))
        funding_rate = json.loads(funding_raw).get("rate", 0.0) if funding_raw else 0.0

        logger.debug(
            "Inputs %s: delta=%.2f bid=%.3f ask=%.3f dominant=%s funding=%.6f",
            symbol, delta, bid_stack, ask_stack, bid_dominant, funding_rate,
        )

        try:
            # --- Compute indicators ---
            atr_val = self._safe_last(ATR().compute(ohlcv, period=14))
            adx_val = self._safe_last(ADX().compute(
                ohlcv_1h if not ohlcv_1h.empty else ohlcv, period=14
            ))

            # --- Regime ---
            regime_state = RegimeDetector().classify(
                ohlcv_1h if not ohlcv_1h.empty else ohlcv, ohlcv
            )

            signal_direction = "long"  # TODO: derive from CHoCH direction

            # --- Module scores (needed for filter context) ---
            vp = compute_volume_profile(ohlcv)
            smc = compute_smc_score(ohlcv, ohlcv_1h if not ohlcv_1h.empty else ohlcv)
            vsa = compute_vsa_score(ohlcv, vp, atr_val, delta)

            # --- Build filter context ---
            raw_btc = r.lrange(RedisKeys.ohlcv("BTC/USDT", "15m"), 0, 9)
            ohlcv_btc = pd.DataFrame([json.loads(c) for c in reversed(raw_btc)]) if raw_btc else pd.DataFrame()

            filter_context = {
                "symbol": symbol,
                "timeframe": timeframe,
                "signal_direction": signal_direction,
                "ohlcv": ohlcv,
                "ohlcv_1h": ohlcv_1h,
                "ohlcv_4h": ohlcv_4h,
                "ohlcv_daily": ohlcv_daily,
                "ohlcv_btc": ohlcv_btc,
                "regime_state": regime_state,
                "htf_bias_1h": smc.htf_bias,
                "delta": delta,
                "bid_stack": bid_stack,
                "ask_stack": ask_stack,
                "funding_rate": funding_rate,
                "r": r,
            }

            # --- Run filter pipeline ---
            # Load active filters from config (default: all 4 enabled)
            active_filter_names = self._get_active_filters()
            active_filters = FilterRegistry.load_active(active_filter_names)

            combined_size_mult = 1.0
            filter_warnings = []
            filter_extras = {}

            for f in active_filters:
                result = f.apply(filter_context)
                if not result.passed:
                    logger.info(
                        "Filter BLOCK %s %s [%s]: %s",
                        symbol, timeframe, f.name, result.block_reason,
                    )
                    # Publish minimal log and return
                    log_entry = build_log_entry(
                        symbol=symbol, timeframe=timeframe,
                        candle_timestamp=datetime.now(timezone.utc).isoformat(),
                        regime=regime_state.regime,
                        regime_multiplier=regime_state.score_multiplier,
                        adx_value=0, atr_value=0,
                        of_score=0, smc_score=0, vsa_score=0, ctx_score=0, bonus=0,
                        raw_score=0, final_score=0, classification="IGNORE",
                        delta=delta, ob_retested=False, fvg_touched=False,
                        choch_aligned=False, htf_bias=smc.htf_bias,
                        no_supply=False, effort_vs_result=False, at_poc=False,
                        funding_rate=funding_rate,
                        extra={"filter_block": f.name, "block_reason": result.block_reason},
                    )
                    publish_log(r, log_entry)
                    return

                combined_size_mult *= result.size_multiplier
                if result.warning:
                    filter_warnings.append(result.warning)
                filter_extras[f.name] = result.to_dict()

            # Store daily bias in Redis for frontend (TTL 4h)
            daily_bias = detect_daily_bias(ohlcv_daily) if not ohlcv_daily.empty else "NEUTRAL"
            r.set(RedisKeys.daily_bias(symbol), daily_bias, ex=14400)
            of = compute_order_flow_score(
                delta=delta,
                bid_stack=bid_stack,
                ask_stack=ask_stack,
                absorption=vsa.absorption or bid_dominant,
                delta_threshold=dynamic_threshold,
            )
            ctx = compute_context_score(
                ohlcv_1h if not ohlcv_1h.empty else ohlcv,
                "long",
                funding_rate,
            )
            bonus = compute_confluence_bonus(ohlcv, smc.order_blocks or smc.order_block, smc.fvg, vp.poc)

            # --- Module scores ---
            of = compute_order_flow_score(
                delta=delta,
                bid_stack=bid_stack,
                ask_stack=ask_stack,
                absorption=vsa.absorption or bid_dominant,
                delta_threshold=dynamic_threshold,
            )
            ctx = compute_context_score(
                ohlcv_1h if not ohlcv_1h.empty else ohlcv,
                "long",
                funding_rate,
            )
            bonus = compute_confluence_bonus(ohlcv, smc.order_blocks or smc.order_block, smc.fvg, vp.poc)

            # --- Final score ---
            score = SignalScorer().score(ScoreInput(
                order_flow=of.score,
                smc=smc.score,
                vsa=vsa.score,
                context=ctx.score,
                bonus=bonus,
                regime_multiplier=regime_state.score_multiplier,
                direction=signal_direction,
                regime=regime_state.regime,
                order_book_available=order_book_available,
            ))

            # Apply filter score adjustments (sum of all filter adjustments)
            total_score_adj = sum(
                r.score_adjustment for r in filter_extras.values()
                if isinstance(r, dict) and r.get("score_adjustment", 0) != 0
            )
            if total_score_adj != 0:
                adjusted_final = max(0, min(100, score.final_score + int(total_score_adj)))
                score = score.__class__(
                    raw_score=score.raw_score,
                    final_score=adjusted_final,
                    classification=SignalScorer().classify(adjusted_final),
                    suppressed=score.suppressed,
                    data_quality=score.data_quality,
                )

            logger.info(
                "Scored %s %s: regime=%s OF=%.0f SMC=%.0f VSA=%.0f CTX=%.0f → %d/100 [%s]%s | delta=%.2f threshold=%.0f | size=%.2f",
                symbol, timeframe, regime_state.regime,
                of.score, smc.score, vsa.score, ctx.score,
                score.final_score, score.classification,
                " ⚠ OB unavailable" if not order_book_available else "",
                delta, dynamic_threshold, combined_size_mult,
            )

            # --- Publish log ---
            log_entry = build_log_entry(
                symbol=symbol, timeframe=timeframe,
                candle_timestamp=datetime.now(timezone.utc).isoformat(),
                regime=regime_state.regime,
                regime_multiplier=regime_state.score_multiplier,
                adx_value=adx_val, atr_value=atr_val,
                of_score=of.score, smc_score=smc.score,
                vsa_score=vsa.score, ctx_score=ctx.score, bonus=bonus,
                raw_score=score.raw_score, final_score=score.final_score,
                classification=score.classification,
                delta=delta, delta_threshold=dynamic_threshold,
                ob_retested=smc.ob_retested,
                fvg_touched=smc.fvg_touched, choch_aligned=smc.choch_aligned,
                htf_bias=smc.htf_bias, no_supply=vsa.no_supply,
                effort_vs_result=vsa.effort_vs_result, at_poc=vsa.at_poc,
                funding_rate=funding_rate,
                extra={
                    "daily_bias": daily_bias,
                    "size_multiplier": combined_size_mult,
                    "filter_warnings": filter_warnings,
                    "filters": filter_extras,
                },
            )
            publish_log(r, log_entry)

            # --- Persist to SQL Server ---
            self._persist_signal(symbol, timeframe, ohlcv, score, smc, vsa, of, ctx, bonus, regime_state, funding_rate)

            # --- Publish ALERT ---
            if score.classification == "ALERT":
                self._publish_alert(
                    r, symbol, timeframe, ohlcv, score, smc, vsa, of, ctx, bonus,
                    regime_state, order_book_available,
                    combined_size_mult=combined_size_mult,
                    daily_bias=daily_bias,
                    filter_warnings=filter_warnings,
                )

        except Exception as exc:
            logger.error("Scoring error %s %s: %s", symbol, timeframe, exc, exc_info=True)

    def _safe_last(self, series) -> float:
        """Return last non-NaN value from a pandas Series, or 0.0."""
        valid = series.dropna()
        return float(valid.iloc[-1]) if not valid.empty else 0.0

    def _persist_signal(self, symbol, timeframe, ohlcv, score, smc, vsa, of, ctx, bonus, regime_state, funding_rate):
        """Persist signal to SQL Server signal_log table."""
        try:
            from db.connection import get_session_factory
            from api.signal_log_writer import write_signal_log
            from strategies.signal import Signal, ScoreBreakdown

            db = get_session_factory()()
            signal_obj = Signal(
                strategy_name="scoring_engine",
                asset=symbol, timeframe=timeframe, direction="long",
                candle_index=len(ohlcv) - 1,
                candle_timestamp=datetime.now(timezone.utc),
                entry_price=float(ohlcv.iloc[-1]["close"]),
                stop_loss=float(ohlcv.iloc[-1]["close"]) * 0.98,
                take_profit_1=float(ohlcv.iloc[-1]["close"]) * 1.03,
                take_profit_2=float(ohlcv.iloc[-1]["close"]) * 1.05,
                raw_score=score.raw_score, final_score=score.final_score,
                score_breakdown=ScoreBreakdown(
                    order_flow=of.score, smc=smc.score,
                    vsa=vsa.score, context=ctx.score, bonus=bonus,
                ),
                classification=score.classification,
                regime=regime_state.regime,
                regime_multiplier=regime_state.score_multiplier,
                funding_rate=funding_rate,
                portfolio_heat=0.0, correlated_group_risk=0.0,
                expires_at_candle=len(ohlcv) + 15,
            )
            write_signal_log(signal_obj, db)
            db.close()
        except Exception as exc:
            logger.warning("Failed to persist signal_log: %s", exc)

    def _publish_alert(self, r, symbol, timeframe, ohlcv, score, smc, vsa, of, ctx, bonus, regime_state, order_book_available=True, combined_size_mult=1.0, daily_bias="NEUTRAL", filter_warnings=None):
        """Publish ALERT signal to Redis alerts:channel."""
        close = float(ohlcv.iloc[-1]["close"])
        r.publish(RedisKeys.Channels.ALERTS, json.dumps({
            "signal_id": f"{symbol}_{timeframe}_{int(time.time())}",
            "asset": symbol, "timeframe": timeframe, "direction": "long",
            "final_score": score.final_score, "classification": "ALERT",
            "regime": regime_state.regime,
            "entry_price": close,
            "stop_loss": close * 0.98,
            "take_profit_1": close * 1.03,
            "take_profit_2": close * 1.05,
            "gross_rr": 1.5, "net_rr": 1.3,
            "score_breakdown": {
                "order_flow": of.score, "smc": smc.score,
                "vsa": vsa.score, "context": ctx.score, "bonus": bonus,
            },
            "data_quality": score.data_quality,
            "ob_warning": None if order_book_available else "⚠ Order Flow data unavailable — score capped at 60",
            "daily_bias": daily_bias,
            "size_multiplier": combined_size_mult,
            "filter_warnings": filter_warnings or [],
            "expires_at_candle": 115,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }))
        logger.info("ALERT published: %s %s score=%d size=%.2f", symbol, timeframe, score.final_score, combined_size_mult)

    def _get_active_filters(self) -> list:
        """
        Get active filter names from config (DB → config.yaml → default).
        Default: all 4 filters enabled.
        """
        try:
            from config.config_resolver import ConfigResolver
            from config.config_system import ConfigSystem
            import os
            cfg = ConfigSystem(os.environ.get("CONFIG_PATH", "config.yaml"))
            resolver = ConfigResolver(cfg)
            unified = resolver.get_unified_config()
            filters_cfg = unified.get("filters", {})
            return filters_cfg.get("active", ["mtf_bias", "btc_guard", "circuit_breaker", "daily_bias"])
        except Exception:
            return ["mtf_bias", "btc_guard", "circuit_breaker", "daily_bias"]
