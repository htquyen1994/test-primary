"""
Audit API routes — paginated queries for signal/trade/no-signal logs.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.schemas import (
    NoSignalAuditListItem, PaginatedNoSignalAudit,
    PaginatedSignalAudit, PaginatedTradeAudit,
    SignalAuditDetail, SignalAuditListItem,
    TradeAuditDetail, TradeAuditListItem,
)
from db.database import get_db
from db.models import NoSignalAuditLog, SignalAuditLog, TradeAuditLog
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audit", tags=["audit"])


# ---------------------------------------------------------------------------
# Signal audit
# ---------------------------------------------------------------------------

@router.get("/signals", response_model=PaginatedSignalAudit)
def list_signals(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    symbol: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
    regime: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    from_ts: Optional[str] = Query(None, alias="from"),
    to_ts: Optional[str] = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    q = db.query(SignalAuditLog)
    if symbol:
        q = q.filter(SignalAuditLog.symbol == symbol)
    if result:
        q = q.filter(SignalAuditLog.signal_result == result)
    if regime:
        q = q.filter(SignalAuditLog.regime == regime)
    if status:
        q = q.filter(SignalAuditLog.audit_status == status)
    if from_ts:
        q = q.filter(SignalAuditLog.timestamp_candle_close >= from_ts)
    if to_ts:
        q = q.filter(SignalAuditLog.timestamp_candle_close <= to_ts)

    total = q.count()
    records = (
        q.order_by(SignalAuditLog.timestamp_candle_close.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    items = [
        SignalAuditListItem(
            id=r.id,
            signal_id=r.signal_id,
            symbol=r.symbol,
            timeframe=r.timeframe,
            timestamp_candle_close=r.timestamp_candle_close,
            signal_result=r.signal_result,
            final_score=r.final_score,
            regime=r.regime,
            mtf_scenario=r.mtf_scenario,
            blocking_reason=r.blocking_reason,
            audit_status=r.audit_status,
            created_at=r.created_at,
        )
        for r in records
    ]
    return PaginatedSignalAudit(total=total, page=page, limit=limit, items=items)


@router.get("/signals/{signal_id}", response_model=SignalAuditDetail)
def get_signal(signal_id: int, db: Session = Depends(get_db)):
    record = db.query(SignalAuditLog).filter(SignalAuditLog.id == signal_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Signal audit not found")
    return SignalAuditDetail(
        id=record.id,
        signal_id=record.signal_id,
        symbol=record.symbol,
        timeframe=record.timeframe,
        timestamp_candle_close=record.timestamp_candle_close,
        signal_result=record.signal_result,
        final_score=record.final_score,
        regime=record.regime,
        mtf_scenario=record.mtf_scenario,
        blocking_reason=record.blocking_reason,
        audit_status=record.audit_status,
        created_at=record.created_at,
        score_breakdown=record.score_breakdown,
        regime_multiplier=record.regime_multiplier,
        mtf_4h_bias=record.mtf_4h_bias,
        daily_bias=record.daily_bias,
        btc_guard_active=record.btc_guard_active,
        circuit_breaker_locked=record.circuit_breaker_locked,
        blocking_detail=record.blocking_detail,
        entry_price_proposed=record.entry_price_proposed,
        sl_proposed=record.sl_proposed,
        tp1_proposed=record.tp1_proposed,
        tp2_proposed=record.tp2_proposed,
        atr_value=record.atr_value,
        adx_value=record.adx_value,
        delta_value=record.delta_value,
        delta_threshold=record.delta_threshold,
        funding_rate=record.funding_rate,
        ob_available=record.ob_available,
        poc_value=record.poc_value,
        htf_bias_1h=record.htf_bias_1h,
        price_at_T1=record.price_at_T1,
        price_at_T4=record.price_at_T4,
        price_at_T16=record.price_at_T16,
        max_favorable_excursion=record.max_favorable_excursion,
        max_adverse_excursion=record.max_adverse_excursion,
        would_have_hit_sl=record.would_have_hit_sl,
        would_have_hit_tp1=record.would_have_hit_tp1,
        would_have_hit_tp2=record.would_have_hit_tp2,
        audit_completed_at=record.audit_completed_at,
    )


# ---------------------------------------------------------------------------
# Trade audit
# ---------------------------------------------------------------------------

@router.get("/trades", response_model=PaginatedTradeAudit)
def list_trades(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    outcome: Optional[str] = Query(None),
    verdict: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(TradeAuditLog)
    if outcome:
        q = q.filter(TradeAuditLog.outcome == outcome)
    if verdict:
        q = q.filter(TradeAuditLog.signal_quality_verdict == verdict)

    total = q.count()
    records = (
        q.order_by(TradeAuditLog.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    items = [
        TradeAuditListItem(
            id=r.id,
            trade_id=r.trade_id,
            signal_audit_id=r.signal_audit_id,
            outcome=r.outcome,
            exit_price=r.exit_price,
            exit_timestamp=r.exit_timestamp,
            hold_duration_minutes=r.hold_duration_minutes,
            net_pnl=r.net_pnl,
            pnl_pct=r.pnl_pct,
            signal_quality_verdict=r.signal_quality_verdict,
            audit_status=r.audit_status,
        )
        for r in records
    ]
    return PaginatedTradeAudit(total=total, page=page, limit=limit, items=items)


@router.get("/trades/{trade_id}", response_model=TradeAuditDetail)
def get_trade(trade_id: int, db: Session = Depends(get_db)):
    record = db.query(TradeAuditLog).filter(TradeAuditLog.id == trade_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Trade audit not found")
    return TradeAuditDetail(
        id=record.id,
        trade_id=record.trade_id,
        signal_audit_id=record.signal_audit_id,
        outcome=record.outcome,
        exit_price=record.exit_price,
        exit_timestamp=record.exit_timestamp,
        hold_duration_minutes=record.hold_duration_minutes,
        net_pnl=record.net_pnl,
        pnl_pct=record.pnl_pct,
        signal_quality_verdict=record.signal_quality_verdict,
        audit_status=record.audit_status,
        entry_price_proposed=record.entry_price_proposed,
        entry_price_actual=record.entry_price_actual,
        sl_proposed=record.sl_proposed,
        sl_actual=record.sl_actual,
        tp1_proposed=record.tp1_proposed,
        tp1_actual=record.tp1_actual,
        gross_pnl=record.gross_pnl,
        sl_hit_reason=record.sl_hit_reason,
        audit_notes=record.audit_notes,
        analyzed_at=record.analyzed_at,
    )


# ---------------------------------------------------------------------------
# No-signal audit
# ---------------------------------------------------------------------------

@router.get("/no-signals", response_model=PaginatedNoSignalAudit)
def list_no_signals(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    missed_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    q = db.query(NoSignalAuditLog)
    if missed_only:
        q = q.filter(NoSignalAuditLog.missed_opportunity == 1)

    total = q.count()
    records = (
        q.order_by(NoSignalAuditLog.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    items = [
        NoSignalAuditListItem(
            id=r.id,
            signal_audit_id=r.signal_audit_id,
            score_at_decision=r.score_at_decision,
            score_gap=r.score_gap,
            blocking_reason=r.blocking_reason,
            missed_opportunity=r.missed_opportunity,
            would_have_been_profitable=r.would_have_been_profitable,
            hypothetical_pnl_pct=r.hypothetical_pnl_pct,
            audit_status=r.audit_status,
        )
        for r in records
    ]
    return PaginatedNoSignalAudit(total=total, page=page, limit=limit, items=items)
