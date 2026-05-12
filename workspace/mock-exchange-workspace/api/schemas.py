"""
Pydantic schemas for all request/response models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Exchange schemas
# ---------------------------------------------------------------------------

class CreateOrderRequest(BaseModel):
    symbol: str
    side: str  # "buy" | "sell"
    order_type: str  # "market" | "limit" | "stop_loss" | "take_profit"
    amount: float
    price: float
    client_order_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class OrderResponse(BaseModel):
    order_id: str
    symbol: str
    side: str
    order_type: str
    amount: float
    price: float
    status: str
    filled_amount: float
    fill_price: Optional[float]
    fee: float
    created_at: str
    filled_at: Optional[str]
    client_order_id: Optional[str]


class PositionResponse(BaseModel):
    symbol: str
    direction: str
    entry_price: float
    amount: float
    leverage: int
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float]
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    opened_at: str
    signal_id: Optional[str]


class AccountStateResponse(BaseModel):
    balance_usd: float
    equity_usd: float
    used_margin: float
    free_margin: float
    total_realized_pnl: float
    total_fees_paid: float


class PriceResponse(BaseModel):
    symbol: str
    price: float


# ---------------------------------------------------------------------------
# Audit schemas
# ---------------------------------------------------------------------------

class SignalAuditListItem(BaseModel):
    id: int
    signal_id: Optional[str]
    symbol: str
    timeframe: str
    timestamp_candle_close: str
    signal_result: str
    final_score: float
    regime: Optional[str]
    mtf_scenario: Optional[str]
    blocking_reason: Optional[str]
    audit_status: str
    created_at: str


class SignalAuditDetail(SignalAuditListItem):
    score_breakdown: Optional[str]
    regime_multiplier: Optional[float]
    mtf_4h_bias: Optional[str]
    daily_bias: Optional[str]
    btc_guard_active: int
    circuit_breaker_locked: int
    blocking_detail: Optional[str]
    entry_price_proposed: Optional[float]
    sl_proposed: Optional[float]
    tp1_proposed: Optional[float]
    tp2_proposed: Optional[float]
    atr_value: Optional[float]
    adx_value: Optional[float]
    delta_value: Optional[float]
    delta_threshold: Optional[float]
    funding_rate: Optional[float]
    ob_available: int
    poc_value: Optional[float]
    htf_bias_1h: Optional[str]
    price_at_T1: Optional[float]
    price_at_T4: Optional[float]
    price_at_T16: Optional[float]
    max_favorable_excursion: Optional[float]
    max_adverse_excursion: Optional[float]
    would_have_hit_sl: Optional[int]
    would_have_hit_tp1: Optional[int]
    would_have_hit_tp2: Optional[int]
    audit_completed_at: Optional[str]


class PaginatedSignalAudit(BaseModel):
    total: int
    page: int
    limit: int
    items: List[SignalAuditListItem]


class TradeAuditListItem(BaseModel):
    id: int
    trade_id: int
    signal_audit_id: Optional[int]
    outcome: str
    exit_price: Optional[float]
    exit_timestamp: Optional[str]
    hold_duration_minutes: Optional[float]
    net_pnl: Optional[float]
    pnl_pct: Optional[float]
    signal_quality_verdict: Optional[str]
    audit_status: str


class TradeAuditDetail(TradeAuditListItem):
    entry_price_proposed: float
    entry_price_actual: float
    sl_proposed: float
    sl_actual: float
    tp1_proposed: float
    tp1_actual: float
    gross_pnl: Optional[float]
    sl_hit_reason: Optional[str]
    audit_notes: Optional[str]
    analyzed_at: Optional[str]


class PaginatedTradeAudit(BaseModel):
    total: int
    page: int
    limit: int
    items: List[TradeAuditListItem]


class NoSignalAuditListItem(BaseModel):
    id: int
    signal_audit_id: int
    score_at_decision: float
    score_gap: float
    blocking_reason: str
    missed_opportunity: Optional[int]
    would_have_been_profitable: Optional[int]
    hypothetical_pnl_pct: Optional[float]
    audit_status: str


class PaginatedNoSignalAudit(BaseModel):
    total: int
    page: int
    limit: int
    items: List[NoSignalAuditListItem]


# ---------------------------------------------------------------------------
# Analytics schemas
# ---------------------------------------------------------------------------

class WinRateWithCI(BaseModel):
    value: float
    ci_95: List[float]


class PerformanceReportResponse(BaseModel):
    sample_size: int
    confidence: str
    confidence_note: str
    win_rate: WinRateWithCI
    win_rate_by_regime: Dict[str, float]
    win_rate_by_mtf_scenario: Dict[str, float]
    win_rate_by_score_bucket: Dict[str, float]
    optimal_threshold_suggestion: Optional[int]
    module_correlation: Dict[str, Any]
    missed_opportunity_rate: float
    sl_hit_reasons: Dict[str, float]
    atr_sl_comparison: Dict[str, Any]
    win_rate_by_hour: Dict[str, float]
    funding_rate_correlation: Dict[str, Any]
    questions: Dict[str, str]


class TuningRecommendation(BaseModel):
    type: str
    confidence: str
    suggestion: Optional[str] = None
    rationale: Optional[str] = None
    current: Optional[Any] = None
    suggested: Optional[Any] = None
    regime: Optional[str] = None
    win_rate: Optional[float] = None
    noise_rate: Optional[float] = None


class TuningReportResponse(BaseModel):
    confidence: str
    sample_size: int
    note: Optional[str] = None
    recommendations: List[TuningRecommendation]
