"""
Pydantic request/response schemas for FastAPI endpoints.
"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel


class ScoreBreakdownSchema(BaseModel):
    order_flow: float
    smc: float
    vsa: float
    context: float
    bonus: float


class SignalCardResponse(BaseModel):
    signal_id: str
    strategy_name: str
    asset: str
    timeframe: str
    direction: str
    final_score: int
    classification: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    gross_rr: float
    net_rr: float
    score_breakdown: ScoreBreakdownSchema
    regime: str
    expires_at_candle: int
    created_at: str


class SkipRequest(BaseModel):
    reason: Optional[str] = None


class TradeJournalEntry(BaseModel):
    trade_id: str
    strategy_name: str
    asset: str
    direction: str
    entry_timestamp: str
    exit_timestamp: Optional[str]
    entry_price: float
    actual_entry_price: float
    actual_exit_price: Optional[float]
    stop_loss: float
    take_profit_1: float
    position_size_usd: float
    slippage_entry: float
    fee_entry: float
    fee_exit: float
    gross_pnl: Optional[float]
    net_pnl: Optional[float]
    result: Optional[str]
    signal_score: int
    is_testnet: bool


class AnalyticsResponse(BaseModel):
    total_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    net_profit: float


class PortfolioResponse(BaseModel):
    portfolio_heat: float
    open_positions: dict


class BacktestRunRequest(BaseModel):
    strategy: str
    asset: str
    timeframe: str
    start_date: str
    end_date: str
