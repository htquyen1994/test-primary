"""
SignalAuditor — processes signal_snapshots and schedules T1/T4/T16 price checks.
Uses APScheduler for deferred T* jobs and handles startup backfill.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from db.models import SignalAuditLog

logger = logging.getLogger(__name__)

# T* offsets
T1_MINUTES = 15
T4_MINUTES = 60
T16_MINUTES = 240


class SignalAuditor:
    """
    Processes audit:pending_snapshots events of type 'signal_snapshot'.
    Schedules APScheduler jobs to fetch forward prices at T1, T4, T16.
    On startup, backfills any pending/partial records.
    """

    def __init__(
        self,
        db_factory,
        exchange_id: str = "binance",
        ws_manager=None,
    ) -> None:
        self._db_factory = db_factory
        self._exchange_id = exchange_id
        self._ws_manager = ws_manager
        self._scheduler = AsyncIOScheduler(timezone="UTC")

    def start_scheduler(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("SignalAuditor scheduler started")

    def stop_scheduler(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    # ------------------------------------------------------------------
    # Process incoming snapshot
    # ------------------------------------------------------------------

    async def process(self, data: dict) -> None:
        """Called by AuditConsumer for each signal_snapshot event."""
        loop = asyncio.get_running_loop()
        try:
            audit_id = await loop.run_in_executor(None, lambda: self._insert_record(data))
            if audit_id is None:
                return
            # Schedule T* jobs
            candle_close_ts = data.get("timestamp_candle_close")
            symbol = data.get("symbol")
            timeframe = data.get("timeframe", "15m")
            entry_price = data.get("entry_price_proposed")
            sl = data.get("sl_proposed")
            tp1 = data.get("tp1_proposed")
            tp2 = data.get("tp2_proposed")
            direction = data.get("direction", "long")

            if candle_close_ts:
                self._schedule_t_jobs(
                    audit_id=audit_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    candle_close_iso=candle_close_ts,
                    direction=direction,
                    entry_price=entry_price,
                    sl=sl,
                    tp1=tp1,
                    tp2=tp2,
                )

            # Broadcast to WS audit feed
            if self._ws_manager:
                try:
                    await self._ws_manager.broadcast_audit(
                        json.dumps({"event": "signal_recorded", "audit_id": audit_id, **data})
                    )
                except Exception:
                    pass

        except Exception as exc:
            logger.error("SignalAuditor.process error: %s", exc)

    def _insert_record(self, data: dict) -> Optional[int]:
        db: Session = self._db_factory()
        try:
            record = SignalAuditLog(
                signal_id=data.get("signal_id"),
                symbol=data.get("symbol", ""),
                timeframe=data.get("timeframe", "15m"),
                timestamp_candle_close=data.get(
                    "timestamp_candle_close",
                    datetime.now(timezone.utc).isoformat()
                ),
                signal_result=data.get("signal_result", "NO_SIGNAL"),
                final_score=data.get("final_score", 0.0),
                score_breakdown=json.dumps(data.get("score_breakdown")) if data.get("score_breakdown") else None,
                regime=data.get("regime"),
                regime_multiplier=data.get("regime_multiplier"),
                mtf_scenario=data.get("mtf_scenario"),
                mtf_4h_bias=data.get("mtf_4h_bias"),
                daily_bias=data.get("daily_bias"),
                btc_guard_active=int(data.get("btc_guard_active", False)),
                circuit_breaker_locked=int(data.get("circuit_breaker_locked", False)),
                blocking_reason=data.get("blocking_reason"),
                blocking_detail=data.get("blocking_detail"),
                entry_price_proposed=data.get("entry_price_proposed"),
                sl_proposed=data.get("sl_proposed"),
                tp1_proposed=data.get("tp1_proposed"),
                tp2_proposed=data.get("tp2_proposed"),
                atr_value=data.get("atr_value"),
                adx_value=data.get("adx_value"),
                delta_value=data.get("delta_value"),
                delta_threshold=data.get("delta_threshold"),
                funding_rate=data.get("funding_rate"),
                ob_available=int(data.get("ob_available", False)),
                poc_value=data.get("poc_value"),
                htf_bias_1h=data.get("htf_bias_1h"),
                audit_status="PENDING",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            logger.debug("SignalAuditLog inserted: id=%s symbol=%s", record.id, record.symbol)
            return record.id
        except Exception as exc:
            db.rollback()
            logger.error("Failed to insert SignalAuditLog: %s", exc)
            return None
        finally:
            db.close()

    # ------------------------------------------------------------------
    # T* scheduling
    # ------------------------------------------------------------------

    def _schedule_t_jobs(
        self,
        audit_id: int,
        symbol: str,
        timeframe: str,
        candle_close_iso: str,
        direction: str,
        entry_price: Optional[float],
        sl: Optional[float],
        tp1: Optional[float],
        tp2: Optional[float],
    ) -> None:
        try:
            base_ts = datetime.fromisoformat(candle_close_iso)
            if base_ts.tzinfo is None:
                base_ts = base_ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError) as exc:
            logger.warning("Cannot parse candle_close timestamp: %s", exc)
            return

        now = datetime.now(timezone.utc)
        t1_run_at = base_ts + timedelta(minutes=T1_MINUTES)
        t4_run_at = base_ts + timedelta(minutes=T4_MINUTES)
        t16_run_at = base_ts + timedelta(minutes=T16_MINUTES)

        job_kwargs = dict(
            audit_id=audit_id,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            entry_price=entry_price,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
        )

        # Schedule T1
        if t1_run_at > now:
            self._scheduler.add_job(
                self._fetch_t1,
                trigger="date",
                run_date=t1_run_at,
                kwargs={**job_kwargs, "target_ts": t1_run_at},
                id=f"t1_{audit_id}",
                replace_existing=True,
                misfire_grace_time=300,
            )
        else:
            # Already past — run immediately
            asyncio.create_task(self._fetch_t1(
                target_ts=t1_run_at, **job_kwargs
            ))

        # Schedule T4
        if t4_run_at > now:
            self._scheduler.add_job(
                self._fetch_t4,
                trigger="date",
                run_date=t4_run_at,
                kwargs={**job_kwargs, "target_ts": t4_run_at},
                id=f"t4_{audit_id}",
                replace_existing=True,
                misfire_grace_time=300,
            )
        else:
            asyncio.create_task(self._fetch_t4(
                target_ts=t4_run_at, **job_kwargs
            ))

        # Schedule T16
        if t16_run_at > now:
            self._scheduler.add_job(
                self._fetch_t16,
                trigger="date",
                run_date=t16_run_at,
                kwargs={**job_kwargs, "target_ts": t16_run_at},
                id=f"t16_{audit_id}",
                replace_existing=True,
                misfire_grace_time=300,
            )
        else:
            asyncio.create_task(self._fetch_t16(
                target_ts=t16_run_at, **job_kwargs
            ))

    # ------------------------------------------------------------------
    # T* fetch implementations
    # ------------------------------------------------------------------

    async def _fetch_t1(
        self,
        audit_id: int,
        symbol: str,
        timeframe: str,
        target_ts: datetime,
        direction: str,
        entry_price: Optional[float],
        sl: Optional[float],
        tp1: Optional[float],
        tp2: Optional[float],
    ) -> None:
        price = await self._fetch_price_at(symbol, timeframe, target_ts)
        if price is None:
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._update_t1(audit_id, price))

    async def _fetch_t4(
        self,
        audit_id: int,
        symbol: str,
        timeframe: str,
        target_ts: datetime,
        direction: str,
        entry_price: Optional[float],
        sl: Optional[float],
        tp1: Optional[float],
        tp2: Optional[float],
    ) -> None:
        price = await self._fetch_price_at(symbol, timeframe, target_ts)
        if price is None:
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._update_t4(audit_id, price))

    async def _fetch_t16(
        self,
        audit_id: int,
        symbol: str,
        timeframe: str,
        target_ts: datetime,
        direction: str,
        entry_price: Optional[float],
        sl: Optional[float],
        tp1: Optional[float],
        tp2: Optional[float],
    ) -> None:
        # Fetch all candles from signal time to T16 for MFE/MAE
        price = await self._fetch_price_at(symbol, timeframe, target_ts)
        candle_range = await self._fetch_candle_range(symbol, timeframe, target_ts)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._update_t16(
                audit_id, price, candle_range, direction, entry_price, sl, tp1, tp2
            )
        )

    async def _fetch_price_at(
        self, symbol: str, timeframe: str, target_ts: datetime
    ) -> Optional[float]:
        """Fetch close price at the candle containing target_ts."""
        try:
            from trading_core.exchange.client import get_exchange_client
            client = get_exchange_client(self._exchange_id)
            # since: milliseconds
            since_ms = int(target_ts.timestamp() * 1000)
            loop = asyncio.get_running_loop()
            candles = await loop.run_in_executor(
                None,
                lambda: client.fetch_ohlcv(symbol, timeframe, limit=3, since=since_ms),
            )
            if candles:
                return float(candles[0][4])  # close
            return None
        except Exception as exc:
            logger.warning("_fetch_price_at failed for %s @%s: %s", symbol, target_ts, exc)
            return None

    async def _fetch_candle_range(
        self, symbol: str, timeframe: str, t16_ts: datetime
    ) -> list:
        """Fetch ~20 candles ending at T16 for MFE/MAE computation."""
        try:
            from trading_core.exchange.client import get_exchange_client
            client = get_exchange_client(self._exchange_id)
            since_ms = int((t16_ts - timedelta(minutes=T16_MINUTES)).timestamp() * 1000)
            loop = asyncio.get_running_loop()
            candles = await loop.run_in_executor(
                None,
                lambda: client.fetch_ohlcv(symbol, timeframe, limit=20, since=since_ms),
            )
            return candles or []
        except Exception as exc:
            logger.warning("_fetch_candle_range failed for %s: %s", symbol, exc)
            return []

    # ------------------------------------------------------------------
    # DB update helpers
    # ------------------------------------------------------------------

    def _update_t1(self, audit_id: int, price: float) -> None:
        db: Session = self._db_factory()
        try:
            record = db.query(SignalAuditLog).filter(SignalAuditLog.id == audit_id).first()
            if record:
                record.price_at_T1 = price
                if record.audit_status == "PENDING":
                    record.audit_status = "PARTIAL"
                db.commit()
                logger.debug("T1 updated: audit_id=%s price=%.4f", audit_id, price)
        except Exception as exc:
            db.rollback()
            logger.error("_update_t1 failed: %s", exc)
        finally:
            db.close()

    def _update_t4(self, audit_id: int, price: float) -> None:
        db: Session = self._db_factory()
        try:
            record = db.query(SignalAuditLog).filter(SignalAuditLog.id == audit_id).first()
            if record:
                record.price_at_T4 = price
                record.audit_status = "PARTIAL"
                db.commit()
                logger.debug("T4 updated: audit_id=%s price=%.4f", audit_id, price)
        except Exception as exc:
            db.rollback()
            logger.error("_update_t4 failed: %s", exc)
        finally:
            db.close()

    def _update_t16(
        self,
        audit_id: int,
        price: Optional[float],
        candles: list,
        direction: str,
        entry_price: Optional[float],
        sl: Optional[float],
        tp1: Optional[float],
        tp2: Optional[float],
    ) -> None:
        db: Session = self._db_factory()
        try:
            record = db.query(SignalAuditLog).filter(SignalAuditLog.id == audit_id).first()
            if record is None:
                return

            if price:
                record.price_at_T16 = price

            # Compute MFE/MAE from candle range
            if candles and entry_price:
                highs = [c[2] for c in candles]  # index 2 = high
                lows = [c[3] for c in candles]   # index 3 = low

                if direction == "long":
                    mfe = max(highs) - entry_price if highs else None
                    mae = entry_price - min(lows) if lows else None
                else:
                    mfe = entry_price - min(lows) if lows else None
                    mae = max(highs) - entry_price if highs else None

                record.max_favorable_excursion = mfe
                record.max_adverse_excursion = mae

                # Would have hit SL/TP
                if sl:
                    if direction == "long":
                        record.would_have_hit_sl = int(min(lows) <= sl)
                    else:
                        record.would_have_hit_sl = int(max(highs) >= sl)
                if tp1:
                    if direction == "long":
                        record.would_have_hit_tp1 = int(max(highs) >= tp1)
                    else:
                        record.would_have_hit_tp1 = int(min(lows) <= tp1)
                if tp2:
                    if direction == "long":
                        record.would_have_hit_tp2 = int(max(highs) >= tp2)
                    else:
                        record.would_have_hit_tp2 = int(min(lows) <= tp2)

            record.audit_status = "COMPLETE"
            record.audit_completed_at = datetime.now(timezone.utc).isoformat()
            db.commit()
            logger.info("T16 completed: audit_id=%s", audit_id)
        except Exception as exc:
            db.rollback()
            logger.error("_update_t16 failed: %s", exc)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Startup backfill
    # ------------------------------------------------------------------

    async def backfill_pending(self) -> None:
        """On startup: backfill all pending/partial T* windows."""
        logger.info("SignalAuditor: starting backfill of pending records...")
        loop = asyncio.get_running_loop()
        records = await loop.run_in_executor(None, self._get_pending_records)

        if not records:
            logger.info("SignalAuditor: no pending records to backfill")
            return

        logger.info("SignalAuditor: backfilling %d records", len(records))
        tasks = []
        for record in records:
            tasks.append(asyncio.create_task(self._backfill_record(record)))

        # Run all backfills concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        errors = sum(1 for r in results if isinstance(r, Exception))
        logger.info(
            "SignalAuditor: backfill complete. %d processed, %d errors",
            len(records) - errors, errors
        )

    def _get_pending_records(self) -> list:
        db: Session = self._db_factory()
        try:
            return (
                db.query(SignalAuditLog)
                .filter(SignalAuditLog.audit_status.in_(["PENDING", "PARTIAL"]))
                .all()
            )
        finally:
            db.close()

    async def _backfill_record(self, record: SignalAuditLog) -> None:
        try:
            ts_str = record.timestamp_candle_close
            base_ts = datetime.fromisoformat(ts_str)
            if base_ts.tzinfo is None:
                base_ts = base_ts.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            elapsed = (now - base_ts).total_seconds() / 60  # minutes

            symbol = record.symbol
            timeframe = record.timeframe
            direction = "long"  # default; would be stored in future
            entry_price = record.entry_price_proposed
            sl = record.sl_proposed
            tp1 = record.tp1_proposed
            tp2 = record.tp2_proposed
            audit_id = record.id

            t1_ts = base_ts + timedelta(minutes=T1_MINUTES)
            t4_ts = base_ts + timedelta(minutes=T4_MINUTES)
            t16_ts = base_ts + timedelta(minutes=T16_MINUTES)

            # Backfill T1
            if elapsed >= T1_MINUTES and record.price_at_T1 is None:
                price = await self._fetch_price_at(symbol, timeframe, t1_ts)
                if price:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, lambda: self._update_t1(audit_id, price))

            # Backfill T4
            if elapsed >= T4_MINUTES and record.price_at_T4 is None:
                price = await self._fetch_price_at(symbol, timeframe, t4_ts)
                if price:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, lambda: self._update_t4(audit_id, price))

            # Backfill T16
            if elapsed >= T16_MINUTES and record.price_at_T16 is None:
                price = await self._fetch_price_at(symbol, timeframe, t16_ts)
                candles = await self._fetch_candle_range(symbol, timeframe, t16_ts)
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self._update_t16(
                        audit_id, price, candles, direction, entry_price, sl, tp1, tp2
                    )
                )

            # Schedule future jobs for windows not yet elapsed
            self._schedule_t_jobs(
                audit_id=audit_id,
                symbol=symbol,
                timeframe=timeframe,
                candle_close_iso=ts_str,
                direction=direction,
                entry_price=entry_price,
                sl=sl,
                tp1=tp1,
                tp2=tp2,
            )

        except Exception as exc:
            logger.error("Backfill error for audit_id=%s: %s", record.id, exc)
            raise
