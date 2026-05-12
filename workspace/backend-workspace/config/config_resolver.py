"""
Config Resolver
================
Merges config.yaml (file-based) and DB-stored settings into one unified config.

Priority rule:
  DB > config.yaml

  - DB (trading_params, exchange_settings) = user's latest intent via UI
  - config.yaml = fallback for first run + non-DB settings (strategy.active, backtest, logging)

This eliminates the conflict between the two config sources.

Usage:
    resolver = ConfigResolver(config_system, db_session)
    unified = resolver.get_unified_config()

    # Use unified config everywhere instead of config_system.get() directly
    exchange_id  = unified["exchange"]["exchange_id"]   # from DB
    alert_thresh = unified["scoring"]["score_alert_threshold"]  # from DB
    strategies   = unified["strategy"]["active"]        # from config.yaml
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ConfigResolver:
    """
    Merges config.yaml and DB settings with DB taking priority.

    Sections sourced from DB (when available):
      - exchange settings (exchange_id, testnet, api_key, market_type, etc.)
      - position sizing (sizing_mode, fixed_usd_per_trade, risk_pct_per_trade, leverage)
      - trading parameters (scoring thresholds, regime, timeframes, risk limits)

    Sections always from config.yaml:
      - strategy.active (list of strategy names)
      - backtest settings
      - logging settings
    """

    def __init__(self, config_system, db_session=None) -> None:
        self._cfg = config_system
        self._db = db_session

    def get_unified_config(self) -> dict:
        """
        Return a unified config dict merging DB and config.yaml.
        DB values take priority over config.yaml values.
        """
        yaml_cfg = self._cfg.get()

        # Start with config.yaml as base
        unified = {
            # Always from config.yaml
            "strategy": {
                "active": yaml_cfg.strategy.active,
                "timeframes": {
                    "trigger": yaml_cfg.strategy.timeframes.trigger,
                    "context": yaml_cfg.strategy.timeframes.context,
                    "entry": yaml_cfg.strategy.timeframes.entry,
                },
            },
            "backtest": {
                "start_date": yaml_cfg.backtest.start_date,
                "end_date": yaml_cfg.backtest.end_date,
                "walk_forward": {
                    "enabled": yaml_cfg.backtest.walk_forward.enabled,
                    "in_sample_days": yaml_cfg.backtest.walk_forward.in_sample_days,
                    "out_sample_days": yaml_cfg.backtest.walk_forward.out_sample_days,
                    "step_days": yaml_cfg.backtest.walk_forward.step_days,
                },
                "min_trades_threshold": yaml_cfg.backtest.min_trades_threshold,
                "overfit_degradation_threshold": yaml_cfg.backtest.overfit_degradation_threshold,
            },
            "logging": {
                "level": yaml_cfg.logging.level,
                "save_all_signals": yaml_cfg.logging.save_all_signals,
                "log_dir": yaml_cfg.logging.log_dir,
            },
        }

        # Merge DB settings (DB takes priority)
        if self._db is not None:
            try:
                from config.config_service import (
                    get_active_trading_params,
                    get_active_exchange_settings,
                )
                db_trading = get_active_trading_params(self._db)
                db_exchange = get_active_exchange_settings(self._db)

                # Trading params from DB
                unified["scoring"] = {
                    "score_alert_threshold": db_trading["score_alert_threshold"],
                    "score_watch_threshold": db_trading["score_watch_threshold"],
                    "order_flow_max_pts": db_trading["order_flow_max_pts"],
                    "smc_max_pts": db_trading["smc_max_pts"],
                    "vsa_max_pts": db_trading["vsa_max_pts"],
                    "context_max_pts": db_trading["context_max_pts"],
                    "confluence_bonus_max_pts": db_trading["confluence_bonus_max_pts"],
                }
                unified["regime"] = {
                    "adx_trending_threshold": db_trading["adx_trending_threshold"],
                    "adx_choppy_threshold": db_trading["adx_choppy_threshold"],
                    "atr_parabolic_multiplier": db_trading["atr_parabolic_multiplier"],
                    "atr_parabolic_rolling_window": db_trading["atr_parabolic_rolling_window"],
                    "parabolic_score_multiplier": db_trading["parabolic_score_multiplier"],
                    "ranging_score_multiplier": db_trading["ranging_score_multiplier"],
                    "trending_score_multiplier": db_trading["trending_score_multiplier"],
                }
                unified["risk"] = {
                    "correlation_threshold": db_trading["correlation_threshold"],
                    "max_correlated_risk_pct": db_trading["max_correlated_risk_pct"],
                    "portfolio_heat_limit_pct": db_trading["portfolio_heat_limit_pct"],
                    "atr_sl_multiplier": db_trading["atr_sl_multiplier"],
                    "tp1_rr_ratio": db_trading["tp1_rr_ratio"],
                    "tp2_rr_ratio": db_trading["tp2_rr_ratio"],
                    "max_concurrent_positions": db_trading["max_concurrent_positions"],
                    "max_daily_loss_pct": db_trading["max_daily_loss_pct"],
                    # Keep max_drawdown_pct from config.yaml (not in DB yet)
                    "max_drawdown_pct": yaml_cfg.risk.max_drawdown_pct,
                }
                unified["strategy"]["time_invalidation_candles"] = db_trading["time_invalidation_candles"]
                unified["strategy"]["timeframes"]["trigger"] = db_trading["trigger_timeframe"]
                unified["strategy"]["timeframes"]["context"] = db_trading["context_timeframe"]

                # Exchange settings from DB
                unified["exchange"] = {
                    "exchange_id": db_exchange["exchange_id"],
                    "name": db_exchange["exchange_id"],  # alias for backward compat
                    "market_type": db_exchange["market_type"],
                    "testnet": db_exchange["testnet"],
                    "fee_rate": db_exchange["fee_rate"],
                    "slippage_pct": db_exchange["slippage_pct"],
                    # Credentials — internal use only, never expose via API
                    "api_key": db_exchange["api_key"],
                    "api_secret": db_exchange["api_secret"],
                    "passphrase": db_exchange["passphrase"],
                }
                unified["account"] = {
                    "balance": db_exchange["account_balance_usd"],
                    "currency": db_exchange["account_currency"],
                }
                unified["position"] = {
                    "mode": db_exchange["sizing_mode"],
                    "fixed_usd": db_exchange["fixed_usd_per_trade"],
                    "risk_pct": db_exchange["risk_pct_per_trade"],
                    "leverage": db_exchange["default_leverage"],
                    "max_concurrent": db_trading["max_concurrent_positions"],
                }
                unified["assets"] = db_exchange["assets"]

                logger.debug("Config resolved: DB settings applied (DB > config.yaml)")

            except Exception as exc:
                logger.warning(
                    "DB config unavailable (%s) — falling back to config.yaml", exc
                )
                unified = self._fallback_from_yaml(yaml_cfg, unified)
        else:
            unified = self._fallback_from_yaml(yaml_cfg, unified)

        return unified

    def _fallback_from_yaml(self, yaml_cfg, unified: dict) -> dict:
        """Fill in from config.yaml when DB is not available."""
        unified["scoring"] = {
            "score_alert_threshold": yaml_cfg.strategy.score_threshold.alert,
            "score_watch_threshold": yaml_cfg.strategy.score_threshold.watch,
            "order_flow_max_pts": 35,
            "smc_max_pts": 30,
            "vsa_max_pts": 30,
            "context_max_pts": 15,
            "confluence_bonus_max_pts": 15,
        }
        unified["regime"] = {
            "adx_trending_threshold": yaml_cfg.regime.adx_trending_threshold,
            "adx_choppy_threshold": yaml_cfg.regime.adx_choppy_threshold,
            "atr_parabolic_multiplier": yaml_cfg.regime.atr_parabolic_multiplier,
            "atr_parabolic_rolling_window": 20,
            "parabolic_score_multiplier": yaml_cfg.regime.parabolic_score_multiplier,
            "ranging_score_multiplier": yaml_cfg.regime.ranging_score_multiplier,
            "trending_score_multiplier": yaml_cfg.regime.trending_score_multiplier,
        }
        unified["risk"] = {
            "correlation_threshold": yaml_cfg.risk.correlation_threshold,
            "max_correlated_risk_pct": yaml_cfg.risk.max_correlated_risk_pct,
            "portfolio_heat_limit_pct": yaml_cfg.risk.portfolio_heat_limit_pct,
            "atr_sl_multiplier": yaml_cfg.risk.atr_sl_multiplier,
            "tp1_rr_ratio": 1.5,
            "tp2_rr_ratio": 2.5,
            "max_concurrent_positions": yaml_cfg.position.max_concurrent,
            "max_daily_loss_pct": yaml_cfg.risk.max_daily_loss_pct,
            "max_drawdown_pct": yaml_cfg.risk.max_drawdown_pct,
        }
        unified["exchange"] = {
            "exchange_id": yaml_cfg.exchange.name,
            "name": yaml_cfg.exchange.name,
            "market_type": yaml_cfg.exchange.market_type,
            "testnet": yaml_cfg.exchange.testnet,
            "fee_rate": yaml_cfg.exchange.fee_rate,
            "slippage_pct": yaml_cfg.exchange.slippage_pct,
            "api_key": "",
            "api_secret": "",
            "passphrase": "",
        }
        unified["account"] = {
            "balance": yaml_cfg.account.balance,
            "currency": yaml_cfg.account.currency,
        }
        unified["position"] = {
            "mode": yaml_cfg.position.mode,
            "fixed_usd": yaml_cfg.position.fixed_usd,
            "risk_pct": yaml_cfg.position.risk_pct,
            "leverage": yaml_cfg.position.leverage,
            "max_concurrent": yaml_cfg.position.max_concurrent,
        }
        unified["assets"] = [
            {"symbol": a.symbol, "enabled": a.enabled, "leverage": a.leverage}
            for a in yaml_cfg.assets
        ]
        unified["strategy"]["time_invalidation_candles"] = yaml_cfg.strategy.time_invalidation_candles
        return unified
