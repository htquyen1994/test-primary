"""
ORM Models — 8 tables for mock exchange + audit system.
All timestamps stored as ISO-8601 TEXT (SQLite compatible).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    CheckConstraint, Float, ForeignKey, Index, Integer,
    Text, UniqueConstraint, event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Mock Exchange Tables
# ---------------------------------------------------------------------------

class MockOrder(Base):
    __tablename__ = "mock_orders"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    side: Mapped[str] = mapped_column(
        Text, nullable=False,
        info={"check": "side IN ('buy', 'sell')"}
    )
    order_type: Mapped[str] = mapped_column(
        Text, nullable=False,
        info={"check": "order_type IN ('market', 'limit', 'stop_loss', 'take_profit')"}
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="PENDING")
    filled_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fill_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    client_order_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signal_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_now_iso)
    filled_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("side IN ('buy', 'sell')", name="ck_order_side"),
        CheckConstraint(
            "order_type IN ('market', 'limit', 'stop_loss', 'take_profit')",
            name="ck_order_type"
        ),
        CheckConstraint(
            "status IN ('PENDING','OPEN','FILLED','PARTIAL','CANCELLED','REJECTED','EXPIRED')",
            name="ck_order_status"
        ),
    )


class MockPosition(Base):
    __tablename__ = "mock_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    leverage: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_1: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="OPEN")
    entry_order_id: Mapped[Optional[str]] = mapped_column(
        Text, ForeignKey("mock_orders.id"), nullable=True
    )
    signal_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    opened_at: Mapped[str] = mapped_column(Text, nullable=False, default=_now_iso)
    closed_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    funding_rate_at_entry: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    __table_args__ = (
        CheckConstraint("direction IN ('long', 'short')", name="ck_position_direction"),
        CheckConstraint("status IN ('OPEN', 'CLOSED')", name="ck_position_status"),
        CheckConstraint(
            "exit_reason IN ('SL_HIT','TP1_HIT','TP2_HIT','MANUAL_CLOSE','EXPIRED') OR exit_reason IS NULL",
            name="ck_position_exit_reason"
        ),
        Index("idx_mock_positions_status", "status", "symbol"),
    )


class MockAccount(Base):
    __tablename__ = "mock_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    balance_usd: Mapped[float] = mapped_column(Float, nullable=False)
    equity_usd: Mapped[float] = mapped_column(Float, nullable=False)
    used_margin: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_realized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_fees_paid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=_now_iso)


class MockAccountHistory(Base):
    __tablename__ = "mock_account_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    balance_usd: Mapped[float] = mapped_column(Float, nullable=False)
    equity_usd: Mapped[float] = mapped_column(Float, nullable=False)
    trade_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("mock_positions.id"), nullable=True
    )
    event: Mapped[str] = mapped_column(Text, nullable=False)
    pnl_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recorded_at: Mapped[str] = mapped_column(Text, nullable=False, default=_now_iso)


# ---------------------------------------------------------------------------
# Audit Tables
# ---------------------------------------------------------------------------

class SignalAuditLog(Base):
    __tablename__ = "signal_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    timeframe: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp_candle_close: Mapped[str] = mapped_column(Text, nullable=False)

    # Signal result
    signal_result: Mapped[str] = mapped_column(Text, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_breakdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON

    # Filter state
    regime: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    regime_multiplier: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mtf_scenario: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mtf_4h_bias: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    daily_bias: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    btc_guard_active: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    circuit_breaker_locked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocking_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blocking_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Technical params
    entry_price_proposed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sl_proposed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tp1_proposed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tp2_proposed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    atr_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    adx_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delta_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delta_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    funding_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ob_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    poc_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    htf_bias_1h: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Forward prices (filled by SignalAuditor)
    price_at_T1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_at_T4: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_at_T16: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_favorable_excursion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_adverse_excursion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    would_have_hit_sl: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    would_have_hit_tp1: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    would_have_hit_tp2: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Audit lifecycle
    audit_status: Mapped[str] = mapped_column(Text, nullable=False, default="PENDING")
    audit_completed_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_now_iso)

    __table_args__ = (
        CheckConstraint("signal_result IN ('SIGNAL', 'NO_SIGNAL')", name="ck_sal_result"),
        CheckConstraint(
            "audit_status IN ('PENDING','PARTIAL','COMPLETE')",
            name="ck_sal_audit_status"
        ),
        Index("idx_signal_audit_symbol_ts", "symbol", "timestamp_candle_close"),
        Index("idx_signal_audit_status", "audit_status"),
        Index("idx_signal_audit_result", "signal_result"),
    )


class TradeAuditLog(Base):
    __tablename__ = "trade_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mock_positions.id"), nullable=False
    )
    signal_audit_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("signal_audit_log.id"), nullable=True
    )

    # Execution quality
    entry_price_proposed: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price_actual: Mapped[float] = mapped_column(Float, nullable=False)
    sl_proposed: Mapped[float] = mapped_column(Float, nullable=False)
    sl_actual: Mapped[float] = mapped_column(Float, nullable=False)
    tp1_proposed: Mapped[float] = mapped_column(Float, nullable=False)
    tp1_actual: Mapped[float] = mapped_column(Float, nullable=False)

    # Outcome
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exit_timestamp: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hold_duration_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gross_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Post-trade analysis
    sl_hit_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signal_quality_verdict: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audit_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audit_status: Mapped[str] = mapped_column(Text, nullable=False, default="PENDING")
    analyzed_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "outcome IN ('SL_HIT','TP1_HIT','TP2_HIT','MANUAL_CLOSE','EXPIRED')",
            name="ck_tal_outcome"
        ),
        CheckConstraint(
            "sl_hit_reason IN ('NOISE','TREND_REVERSAL','NEWS_EVENT','BTC_SPIKE') OR sl_hit_reason IS NULL",
            name="ck_tal_sl_reason"
        ),
        CheckConstraint(
            "signal_quality_verdict IN ('TRUE_POSITIVE','FALSE_POSITIVE','PREMATURE_SL') OR signal_quality_verdict IS NULL",
            name="ck_tal_verdict"
        ),
        CheckConstraint(
            "audit_status IN ('PENDING','ANALYZED','REVIEWED')",
            name="ck_tal_audit_status"
        ),
        Index("idx_trade_audit_signal", "signal_audit_id"),
    )


class NoSignalAuditLog(Base):
    __tablename__ = "no_signal_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_audit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("signal_audit_log.id"), nullable=False
    )

    score_at_decision: Mapped[float] = mapped_column(Float, nullable=False)
    score_gap: Mapped[float] = mapped_column(Float, nullable=False)
    blocking_reason: Mapped[str] = mapped_column(Text, nullable=False)
    blocking_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Counterfactual
    hypothetical_entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hypothetical_sl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hypothetical_tp1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    would_have_been_profitable: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hypothetical_pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    missed_opportunity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    audit_status: Mapped[str] = mapped_column(Text, nullable=False, default="PENDING")
    completed_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "audit_status IN ('PENDING','COMPLETE')",
            name="ck_nsal_audit_status"
        ),
        Index("idx_no_signal_missed", "missed_opportunity"),
    )


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    timeframe: Mapped[str] = mapped_column(Text, nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[str] = mapped_column(Text, nullable=False, default=_now_iso)

    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_price_snapshot"),
        Index("idx_price_snapshots_lookup", "symbol", "timeframe", "timestamp"),
    )
