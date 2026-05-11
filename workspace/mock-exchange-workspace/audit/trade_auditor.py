"""
TradeAuditor — records trade open/close events and computes auto-verdict.
Triggered by AuditConsumer dispatch.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from db.models import MockPosition, SignalAuditLog, TradeAuditLog

logger = logging.getLogger(__name__)


class TradeAuditor:
    """
    Handles:
    - trade_opened events: INSERT pending TradeAuditLog
    - trade_closed events: UPDATE with outcome, PnL, auto-verdict
    """

    def __init__(self, db_factory, redis_client=None, ws_manager=None) -> None:
        self._db_factory = db_factory
        self._redis = redis_client
        self._ws_manager = ws_manager

    # ------------------------------------------------------------------
    # Event handlers (called by AuditConsumer)
    # ------------------------------------------------------------------

    async def on_trade_opened(self, data: dict) -> None:
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, lambda: self._handle_trade_opened(data))
        except Exception as exc:
            logger.error("TradeAuditor.on_trade_opened error: %s", exc)

    async def on_trade_closed(self, data: dict) -> None:
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, lambda: self._handle_trade_closed(data))
        except Exception as exc:
            logger.error("TradeAuditor.on_trade_closed error: %s", exc)

        # Broadcast to WS audit feed
        if self._ws_manager:
            try:
                await self._ws_manager.broadcast_audit(
                    json.dumps({"event": "trade_closed", **data})
                )
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Sync DB handlers
    # ------------------------------------------------------------------

    def _handle_trade_opened(self, data: dict) -> None:
        db: Session = self._db_factory()
        try:
            position_id = data.get("position_id")
            signal_id = data.get("signal_id")

            # Find the corresponding signal_audit_log
            signal_audit_id = None
            if signal_id:
                sal = (
                    db.query(SignalAuditLog)
                    .filter(SignalAuditLog.signal_id == str(signal_id))
                    .order_by(SignalAuditLog.id.desc())
                    .first()
                )
                if sal:
                    signal_audit_id = sal.id

            # Find the position for proposed values
            pos = None
            if position_id:
                pos = db.query(MockPosition).filter(MockPosition.id == position_id).first()

            record = TradeAuditLog(
                trade_id=position_id or 0,
                signal_audit_id=signal_audit_id,
                entry_price_proposed=data.get("entry_price_proposed") or (pos.entry_price if pos else 0.0),
                entry_price_actual=pos.entry_price if pos else data.get("entry_price", 0.0),
                sl_proposed=data.get("sl_proposed") or (pos.stop_loss if pos else 0.0),
                sl_actual=pos.stop_loss if pos else data.get("sl", 0.0),
                tp1_proposed=data.get("tp1_proposed") or (pos.take_profit_1 if pos else 0.0),
                tp1_actual=pos.take_profit_1 if pos else data.get("tp1", 0.0),
                outcome="MANUAL_CLOSE",  # placeholder, updated on close
                audit_status="PENDING",
            )
            db.add(record)
            db.commit()
            logger.debug(
                "TradeAuditLog created for position_id=%s", position_id
            )
        except Exception as exc:
            db.rollback()
            logger.error("_handle_trade_opened failed: %s", exc)
        finally:
            db.close()

    def _handle_trade_closed(self, data: dict) -> None:
        db: Session = self._db_factory()
        try:
            position_id = data.get("position_id")
            exit_reason = data.get("exit_reason", "MANUAL_CLOSE")
            exit_price = data.get("exit_price")
            net_pnl = data.get("net_pnl", 0.0)
            gross_pnl = data.get("gross_pnl", 0.0)
            pnl_pct = data.get("pnl_pct", 0.0)
            hold_hours = data.get("hold_hours", 0.0)
            closed_at = data.get("closed_at", datetime.now(timezone.utc).isoformat())

            # Find existing trade audit log
            record = (
                db.query(TradeAuditLog)
                .filter(TradeAuditLog.trade_id == position_id)
                .order_by(TradeAuditLog.id.desc())
                .first()
            )

            if record is None:
                # Create one if not found (e.g. service restart scenario)
                pos = db.query(MockPosition).filter(MockPosition.id == position_id).first()
                signal_audit_id = None
                if pos and pos.signal_id:
                    sal = (
                        db.query(SignalAuditLog)
                        .filter(SignalAuditLog.signal_id == pos.signal_id)
                        .order_by(SignalAuditLog.id.desc())
                        .first()
                    )
                    if sal:
                        signal_audit_id = sal.id

                record = TradeAuditLog(
                    trade_id=position_id or 0,
                    signal_audit_id=signal_audit_id,
                    entry_price_proposed=pos.entry_price if pos else 0.0,
                    entry_price_actual=pos.entry_price if pos else 0.0,
                    sl_proposed=pos.stop_loss if pos else 0.0,
                    sl_actual=pos.stop_loss if pos else 0.0,
                    tp1_proposed=pos.take_profit_1 if pos else 0.0,
                    tp1_actual=pos.take_profit_1 if pos else 0.0,
                    outcome=exit_reason,
                    audit_status="PENDING",
                )
                db.add(record)
                db.flush()

            # Update outcome
            record.outcome = exit_reason
            record.exit_price = exit_price
            record.exit_timestamp = closed_at
            record.hold_duration_minutes = hold_hours * 60
            record.gross_pnl = gross_pnl
            record.net_pnl = net_pnl
            record.pnl_pct = pnl_pct
            record.audit_status = "ANALYZED"
            record.analyzed_at = datetime.now(timezone.utc).isoformat()

            # Auto-verdict
            verdict, sl_reason = self._compute_verdict(db, data, record)
            record.signal_quality_verdict = verdict
            record.sl_hit_reason = sl_reason

            db.commit()
            logger.info(
                "TradeAuditLog updated: position_id=%s outcome=%s verdict=%s",
                position_id, exit_reason, verdict,
            )

            # Update signal_audit_log status
            if record.signal_audit_id:
                sal = db.query(SignalAuditLog).filter(
                    SignalAuditLog.id == record.signal_audit_id
                ).first()
                if sal and sal.audit_status == "PENDING":
                    sal.audit_status = "PARTIAL"
                    db.commit()

        except Exception as exc:
            db.rollback()
            logger.error("_handle_trade_closed failed: %s", exc)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Auto-verdict
    # ------------------------------------------------------------------

    def _compute_verdict(
        self,
        db: Session,
        data: dict,
        record: TradeAuditLog,
    ) -> tuple[Optional[str], Optional[str]]:
        outcome = data.get("exit_reason", "")
        direction = data.get("direction", "long")
        entry_price = data.get("entry_price") or record.entry_price_actual

        if outcome in ("TP1_HIT", "TP2_HIT"):
            return "TRUE_POSITIVE", None

        if outcome == "SL_HIT":
            sl_reason = self._determine_sl_reason(db, data, record)

            # Premature SL: price recovered after SL hit
            # Check via signal_audit_log.price_at_T4
            if record.signal_audit_id:
                sal = db.query(SignalAuditLog).filter(
                    SignalAuditLog.id == record.signal_audit_id
                ).first()
                if sal and sal.price_at_T4 is not None:
                    price_at_t4 = sal.price_at_T4
                    if direction == "long" and price_at_t4 > entry_price:
                        return "PREMATURE_SL", sl_reason
                    elif direction == "short" and price_at_t4 < entry_price:
                        return "PREMATURE_SL", sl_reason

            return "FALSE_POSITIVE", sl_reason

        return None, None

    def _determine_sl_reason(
        self,
        db: Session,
        data: dict,
        record: TradeAuditLog,
    ) -> str:
        symbol = data.get("symbol", "")
        closed_at = data.get("closed_at", "")

        # BTC_SPIKE: check if BTC moved >2% in same 15m candle
        if symbol != "BTC/USDT" and closed_at:
            try:
                from db.models import PriceSnapshot
                btc_snap = (
                    db.query(PriceSnapshot)
                    .filter(
                        PriceSnapshot.symbol == "BTC/USDT",
                        PriceSnapshot.timeframe == "15m",
                        PriceSnapshot.timestamp <= closed_at,
                    )
                    .order_by(PriceSnapshot.timestamp.desc())
                    .first()
                )
                if btc_snap and btc_snap.open > 0:
                    btc_move_pct = abs(btc_snap.close - btc_snap.open) / btc_snap.open * 100
                    if btc_move_pct > 2.0:
                        return "BTC_SPIKE"
            except Exception as exc:
                logger.debug("BTC spike check failed: %s", exc)

        # NOISE: price_at_T1 recovered past SL level
        if record.signal_audit_id:
            try:
                sal = db.query(SignalAuditLog).filter(
                    SignalAuditLog.id == record.signal_audit_id
                ).first()
                if sal and sal.price_at_T1 is not None:
                    direction = data.get("direction", "long")
                    sl_level = record.sl_actual
                    if direction == "long" and sal.price_at_T1 > sl_level:
                        return "NOISE"
                    elif direction == "short" and sal.price_at_T1 < sl_level:
                        return "NOISE"
            except Exception as exc:
                logger.debug("NOISE check failed: %s", exc)

        return "TREND_REVERSAL"
