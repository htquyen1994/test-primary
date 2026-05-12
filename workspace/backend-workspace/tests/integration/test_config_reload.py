"""
Integration Test: Config Hot-Reload
=====================================
Tests that ConfigSystem.reload() applies changes without restart.

Satisfies: Requirement 15.11
"""

from __future__ import annotations

import yaml
from pathlib import Path

import pytest

from config.config_system import ConfigSystem


def test_config_hot_reload(tmp_path: Path):
    """
    Modify config.yaml and call reload() — changes must be applied.
    Satisfies: Requirement 15.11
    """
    config_file = tmp_path / "config.yaml"
    initial = {
        "account": {"balance": 10000.0, "currency": "USDT"},
        "position": {"mode": "risk_pct", "fixed_usd": 100.0, "risk_pct": 0.02,
                     "max_concurrent": 3, "leverage": 5},
        "regime": {"enabled": True, "adx_trending_threshold": 25.0,
                   "adx_choppy_threshold": 20.0, "atr_parabolic_multiplier": 3.0,
                   "parabolic_score_multiplier": 0.6, "ranging_score_multiplier": 0.85,
                   "trending_score_multiplier": 1.0},
        "risk": {"max_daily_loss_pct": 0.05, "max_drawdown_pct": 0.15,
                 "correlation_threshold": 0.8, "max_correlated_risk_pct": 3.0,
                 "portfolio_heat_limit_pct": 6.0, "atr_sl_multiplier": 1.5},
        "strategy": {"active": ["smc_ob_fvg"],
                     "score_threshold": {"alert": 75, "watch": 55},
                     "timeframes": {"trigger": "15m", "context": "1h", "entry": "5m"},
                     "time_invalidation_candles": 15},
        "exchange": {"name": "binance", "market_type": "futures",
                     "fee_rate": 0.001, "slippage_pct": 0.0002, "testnet": True},
        "assets": [{"symbol": "BTC/USDT", "enabled": True, "leverage": 10}],
        "backtest": {"start_date": "2024-01-01", "end_date": "2024-12-31",
                     "walk_forward": {"enabled": False, "in_sample_days": 90,
                                      "out_sample_days": 30, "step_days": 30},
                     "min_trades_threshold": 30, "overfit_degradation_threshold": 0.20},
        "logging": {"level": "INFO", "save_all_signals": True,
                    "log_dir": "logs/", "signal_log_dir": "logs/signals/",
                    "backtest_log_dir": "logs/backtest/"},
    }
    config_file.write_text(yaml.dump(initial), encoding="utf-8")

    cfg = ConfigSystem(str(config_file))
    assert cfg.get().strategy.score_threshold.alert == 75

    # Modify the config file
    updated = dict(initial)
    updated["strategy"] = dict(initial["strategy"])
    updated["strategy"]["score_threshold"] = {"alert": 80, "watch": 60}
    config_file.write_text(yaml.dump(updated), encoding="utf-8")

    # Hot-reload
    cfg.reload()

    # New threshold must be applied
    assert cfg.get().strategy.score_threshold.alert == 80
    assert cfg.get().strategy.score_threshold.watch == 60
