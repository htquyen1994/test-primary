"""
SQLAlchemy ORM Models
======================
Maps Python classes to SQL Server tables defined in 001_initial_schema.sql.
Uses SQL Server native types: NVARCHAR, DATETIME2, BIT, FLOAT.
Falls back gracefully to SQLite for tests.

Satisfies: Requirements 17.7, 19.5
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.connection import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# signal_log
# ---------------------------------------------------------------------------

class SignalLog(Base):
    """
    Every generated Signal — regardless of classification or user action.
    Satisfies: Requirements 17.1, 17.2, 17.7
    """
    __tablename__ = "signal_log"

    log_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    asset: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    direction: Mapped[str] = mapped_column(String(5), nullable=False)
    candle_index: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_price: Mapped[Optional[float]] = mapped_column(Float)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float)
    take_profit_1: Mapped[Optional[float]] = mapped_column(Float)
    take_profit_2: Mapped[Optional[float]] = mapped_column(Float)
    raw_score: Mapped[float] = mapped_column(Float, nullable=False)
    final_score: Mapped[int] = mapped_column(Integer, nullable=False)
    score_order_flow: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_smc: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_vsa: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_context: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_bonus: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    regime: Mapped[str] = mapped_column(String(20), nullable=False)
    regime_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    funding_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    portfolio_heat: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    correlated_group_risk: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    classification: Mapped[str] = mapped_column(String(10), nullable=False)
    user_action: Mapped[Optional[str]] = mapped_column(String(10))
    skip_reason: Mapped[Optional[str]] = mapped_column(Text)
    expiry_price: Mapped[Optional[float]] = mapped_column(Float)
    expires_at_candle: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("idx_signal_log_asset_ts", "asset", "timestamp"),
        Index("idx_signal_log_classification", "classification"),
        Index("idx_signal_log_strategy", "strategy_name"),
    )

    def __repr__(self) -> str:
        return (
            f"<SignalLog {self.log_id[:8]} | {self.asset} {self.direction} "
            f"score={self.final_score} {self.classification}>"
        )


# ---------------------------------------------------------------------------
# trade_journal
# ---------------------------------------------------------------------------

class TradeJournal(Base):
    """
    Persistent log of all confirmed trades with actual fill prices and PnL.
    Satisfies: Requirements 17, 18.7, 19.5, 19.6, 19.10
    """
    __tablename__ = "trade_journal"

    trade_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    signal_log_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    asset: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)
    direction: Mapped[str] = mapped_column(String(5), nullable=False)
    entry_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[Optional[float]] = mapped_column(Float)
    actual_entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    actual_exit_price: Mapped[Optional[float]] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_1: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_2: Mapped[Optional[float]] = mapped_column(Float)
    position_size_usd: Mapped[float] = mapped_column(Float, nullable=False)
    leverage: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    slippage_entry: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    slippage_exit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fee_entry: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fee_exit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    funding_paid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gross_pnl: Mapped[Optional[float]] = mapped_column(Float)
    net_pnl: Mapped[Optional[float]] = mapped_column(Float)
    result: Mapped[Optional[str]] = mapped_column(String(4))
    signal_score: Mapped[int] = mapped_column(Integer, nullable=False)
    exchange_order_id: Mapped[Optional[str]] = mapped_column(String(100))
    is_testnet: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("idx_trade_journal_asset", "asset"),
        Index("idx_trade_journal_strategy", "strategy_name"),
        Index("idx_trade_journal_entry_ts", "entry_timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<TradeJournal {self.trade_id[:8]} | {self.asset} {self.direction} "
            f"result={self.result} net_pnl={self.net_pnl}>"
        )


# ---------------------------------------------------------------------------
# backtest_results
# ---------------------------------------------------------------------------

class BacktestResult(Base):
    """
    One row per backtest run; includes walk-forward metadata.
    Satisfies: Requirements 9, 10, 11
    """
    __tablename__ = "backtest_results"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    asset: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    win_rate: Mapped[Optional[float]] = mapped_column(Float)
    profit_factor: Mapped[Optional[float]] = mapped_column(Float)
    max_drawdown: Mapped[Optional[float]] = mapped_column(Float)
    sharpe_ratio: Mapped[Optional[float]] = mapped_column(Float)
    recovery_factor: Mapped[Optional[float]] = mapped_column(Float)
    total_trades: Mapped[Optional[int]] = mapped_column(Integer)
    winning_trades: Mapped[Optional[int]] = mapped_column(Integer)
    losing_trades: Mapped[Optional[int]] = mapped_column(Integer)
    is_walk_forward: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    wf_window_index: Mapped[Optional[int]] = mapped_column(Integer)
    is_in_sample: Mapped[Optional[bool]] = mapped_column(Boolean)
    is_statistically_insufficient: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    config_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("idx_backtest_results_strategy", "strategy_name", "asset", "timeframe"),
    )

    def __repr__(self) -> str:
        return (
            f"<BacktestResult {self.run_id[:8]} | {self.strategy_name} "
            f"{self.asset} {self.timeframe} wr={self.win_rate}>"
        )


# ---------------------------------------------------------------------------
# trading_params (Group A — versioned trading parameters)
# ---------------------------------------------------------------------------

class TradingParams(Base):
    """
    Versioned trading parameters — signal scoring, regime, timeframes, strategy thresholds.
    Every change creates a new row. Old rows kept for history and rollback.
    """
    __tablename__ = "trading_params"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    version_tag: Mapped[str] = mapped_column(String(50), nullable=False)
    version_note: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Signal Scoring
    score_alert_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=75)
    score_watch_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=55)
    order_flow_max_pts: Mapped[int] = mapped_column(Integer, nullable=False, default=35)
    smc_max_pts: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    vsa_max_pts: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    context_max_pts: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    confluence_bonus_max_pts: Mapped[int] = mapped_column(Integer, nullable=False, default=15)

    # Regime Detection
    adx_trending_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=25.0)
    adx_choppy_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=20.0)
    atr_parabolic_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    atr_parabolic_rolling_window: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    parabolic_score_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=0.6)
    ranging_score_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=0.85)
    trending_score_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Timeframes
    trigger_timeframe: Mapped[str] = mapped_column(String(5), nullable=False, default="15m")
    context_timeframe: Mapped[str] = mapped_column(String(5), nullable=False, default="1h")
    entry_timeframe: Mapped[str] = mapped_column(String(5), nullable=False, default="5m")
    time_invalidation_candles: Mapped[int] = mapped_column(Integer, nullable=False, default=15)

    # Strategy thresholds
    ob_atr_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.5)
    fvg_touch_tolerance_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.001)
    ob_retest_tolerance_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.002)
    pinbar_tail_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)
    pinbar_body_position_long: Mapped[float] = mapped_column(Float, nullable=False, default=0.70)
    pinbar_body_position_short: Mapped[float] = mapped_column(Float, nullable=False, default=0.30)
    no_supply_vol_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.40)
    effort_result_vol_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.50)
    poc_tolerance_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.003)
    swing_lookback: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    fibonacci_lookback: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    # Risk
    correlation_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    max_correlated_risk_pct: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    portfolio_heat_limit_pct: Mapped[float] = mapped_column(Float, nullable=False, default=6.0)
    # SL/TP parameters (user-configurable via FE → DB → ScoringService)
    atr_sl_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.5)
    tp1_rr_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)
    tp2_rr_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    min_net_rr: Mapped[float] = mapped_column(Float, nullable=False, default=1.5)
    max_concurrent_positions: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    max_daily_loss_pct: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)

    # Backtest
    min_trades_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    overfit_degradation_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.20)

    __table_args__ = (
        Index("idx_trading_params_active", "is_active", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<TradingParams {self.version_tag} active={self.is_active}>"


# ---------------------------------------------------------------------------
# exchange_settings (Group B — exchange credentials and account config)
# ---------------------------------------------------------------------------

class ExchangeSettings(Base):
    """
    Exchange credentials, position sizing, and account configuration.
    API keys stored encrypted. Never returned as plaintext via API.
    """
    __tablename__ = "exchange_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    profile_name: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Exchange selection
    exchange_id: Mapped[str] = mapped_column(String(50), nullable=False, default="binance")
    market_type: Mapped[str] = mapped_column(String(10), nullable=False, default="futures")
    testnet: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # API Credentials (encrypted)
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    api_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    passphrase_encrypted: Mapped[Optional[str]] = mapped_column(Text)

    # Account
    account_balance_usd: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)
    account_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USDT")

    # Position sizing
    sizing_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="risk_pct")
    fixed_usd_per_trade: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    risk_pct_per_trade: Mapped[float] = mapped_column(Float, nullable=False, default=0.02)
    default_leverage: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    # Fees
    fee_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.001)
    slippage_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0002)

    __table_args__ = (
        Index("idx_exchange_settings_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<ExchangeSettings {self.exchange_id} testnet={self.testnet} active={self.is_active}>"


# ---------------------------------------------------------------------------
# exchange_assets (per-asset config linked to exchange_settings)
# ---------------------------------------------------------------------------

class ExchangeAsset(Base):
    """Per-asset configuration: which symbols to trade, leverage overrides."""
    __tablename__ = "exchange_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    exchange_settings_id: Mapped[str] = mapped_column(String(36), nullable=False)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    leverage_override: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_exchange_assets_settings", "exchange_settings_id", "enabled"),
    )

    def __repr__(self) -> str:
        return f"<ExchangeAsset {self.symbol} enabled={self.enabled}>"
