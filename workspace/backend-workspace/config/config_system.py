"""
Config System
=============
Loads, validates, and hot-reloads config.yaml.
All modules source their parameters from this single object.

Satisfies: Requirements 15.1–15.11, 12.5, 12.6
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import List, Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class ConfigValidationError(ValueError):
    """
    Raised when config.yaml has a missing or invalid parameter.
    Satisfies: Requirement 15.10, 12.6
    """
    pass


# ---------------------------------------------------------------------------
# Pydantic config models — one per namespace
# ---------------------------------------------------------------------------

class AccountConfig(BaseModel):
    balance: float = Field(gt=0, description="Account balance in USD")
    currency: str = Field(default="USDT")


class PositionConfig(BaseModel):
    mode: Literal["fixed_usd", "risk_pct", "kelly"] = "risk_pct"
    fixed_usd: float = Field(default=100.0, gt=0,
                             description="USD per trade when mode=fixed_usd")
    risk_pct: float = Field(default=0.02, gt=0, le=0.1,
                            description="Fraction of equity risked per trade (0.02 = 2%)")
    max_concurrent: int = Field(default=3, ge=1, le=20)
    leverage: int = Field(default=5, ge=1, le=125)


class RegimeConfig(BaseModel):
    enabled: bool = True
    adx_trending_threshold: float = Field(default=25.0, gt=0)
    adx_choppy_threshold: float = Field(default=20.0, gt=0)
    atr_parabolic_multiplier: float = Field(default=3.0, gt=1.0)
    parabolic_score_multiplier: float = Field(default=0.6, gt=0, le=1.0)
    ranging_score_multiplier: float = Field(default=0.85, gt=0, le=1.0)
    trending_score_multiplier: float = Field(default=1.0, gt=0, le=1.0)

    @model_validator(mode="after")
    def choppy_lt_trending(self) -> "RegimeConfig":
        if self.adx_choppy_threshold >= self.adx_trending_threshold:
            raise ValueError(
                f"adx_choppy_threshold ({self.adx_choppy_threshold}) must be "
                f"less than adx_trending_threshold ({self.adx_trending_threshold})"
            )
        return self


class RiskConfig(BaseModel):
    max_daily_loss_pct: float = Field(default=0.05, gt=0, le=1.0)
    max_drawdown_pct: float = Field(default=0.15, gt=0, le=1.0)
    correlation_threshold: float = Field(default=0.8, gt=0, le=1.0)
    max_correlated_risk_pct: float = Field(default=3.0, gt=0)
    portfolio_heat_limit_pct: float = Field(default=6.0, gt=0)
    # ATR-based SL/TP parameters (user-configurable via FE)
    atr_sl_multiplier: float = Field(default=1.5, gt=0,
                                     description="SL distance = ATR × this multiplier")
    tp1_rr: float = Field(default=2.0, gt=1.0,
                          description="TP1 gross R:R (e.g. 2.0 = 2× SL distance)")
    tp2_rr: float = Field(default=3.0, gt=1.0,
                          description="TP2 gross R:R (e.g. 3.0 = 3× SL distance)")
    min_net_rr: float = Field(default=1.5, gt=0,
                              description="Minimum net R:R after fees — alerts below this are suppressed")

    @model_validator(mode="after")
    def tp_rr_ordering(self) -> "RiskConfig":
        if self.tp1_rr >= self.tp2_rr:
            raise ValueError(
                f"tp1_rr ({self.tp1_rr}) must be less than tp2_rr ({self.tp2_rr})"
            )
        return self


class ScoreThresholdConfig(BaseModel):
    alert: int = Field(default=75, ge=0, le=100)
    watch: int = Field(default=55, ge=0, le=100)

    @model_validator(mode="after")
    def watch_lt_alert(self) -> "ScoreThresholdConfig":
        if self.watch >= self.alert:
            raise ValueError(
                f"watch threshold ({self.watch}) must be less than alert threshold ({self.alert})"
            )
        return self


class TimeframesConfig(BaseModel):
    trigger: str = "15m"
    context: str = "1h"
    entry: str = "5m"


class StrategyConfig(BaseModel):
    active: List[str] = Field(default_factory=list,
                              description="List of strategy names to load from registry")
    score_threshold: ScoreThresholdConfig = Field(default_factory=ScoreThresholdConfig)
    timeframes: TimeframesConfig = Field(default_factory=TimeframesConfig)
    time_invalidation_candles: int = Field(default=15, ge=1)


class ExchangeConfig(BaseModel):
    name: str = Field(default="binance", description="ccxt exchange id")
    market_type: Literal["futures", "spot"] = "futures"
    fee_rate: float = Field(default=0.001, gt=0, le=0.01)
    slippage_pct: float = Field(default=0.0002, ge=0, le=0.01)
    testnet: bool = Field(default=True,
                          description="MUST be explicitly false for live trading")


class AssetConfig(BaseModel):
    symbol: str
    enabled: bool = True
    leverage: Optional[int] = Field(default=None, ge=1, le=125)


class WalkForwardConfig(BaseModel):
    enabled: bool = False
    in_sample_days: int = Field(default=90, ge=1)
    out_sample_days: int = Field(default=30, ge=1)
    step_days: int = Field(default=30, ge=1)


class BacktestConfig(BaseModel):
    start_date: str = "2024-01-01"
    end_date: str = "2024-12-31"
    walk_forward: WalkForwardConfig = Field(default_factory=WalkForwardConfig)
    min_trades_threshold: int = Field(default=30, ge=1)
    overfit_degradation_threshold: float = Field(default=0.20, gt=0, le=1.0)


class LoggingConfig(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    save_all_signals: bool = True
    log_dir: str = "logs/"
    signal_log_dir: str = "logs/signals/"
    backtest_log_dir: str = "logs/backtest/"


class AppConfig(BaseModel):
    """Root configuration object — all namespaces."""
    account: AccountConfig = Field(default_factory=lambda: AccountConfig(balance=10000.0))
    position: PositionConfig = Field(default_factory=PositionConfig)
    regime: RegimeConfig = Field(default_factory=RegimeConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig)
    assets: List[AssetConfig] = Field(default_factory=list)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


# ---------------------------------------------------------------------------
# ConfigSystem
# ---------------------------------------------------------------------------

class ConfigSystem:
    """
    Loads, validates, and hot-reloads config.yaml.

    Usage:
        cfg = ConfigSystem("config.yaml")
        exchange_name = cfg.get().exchange.name

    Satisfies: Requirements 15.1–15.11
    """

    def __init__(self, config_path: str = "config.yaml") -> None:
        self._path = Path(config_path)
        self._config: AppConfig = self._load()
        self._lock = threading.RLock()
        self._reload_callbacks: list = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self) -> AppConfig:
        """Return the validated configuration object."""
        with self._lock:
            return self._config

    def reload(self) -> None:
        """
        Re-read and re-validate config.yaml without restarting the process.
        Applies changes to all modules on the next candle close.
        Satisfies: Requirement 15.11
        """
        with self._lock:
            new_config = self._load()
            self._config = new_config
            logger.info("Config reloaded from %s", self._path)
            for cb in self._reload_callbacks:
                try:
                    cb(new_config)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Reload callback %s raised: %s", cb, exc)

    def on_reload(self, callback) -> None:
        """Register a callback invoked after each successful reload."""
        self._reload_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> AppConfig:
        """
        Read YAML file and validate with Pydantic.
        Raises ConfigValidationError with parameter name + expected type
        before any module is initialized.
        Satisfies: Requirements 15.1, 15.10, 12.6
        """
        if not self._path.exists():
            raise FileNotFoundError(
                f"config.yaml not found at '{self._path}'. "
                "Copy config.example.yaml to config.yaml and fill in your values."
            )

        with open(self._path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        try:
            return AppConfig.model_validate(raw)
        except Exception as exc:
            # Re-raise as ConfigValidationError with a clear message
            raise ConfigValidationError(
                f"config.yaml validation failed:\n{exc}\n\n"
                f"File: {self._path.resolve()}"
            ) from exc
