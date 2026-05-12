"""
Property 20: Config Validation Completeness
=============================================
For any config.yaml with any required parameter removed or set to an
invalid type or out-of-range value, the Config_System must raise a
descriptive error that includes the parameter name, expected type or
range, and received value — before any module is initialized or any
data is fetched.

Satisfies: Requirements 15.10, 12.6
"""

import copy
import tempfile
from pathlib import Path

import pytest
import yaml
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from config.config_system import ConfigSystem, ConfigValidationError

# ---------------------------------------------------------------------------
# Minimal valid config used as the base for all mutations
# ---------------------------------------------------------------------------

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


def write_config(cfg_dict: dict) -> str:
    """Write a config dict to a temp file and return the path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    )
    yaml.dump(cfg_dict, tmp)
    tmp.close()
    return tmp.name


def load_config(path: str) -> ConfigSystem:
    return ConfigSystem(path)


# ---------------------------------------------------------------------------
# Unit tests — specific invalid inputs
# ---------------------------------------------------------------------------

class TestConfigValidationUnit:

    def test_valid_config_loads_without_error(self):
        path = write_config(VALID_CONFIG)
        cfg = load_config(path)
        assert cfg.get().exchange.name == "binance"
        assert cfg.get().position.mode == "risk_pct"

    def test_negative_account_balance_raises(self):
        bad = copy.deepcopy(VALID_CONFIG)
        bad["account"]["balance"] = -100.0
        path = write_config(bad)
        with pytest.raises(ConfigValidationError):
            load_config(path)

    def test_invalid_position_mode_raises(self):
        bad = copy.deepcopy(VALID_CONFIG)
        bad["position"]["mode"] = "invalid_mode"
        path = write_config(bad)
        with pytest.raises(ConfigValidationError):
            load_config(path)

    def test_risk_pct_above_10_percent_raises(self):
        bad = copy.deepcopy(VALID_CONFIG)
        bad["position"]["risk_pct"] = 0.5  # 50% — way too high
        path = write_config(bad)
        with pytest.raises(ConfigValidationError):
            load_config(path)

    def test_choppy_threshold_gte_trending_raises(self):
        bad = copy.deepcopy(VALID_CONFIG)
        bad["regime"]["adx_choppy_threshold"] = 30.0   # >= trending (25)
        bad["regime"]["adx_trending_threshold"] = 25.0
        path = write_config(bad)
        with pytest.raises(ConfigValidationError):
            load_config(path)

    def test_watch_threshold_gte_alert_raises(self):
        bad = copy.deepcopy(VALID_CONFIG)
        bad["strategy"]["score_threshold"]["watch"] = 80
        bad["strategy"]["score_threshold"]["alert"] = 75
        path = write_config(bad)
        with pytest.raises(ConfigValidationError):
            load_config(path)

    def test_invalid_market_type_raises(self):
        bad = copy.deepcopy(VALID_CONFIG)
        bad["exchange"]["market_type"] = "options"
        path = write_config(bad)
        with pytest.raises(ConfigValidationError):
            load_config(path)

    def test_invalid_log_level_raises(self):
        bad = copy.deepcopy(VALID_CONFIG)
        bad["logging"]["level"] = "VERBOSE"
        path = write_config(bad)
        with pytest.raises(ConfigValidationError):
            load_config(path)

    def test_missing_config_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")

    def test_error_message_contains_parameter_info(self):
        bad = copy.deepcopy(VALID_CONFIG)
        bad["position"]["mode"] = "bad_mode"
        path = write_config(bad)
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(path)
        # Error message should reference the problematic field
        assert "mode" in str(exc_info.value).lower() or "position" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Strategy for generating invalid position modes
invalid_mode = st.text().filter(lambda s: s not in ("fixed_usd", "risk_pct", "kelly"))

# Strategy for generating out-of-range risk_pct values
invalid_risk_pct = st.one_of(
    st.floats(max_value=0.0, allow_nan=False),   # <= 0
    st.floats(min_value=0.11, max_value=10.0, allow_nan=False),  # > 10%
)

# Strategy for generating invalid market types
invalid_market_type = st.text().filter(lambda s: s not in ("futures", "spot"))


@given(mode=invalid_mode)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_invalid_position_mode_always_raises(mode: str):
    """
    Property 20 (partial): For any position.mode value that is not one of
    {fixed_usd, risk_pct, kelly}, ConfigSystem must raise ConfigValidationError.
    """
    bad = copy.deepcopy(VALID_CONFIG)
    bad["position"]["mode"] = mode
    path = write_config(bad)
    with pytest.raises(ConfigValidationError):
        load_config(path)


@given(risk_pct=invalid_risk_pct)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_invalid_risk_pct_always_raises(risk_pct: float):
    """
    Property 20 (partial): For any risk_pct outside (0, 0.1], ConfigSystem
    must raise ConfigValidationError.
    """
    bad = copy.deepcopy(VALID_CONFIG)
    bad["position"]["risk_pct"] = risk_pct
    path = write_config(bad)
    with pytest.raises(ConfigValidationError):
        load_config(path)


@given(market_type=invalid_market_type)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_invalid_market_type_always_raises(market_type: str):
    """
    Property 20 (partial): For any exchange.market_type not in {futures, spot},
    ConfigSystem must raise ConfigValidationError.
    """
    bad = copy.deepcopy(VALID_CONFIG)
    bad["exchange"]["market_type"] = market_type
    path = write_config(bad)
    with pytest.raises(ConfigValidationError):
        load_config(path)


@given(
    watch=st.integers(min_value=0, max_value=100),
    alert=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_watch_gte_alert_always_raises(watch: int, alert: int):
    """
    Property 20 (partial): When watch threshold >= alert threshold,
    ConfigSystem must raise ConfigValidationError.
    """
    if watch < alert:
        # Valid case — should NOT raise
        bad = copy.deepcopy(VALID_CONFIG)
        bad["strategy"]["score_threshold"]["watch"] = watch
        bad["strategy"]["score_threshold"]["alert"] = alert
        path = write_config(bad)
        cfg = load_config(path)
        assert cfg.get().strategy.score_threshold.watch == watch
    else:
        # Invalid case — MUST raise
        bad = copy.deepcopy(VALID_CONFIG)
        bad["strategy"]["score_threshold"]["watch"] = watch
        bad["strategy"]["score_threshold"]["alert"] = alert
        path = write_config(bad)
        with pytest.raises(ConfigValidationError):
            load_config(path)
