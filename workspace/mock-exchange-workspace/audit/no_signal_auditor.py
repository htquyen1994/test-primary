"""
NoSignalAuditor — computes counterfactual for NO_SIGNAL snapshots.
Runs after T16 is filled in signal_audit_log.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from db.models import NoSignalAuditLog, SignalAuditLog

logger = logging.getLogger(__name__)

# Threshold that was not met to generate a signal
SCORE_THRESHOLD = 75.0


class NoSignalAuditor:
    """
    Processes NO_SIGNAL records from signal_audit_log after T16 is complete.
    Creates no_signal_audit_log entries with counterfactual analysis.
    """

    def __init__(self, db_factory) -> None:
        self._db_factory = db_factory

    async def process_completed_no_signals(self) -> None:
        """
        Scan signal_audit_log for NO_SIGNAL records that have COMPLETE T16
        but don't have a no_signal_audit_log entry yet.
        Called periodically or after T16 completion.
        """
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._process_all_pending)
        except Exception as exc:
            logger.error("NoSignalAuditor.process_completed_no_signals error: %s", exc)

    def _process_all_pending(self) -> None:
        db: Session = self._db_factory()
        try:
            # Find NO_SIGNAL records with complete T16 but no no_signal_audit_log
            existing_ids_q = db.query(NoSignalAuditLog.signal_audit_id)
            existing_ids = {row[0] for row in existing_ids_q.all()}

            records = (
                db.query(SignalAuditLog)
                .filter(
                    SignalAuditLog.signal_result == "NO_SIGNAL",
                    SignalAuditLog.audit_status == "COMPLETE",
                    SignalAuditLog.would_have_hit_tp1.isnot(None),
                )
                .all()
            )

            count = 0
            for record in records:
                if record.id in existing_ids:
                    continue
                self._create_no_signal_entry(db, record)
                count += 1

            if count:
                logger.info("NoSignalAuditor: processed %d new NO_SIGNAL records", count)

        except Exception as exc:
            db.rollback()
            logger.error("_process_all_pending failed: %s", exc)
        finally:
            db.close()

    def _create_no_signal_entry(self, db: Session, sal: SignalAuditLog) -> None:
        """Create no_signal_audit_log entry from a completed SignalAuditLog."""
        try:
            score = sal.final_score or 0.0
            score_gap = SCORE_THRESHOLD - score

            # Counterfactual: use would_have_hit_tp1 from signal_audit_log
            would_have_hit_tp1 = bool(sal.would_have_hit_tp1)
            would_have_hit_sl = bool(sal.would_have_hit_sl)

            # Hypothetical PnL (simplified — no leverage/fees for NO_SIGNAL)
            hypothetical_pnl_pct = None
            would_have_been_profitable = None

            if sal.entry_price_proposed and sal.price_at_T16:
                hypothetical_pnl_pct = (
                    (sal.price_at_T16 - sal.entry_price_proposed)
                    / sal.entry_price_proposed * 100
                )
                would_have_been_profitable = int(hypothetical_pnl_pct > 0)

            if sal.entry_price_proposed and sal.tp1_proposed and would_have_hit_tp1:
                hypothetical_pnl_pct = (
                    (sal.tp1_proposed - sal.entry_price_proposed)
                    / sal.entry_price_proposed * 100
                )
                would_have_been_profitable = 1

            missed_opportunity = int(would_have_hit_tp1)

            entry = NoSignalAuditLog(
                signal_audit_id=sal.id,
                score_at_decision=score,
                score_gap=score_gap,
                blocking_reason=sal.blocking_reason or "LOW_SCORE",
                blocking_detail=sal.blocking_detail,
                hypothetical_entry_price=sal.entry_price_proposed,
                hypothetical_sl=sal.sl_proposed,
                hypothetical_tp1=sal.tp1_proposed,
                would_have_been_profitable=would_have_been_profitable,
                hypothetical_pnl_pct=hypothetical_pnl_pct,
                missed_opportunity=missed_opportunity,
                audit_status="COMPLETE",
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            db.add(entry)
            db.commit()
            logger.debug(
                "NoSignalAuditLog created: sal_id=%s missed=%s", sal.id, missed_opportunity
            )
        except Exception as exc:
            db.rollback()
            logger.error("_create_no_signal_entry failed for sal.id=%s: %s", sal.id, exc)
            raise
