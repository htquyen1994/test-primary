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

# ATR-based SL/TP — replaces hardcoded percentage offsets
SL_ATR_MULT = 1.5          # SL distance = 1.5 × ATR(14)
TP1_RR = 2.0               # Gross R:R target for TP1 (yields ~1.65 net after 0.2% fees at 1.5% SL)
TP2_RR = 3.0               # Gross R:R target for TP2
MIN_NET_RR = 1.5           # Minimum net R:R (after fees) required to publish an ALERT
DEFAULT_FEE_RATE = 0.001   # 0.1% taker fee per fill (entry + exit = 0.2% round-trip)


class ScoringService:
    """
    Subscribes to candle_close events and runs the full scoring pipeline.
    Runs in a background thread to avoid blocking the event loop.
    """

    # Refresh trading-params cache every N candle events to avoid hitting DB each time.
    _TP_CACHE_TTL = 30   # refresh after 30 candle events

    def __init__(self, config=None, audit_client=None) -> None:
        self._loop = None
        self._config = config  # ConfigSystem instance; None → use module-level defaults
        self._audit_client = audit_client
        from engine.correlation_manager import CorrelationManager
        self._correlation_manager = CorrelationManager()
        # Trading-params cache (weights, thresholds) — refreshed periodically
        self._tp_cache: dict = {}
        self._tp_cache_counter: int = 0

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
                    # Update heartbeat (TTL 5min — shows pipeline is alive)
                    try:
                        r.set("pipeline:heartbeat", datetime.now(timezone.utc).isoformat(), ex=300)
                    except Exception:
                        pass
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

    def _refresh_tp_cache(self) -> None:
        """Refresh trading-params cache from DB. Called every _TP_CACHE_TTL cycles."""
        try:
            from db.connection import get_session_factory
            from config.config_service import get_active_trading_params
            db = get_session_factory()()
            try:
                self._tp_cache = get_active_trading_params(db)
            finally:
                db.close()
        except Exception as exc:
            logger.debug("TradingParams cache refresh failed (%s) — keeping previous values", exc)
            if not self._tp_cache:
                self._tp_cache = {}  # first-time failure → empty dict → defaults apply

    async def _run_cycle(self, symbol: str, timeframe: str) -> None:
        """Run one full scoring cycle for a symbol/timeframe."""
        # Refresh trading-params cache periodically (weights, thresholds)
        self._tp_cache_counter += 1
        if self._tp_cache_counter >= self._TP_CACHE_TTL or not self._tp_cache:
            self._refresh_tp_cache()
            self._tp_cache_counter = 0

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

        # Update correlation matrix with latest 1H closes (TASK-11)
        if not ohlcv_1h.empty:
            self._correlation_manager.update(symbol, ohlcv_1h)

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

        _OB_STALE_THRESHOLD = 60  # seconds
        if ob_age > _OB_STALE_THRESHOLD:
            order_book_available = False
            logger.warning(
                "Order Book stale for %s (%.0fs old > %ds threshold) — capping score at 60",
                symbol, ob_age, _OB_STALE_THRESHOLD,
            )
        elif bid_stack == 0.0 and ask_stack == 0.0:
            order_book_available = False
            logger.warning(
                "Order Book unavailable for %s — bid_stack=0 ask_stack=0 — score will be capped at 60",
                symbol,
            )
        else:
            order_book_available = True

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

            _audit = {
                "type": "signal_snapshot",
                "symbol": symbol, "timeframe": timeframe,
                "timestamp_candle_close": datetime.now(timezone.utc).isoformat(),
                "signal_result": "NO_SIGNAL",
                "final_score": 0,
                "score_breakdown": None,
                "regime": regime_state.regime,
                "regime_multiplier": regime_state.score_multiplier,
                "btc_guard_active": False,
                "circuit_breaker_locked": False,
                "blocking_reason": None,
                "blocking_detail": None,
                "entry_price_proposed": None,
                "sl_proposed": None,
                "tp1_proposed": None,
                "tp2_proposed": None,
                "atr_value": atr_val,
                "adx_value": adx_val,
                "delta_value": delta,
                "delta_threshold": dynamic_threshold,
                "funding_rate": funding_rate,
                "ob_available": order_book_available,
                "signal_id": None,
            }

            # --- Module scores (needed for filter context) ---
            vp = compute_volume_profile(ohlcv.iloc[-96:])

            # Compute HTF bias once — reused by smc (both passes) and ctx
            _ohlcv_1h_or_15m = ohlcv_1h if not ohlcv_1h.empty else ohlcv
            from engine.smc import detect_htf_bias as _detect_htf_bias
            htf_bias = _detect_htf_bias(_ohlcv_1h_or_15m) if not _ohlcv_1h_or_15m.empty else "neutral"

            # Load SMC params from DB trading_params (priority: DB > module constants)
            _smc_atr_mult = None
            _smc_fvg_tol  = None
            _smc_swing    = None
            try:
                from db.connection import get_session_factory
                from config.config_service import get_active_trading_params
                _db = get_session_factory()()
                try:
                    _tp = get_active_trading_params(_db)
                finally:
                    _db.close()
                _smc_atr_mult = _tp.get("ob_atr_multiplier")
                _smc_fvg_tol  = _tp.get("fvg_touch_tolerance_pct")
                _smc_swing    = _tp.get("swing_lookback")
            except Exception as _e:
                logger.debug("SMC params from DB unavailable (%s) — using module constants", _e)

            # Pass 1: detect CHoCH to derive signal direction (uses pre-computed htf_bias)
            _smc_raw = compute_smc_score(
                ohlcv, _ohlcv_1h_or_15m, htf_bias=htf_bias,
                atr_multiplier=_smc_atr_mult or 1.0,
                fvg_tolerance=_smc_fvg_tol,
                swing_lookback=_smc_swing,
            )

            # Derive signal direction from CHoCH + HTF bias.
            if (
                _smc_raw.choch is not None
                and _smc_raw.choch.direction == "bearish"
                and _smc_raw.htf_bias == "bearish"
            ):
                signal_direction = "short"
            else:
                signal_direction = "long"

            # Pass 2: rescore with direction-aware OB filter
            smc = compute_smc_score(
                ohlcv, _ohlcv_1h_or_15m,
                signal_direction=signal_direction, htf_bias=htf_bias,
                atr_multiplier=_smc_atr_mult or 1.0,
                fvg_tolerance=_smc_fvg_tol,
                swing_lookback=_smc_swing,
            )

            # Compute nearest S/R distance from detected OB + FVG boundaries.
            # Used by compute_context_score to award +3 pts when price is away from S/R.
            _current_price = float(ohlcv.iloc[-1]["close"])
            _sr_levels = []
            for _ob in smc.order_blocks:
                _sr_levels.extend([_ob.high, _ob.low])
            if smc.fvg:
                _sr_levels.extend([smc.fvg.top, smc.fvg.bot])
            nearest_sr_distance_pct = (
                min(abs(_current_price - lvl) for lvl in _sr_levels) / _current_price
                if _sr_levels and _current_price > 0 else 0.0
            )

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
                    _audit["blocking_reason"] = self._map_filter_to_reason(f.name)
                    _audit["blocking_detail"] = result.block_reason
                    _audit["btc_guard_active"] = f.name == "btc_guard"
                    _audit["circuit_breaker_locked"] = f.name == "circuit_breaker"
                    self._emit_audit(_audit)
                    return

                combined_size_mult *= result.size_multiplier
                if result.warning:
                    filter_warnings.append(result.warning)
                filter_extras[f.name] = result.to_dict()

            # Store daily bias in Redis for frontend (TTL 4h)
            daily_bias = detect_daily_bias(ohlcv_daily) if not ohlcv_daily.empty else "NEUTRAL"
            r.set(RedisKeys.daily_bias(symbol), daily_bias, ex=14400)

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
                signal_direction,
                funding_rate,
                nearest_sr_distance_pct=nearest_sr_distance_pct,
                htf_bias=htf_bias,
            )
            bonus = compute_confluence_bonus(ohlcv, smc.order_blocks or smc.order_block, smc.fvg, vp.poc)

            # --- Load weight multipliers & thresholds from DB (migration 006) ---
            # Falls back to defaults (1.0 / 75 / 55) when columns are absent.
            _w_of    = self._tp_cache.get("weight_of", 1.0)
            _w_smc   = self._tp_cache.get("weight_smc", 1.0)
            _w_vsa   = self._tp_cache.get("weight_vsa", 1.0)
            _w_ctx   = self._tp_cache.get("weight_ctx", 1.0)
            _w_bonus = self._tp_cache.get("weight_bonus", 1.0)
            _alert_t = int(self._tp_cache.get("score_alert_threshold", 75))
            _watch_t = int(self._tp_cache.get("score_watch_threshold", 55))

            # Compute weight-adjusted max denominator
            _max_raw_adj = 35.0*_w_of + 30.0*_w_smc + 30.0*_w_vsa + 15.0*_w_ctx + 15.0*_w_bonus

            # --- Final score ---
            score = SignalScorer(
                alert_threshold=_alert_t,
                watch_threshold=_watch_t,
            ).score(ScoreInput(
                order_flow=of.score   * _w_of,
                smc=smc.score         * _w_smc,
                vsa=vsa.score         * _w_vsa,
                context=ctx.score     * _w_ctx,
                bonus=bonus           * _w_bonus,
                regime_multiplier=regime_state.score_multiplier,
                direction=signal_direction,
                regime=regime_state.regime,
                order_book_available=order_book_available,
                max_raw=_max_raw_adj,
            ))

            # Apply filter score adjustments (sum of all filter adjustments).
            # filter_extras values are plain dicts (from FilterResult.to_dict()),
            # so use .get() — NOT attribute access.
            total_score_adj = sum(
                r.get("score_adjustment", 0)
                for r in filter_extras.values()
                if isinstance(r, dict)
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

            # --- Compute ATR-based SL/TP (params from config or module defaults) ---
            sl_atr_mult, tp1_rr, tp2_rr, min_net_rr, fee_rate = self._get_sl_tp_params()
            close = float(ohlcv.iloc[-1]["close"])
            if atr_val > 0:
                stop_loss, tp1, tp2, gross_rr, net_rr = self._compute_sl_tp(
                    close, atr_val, signal_direction,
                    fee_rate=fee_rate,
                    sl_atr_mult=sl_atr_mult,
                    tp1_rr=tp1_rr,
                    tp2_rr=tp2_rr,
                )
            else:
                logger.warning(
                    "ATR=0 for %s %s — cannot compute ATR-based SL/TP, ALERT suppressed",
                    symbol, timeframe,
                )
                stop_loss = tp1 = tp2 = gross_rr = net_rr = 0.0

            # --- Persist to SQL Server ---
            signal_id = self._persist_signal(
                symbol, timeframe, ohlcv, score, smc, vsa, of, ctx, bonus,
                regime_state, funding_rate,
                stop_loss=stop_loss, tp1=tp1, tp2=tp2,
                signal_direction=signal_direction,
            )

            # --- Emit audit snapshot ---
            _audit["final_score"] = score.final_score
            _audit["score_breakdown"] = {
                "of": of.score, "smc": smc.score,
                "vsa": vsa.score, "ctx": ctx.score, "bonus": bonus,
            }
            _audit["signal_result"] = "SIGNAL" if score.classification == "ALERT" else "NO_SIGNAL"
            _audit["signal_id"] = signal_id
            _audit["entry_price_proposed"] = close
            _audit["sl_proposed"] = stop_loss
            _audit["tp1_proposed"] = tp1
            _audit["tp2_proposed"] = tp2
            self._emit_audit(_audit)

            # --- Publish ALERT (only when ATR is valid and R:R meets minimum) ---
            if score.classification == "ALERT":
                if atr_val == 0:
                    logger.warning(
                        "ALERT suppressed for %s %s: ATR=0 — no valid SL/TP",
                        symbol, timeframe,
                    )
                elif net_rr < min_net_rr:
                    logger.warning(
                        "ALERT suppressed for %s %s: net R:R %.2f < %.1f minimum",
                        symbol, timeframe, net_rr, min_net_rr,
                    )
                else:
                    self._publish_alert(
                        r, symbol, timeframe, ohlcv, score, smc, vsa, of, ctx, bonus,
                        regime_state, order_book_available,
                        combined_size_mult=combined_size_mult,
                        daily_bias=daily_bias,
                        filter_warnings=filter_warnings,
                        stop_loss=stop_loss, tp1=tp1, tp2=tp2,
                        gross_rr=gross_rr, net_rr=net_rr,
                        signal_direction=signal_direction,
                    )

        except Exception as exc:
            logger.error("Scoring error %s %s: %s", symbol, timeframe, exc, exc_info=True)

    def _get_sl_tp_params(self) -> tuple:
        """
        Return (sl_atr_mult, tp1_rr, tp2_rr, min_net_rr, fee_rate).

        Priority (DB > ConfigSystem > module constants):
        1. DB TradingParams — authoritative, updated via FE without restart
        2. ConfigSystem (config.yaml) — fallback when DB unavailable
        3. Module-level constants — last resort (test environments)
        """
        # Fee rate from ExchangeSettings (Group B) or ConfigSystem fallback
        fee_rate = DEFAULT_FEE_RATE
        if self._config is not None:
            try:
                fee_rate = self._config.get().exchange.fee_rate
            except Exception:
                pass

        # 1. Try DB TradingParams (primary — always reflects latest FE save)
        try:
            from db.connection import get_session_factory
            from config.config_service import get_active_trading_params
            db = get_session_factory()()
            try:
                tp = get_active_trading_params(db)
            finally:
                db.close()
            return (
                tp.get("atr_sl_multiplier", SL_ATR_MULT),
                tp.get("tp1_rr_ratio", TP1_RR),
                tp.get("tp2_rr_ratio", TP2_RR),
                tp.get("min_net_rr", MIN_NET_RR),
                fee_rate,
            )
        except Exception as exc:
            logger.debug("_get_sl_tp_params: DB unavailable (%s), falling back", exc)

        # 2. ConfigSystem (config.yaml)
        if self._config is not None:
            try:
                cfg = self._config.get()
                return (
                    cfg.risk.atr_sl_multiplier,
                    cfg.risk.tp1_rr,
                    cfg.risk.tp2_rr,
                    cfg.risk.min_net_rr,
                    fee_rate,
                )
            except Exception:
                pass

        # 3. Module constants
        return SL_ATR_MULT, TP1_RR, TP2_RR, MIN_NET_RR, fee_rate

    def _safe_last(self, series) -> float:
        """Return last non-NaN value from a pandas Series, or 0.0."""
        valid = series.dropna()
        return float(valid.iloc[-1]) if not valid.empty else 0.0

    def _compute_sl_tp(
        self,
        entry: float,
        atr: float,
        direction: str,
        fee_rate: float = DEFAULT_FEE_RATE,
        sl_atr_mult: float = SL_ATR_MULT,
        tp1_rr: float = TP1_RR,
        tp2_rr: float = TP2_RR,
    ) -> tuple:
        """
        Compute ATR-based stop loss, take profit levels, and net R:R.

        SL  = entry ± sl_atr_mult × ATR(14)
        TP1 = entry ± tp1_rr × SL_distance
        TP2 = entry ± tp2_rr × SL_distance

        Net R:R accounts for round-trip fee cost (entry + exit).

        Returns:
            (stop_loss, tp1, tp2, gross_rr, net_rr)
        """
        sl_dist = atr * sl_atr_mult
        tp1_dist = sl_dist * tp1_rr
        tp2_dist = sl_dist * tp2_rr

        if direction == "long":
            stop_loss = entry - sl_dist
            tp1 = entry + tp1_dist
            tp2 = entry + tp2_dist
        else:  # short
            stop_loss = entry + sl_dist
            tp1 = entry - tp1_dist
            tp2 = entry - tp2_dist

        # Net R:R: deduct round-trip fee from both reward and risk
        sl_pct = sl_dist / entry
        tp1_pct = tp1_dist / entry
        fee_total = fee_rate * 2  # entry + exit
        net_rr = round(
            (tp1_pct - fee_total) / (sl_pct + fee_total), 2
        ) if (sl_pct + fee_total) > 0 else 0.0
        gross_rr = round(tp1_rr, 2)

        return round(stop_loss, 8), round(tp1, 8), round(tp2, 8), gross_rr, net_rr

    def _persist_signal(self, symbol, timeframe, ohlcv, score, smc, vsa, of, ctx, bonus, regime_state, funding_rate, stop_loss, tp1, tp2, signal_direction="long") -> Optional[str]:
        """Persist signal to SQL Server. Returns signal log_id (UUID str) or None on failure."""
        try:
            from db.connection import get_session_factory
            from api.signal_log_writer import write_signal_log
            from strategies.signal import Signal, ScoreBreakdown

            db = get_session_factory()()
            signal_obj = Signal(
                strategy_name="scoring_engine",
                asset=symbol, timeframe=timeframe, direction=signal_direction,
                candle_index=len(ohlcv) - 1,
                candle_timestamp=datetime.now(timezone.utc),
                entry_price=float(ohlcv.iloc[-1]["close"]),
                stop_loss=stop_loss,
                take_profit_1=tp1,
                take_profit_2=tp2,
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
            log_id = write_signal_log(signal_obj, db)
            db.close()
            return log_id
        except Exception as exc:
            logger.warning("Failed to persist signal_log: %s", exc)
            return None

    def _publish_alert(self, r, symbol, timeframe, ohlcv, score, smc, vsa, of, ctx, bonus, regime_state, order_book_available=True, combined_size_mult=1.0, daily_bias="NEUTRAL", filter_warnings=None, stop_loss=0.0, tp1=0.0, tp2=0.0, gross_rr=0.0, net_rr=0.0, signal_direction="long"):
        """Publish ALERT signal to Redis alerts:channel."""
        close = float(ohlcv.iloc[-1]["close"])
        r.publish(RedisKeys.Channels.ALERTS, json.dumps({
            "signal_id": f"{symbol}_{timeframe}_{int(time.time())}",
            "asset": symbol, "timeframe": timeframe, "direction": signal_direction,
            "final_score": score.final_score, "classification": "ALERT",
            "regime": regime_state.regime,
            "entry_price": close,
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "gross_rr": gross_rr, "net_rr": net_rr,
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

    def _emit_audit(self, audit_data: dict) -> None:
        if self._audit_client is not None:
            self._audit_client.emit("signal_snapshot", audit_data)

    @staticmethod
    def _map_filter_to_reason(filter_name: str) -> str:
        return {
            "mtf_bias": "MTF_BLOCK",
            "btc_guard": "BTC_GUARD",
            "circuit_breaker": "CB_LOCKED",
            "daily_bias": "REGIME",
        }.get(filter_name, "LOW_SCORE")
