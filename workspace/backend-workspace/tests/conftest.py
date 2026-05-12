"""
Shared test fixtures for the Crypto Trading System test suite.
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

# Force SQLite in-memory for all tests (no SQL Server required for unit/property tests)
# Integration tests that need SQL Server should set DATABASE_URL explicitly
os.environ["DATABASE_URL"] = "sqlite:///:memory:"


VALID_CONFIG = {
    "account": {"balance": 10000.0, "currency": "USDT"},
    "position": {
        "mode": "risk_pct",
        "fixed_usd": 100.0,
        "risk_pct": 0.02,
        "max_concurrent": 3,
        "leverage": 5,
    },
    "regime": {
        "enabled": True,
        "adx_trending_threshold": 25.0,
        "adx_choppy_threshold": 20.0,
        "atr_parabolic_multiplier": 3.0,
        "parabolic_score_multiplier": 0.6,
        "ranging_score_multiplier": 0.85,
        "trending_score_multiplier": 1.0,
    },
    "risk": {
        "max_daily_loss_pct": 0.05,
        "max_drawdown_pct": 0.15,
        "correlation_threshold": 0.8,
        "max_correlated_risk_pct": 3.0,
        "portfolio_heat_limit_pct": 6.0,
        "atr_sl_multiplier": 1.5,
    },
    "strategy": {
        "active": ["smc_ob_fvg"],
        "score_threshold": {"alert": 75, "watch": 55},
        "timeframes": {"trigger": "15m", "context": "1h", "entry": "5m"},
        "time_invalidation_candles": 15,
    },
    "exchange": {
        "name": "binance",
        "market_type": "futures",
        "fee_rate": 0.001,
        "slippage_pct": 0.0002,
        "testnet": True,
    },
    "assets": [{"symbol": "BTC/USDT", "enabled": True, "leverage": 10}],
    "backtest": {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "walk_forward": {"enabled": False, "in_sample_days": 90,
                         "out_sample_days": 30, "step_days": 30},
        "min_trades_threshold": 30,
        "overfit_degradation_threshold": 0.20,
    },
    "logging": {
        "level": "INFO",
        "save_all_signals": True,
        "log_dir": "logs/",
        "signal_log_dir": "logs/signals/",
        "backtest_log_dir": "logs/backtest/",
    },
}


@pytest.fixture
def valid_config_path(tmp_path: Path) -> str:
    """Write a valid config.yaml to a temp file and return the path."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(VALID_CONFIG), encoding="utf-8")
    return str(config_file)


@pytest.fixture
def config_system(valid_config_path: str):
    """Return a loaded ConfigSystem instance."""
    from config.config_system import ConfigSystem
    return ConfigSystem(valid_config_path)
