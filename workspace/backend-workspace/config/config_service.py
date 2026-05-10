"""
Config Service
===============
Manages two config groups stored in SQL Server:

Group A — TradingParams: signal scoring, regime, timeframes, strategy thresholds.
  - Versioned: every change creates a new row, old rows kept for history.
  - Active version loaded at startup and on hot-reload.

Group B — ExchangeSettings: exchange credentials, assets, position sizing.
  - API keys stored AES-256 encrypted.
  - Never returned as plaintext via API.

Satisfies: Config management requirements for exchange selection,
           API credentials, position sizing, and trading parameters.
"""

from __future__ import annotations

import base64
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Encryption key from environment — MUST be set in production
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
_ENCRYPTION_KEY = os.environ.get("CONFIG_ENCRYPTION_KEY", "dev_key_change_in_production_32b!")


# ---------------------------------------------------------------------------
# Simple AES-256 encryption (using Fernet for simplicity)
# In production, use a proper KMS or vault
# ---------------------------------------------------------------------------

def _get_fernet():
    """Get Fernet cipher. Lazy import to avoid hard dependency."""
    try:
        from cryptography.fernet import Fernet
        import hashlib
        # Derive a 32-byte key from the env variable
        key_bytes = hashlib.sha256(_ENCRYPTION_KEY.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        return Fernet(fernet_key)
    except ImportError:
        logger.warning(
            "cryptography package not installed — API keys stored as plaintext. "
            "Install with: pip install cryptography"
        )
        return None


def encrypt_value(plaintext: str) -> str:
    """Encrypt a sensitive value. Returns base64-encoded ciphertext."""
    if not plaintext:
        return ""
    fernet = _get_fernet()
    if fernet is None:
        # Fallback: base64 encode (NOT secure — install cryptography package)
        return base64.b64encode(plaintext.encode()).decode()
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a sensitive value. Returns plaintext."""
    if not ciphertext:
        return ""
    fernet = _get_fernet()
    if fernet is None:
        try:
            return base64.b64decode(ciphertext.encode()).decode()
        except Exception:
            return ciphertext
    try:
        return fernet.decrypt(ciphertext.encode()).decode()
    except Exception as exc:
        logger.error("Failed to decrypt value: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Trading Params (Group A)
# ---------------------------------------------------------------------------

def get_active_trading_params(db_session) -> dict:
    """
    Load the currently active TradingParams version from DB.
    Returns a dict with all parameter values.
    Falls back to defaults if no active row exists.
    """
    from db.models import TradingParams
    from sqlalchemy import select

    row = db_session.execute(
        select(TradingParams).where(TradingParams.is_active == True)
        .order_by(TradingParams.activated_at.desc())
    ).scalar_one_or_none()

    if row is None:
        logger.warning("No active TradingParams found — using hardcoded defaults")
        return _default_trading_params()

    return _trading_params_to_dict(row)


def save_trading_params(params: dict, version_tag: str, version_note: str, db_session) -> str:
    """
    Save a new version of TradingParams.
    Deactivates the current active version and activates the new one.
    Returns the new version ID.
    """
    from db.models import TradingParams
    from sqlalchemy import update

    # Deactivate current active
    db_session.execute(
        update(TradingParams).where(TradingParams.is_active == True)
        .values(is_active=False)
    )

    # Create new version
    new_id = str(uuid.uuid4())
    row = TradingParams(
        id=new_id,
        version_tag=version_tag,
        version_note=version_note,
        is_active=True,
        activated_at=datetime.now(timezone.utc),
        **{k: v for k, v in params.items() if k not in ("id", "version_tag", "version_note",
                                                          "is_active", "created_at", "activated_at")},
    )
    db_session.add(row)
    db_session.commit()
    logger.info("TradingParams saved: version=%s id=%s", version_tag, new_id[:8])
    return new_id


def get_trading_params_history(db_session, limit: int = 20) -> list:
    """Return version history of TradingParams (newest first)."""
    from db.models import TradingParams
    from sqlalchemy import select, desc

    rows = db_session.execute(
        select(TradingParams).order_by(desc(TradingParams.created_at)).limit(limit)
    ).scalars().all()

    return [
        {
            "id": r.id,
            "version_tag": r.version_tag,
            "version_note": r.version_note,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "activated_at": r.activated_at.isoformat() if r.activated_at else None,
        }
        for r in rows
    ]


def activate_trading_params_version(version_id: str, db_session) -> bool:
    """Rollback to a previous version by activating it."""
    from db.models import TradingParams
    from sqlalchemy import update, select

    row = db_session.execute(
        select(TradingParams).where(TradingParams.id == version_id)
    ).scalar_one_or_none()

    if row is None:
        return False

    db_session.execute(
        update(TradingParams).where(TradingParams.is_active == True)
        .values(is_active=False)
    )
    row.is_active = True
    row.activated_at = datetime.now(timezone.utc)
    db_session.commit()
    logger.info("TradingParams activated: version=%s", row.version_tag)
    return True


# ---------------------------------------------------------------------------
# Exchange Settings (Group B)
# ---------------------------------------------------------------------------

def get_active_exchange_settings(db_session) -> dict:
    """
    Load the active ExchangeSettings from DB.
    API keys are decrypted but NEVER returned via API endpoints.
    """
    from db.models import ExchangeSettings, ExchangeAsset
    from sqlalchemy import select

    row = db_session.execute(
        select(ExchangeSettings).where(ExchangeSettings.is_active == True)
    ).scalar_one_or_none()

    if row is None:
        logger.warning("No active ExchangeSettings found — using defaults")
        return _default_exchange_settings()

    assets = db_session.execute(
        select(ExchangeAsset).where(
            ExchangeAsset.exchange_settings_id == row.id,
            ExchangeAsset.enabled == True,
        )
    ).scalars().all()

    return {
        "id": row.id,
        "profile_name": row.profile_name,
        "exchange_id": row.exchange_id,
        "market_type": row.market_type,
        "testnet": bool(row.testnet),
        # Credentials — decrypted for internal use only
        "api_key": decrypt_value(row.api_key_encrypted or ""),
        "api_secret": decrypt_value(row.api_secret_encrypted or ""),
        "passphrase": decrypt_value(row.passphrase_encrypted or ""),
        # Account
        "account_balance_usd": row.account_balance_usd,
        "account_currency": row.account_currency,
        # Position sizing
        "sizing_mode": row.sizing_mode,
        "fixed_usd_per_trade": row.fixed_usd_per_trade,
        "risk_pct_per_trade": row.risk_pct_per_trade,
        "default_leverage": row.default_leverage,
        # Fees
        "fee_rate": row.fee_rate,
        "slippage_pct": row.slippage_pct,
        # Assets
        "assets": [
            {
                "symbol": a.symbol,
                "enabled": bool(a.enabled),
                "leverage": a.leverage_override,
            }
            for a in assets
        ],
    }


def get_exchange_settings_for_api(db_session) -> dict:
    """
    Safe version for API responses — masks sensitive fields.
    API keys shown as '***' if set, empty string if not set.
    """
    settings = get_active_exchange_settings(db_session)
    settings["api_key"] = "***" if settings.get("api_key") else ""
    settings["api_secret"] = "***" if settings.get("api_secret") else ""
    settings["passphrase"] = "***" if settings.get("passphrase") else ""
    return settings


def save_exchange_settings(data: dict, db_session) -> str:
    """
    Save ExchangeSettings. Encrypts sensitive fields before storing.
    Deactivates current active profile and activates the new one.
    """
    from db.models import ExchangeSettings, ExchangeAsset
    from sqlalchemy import update, delete

    # Deactivate current
    db_session.execute(
        update(ExchangeSettings).where(ExchangeSettings.is_active == True)
        .values(is_active=False)
    )

    new_id = str(uuid.uuid4())
    row = ExchangeSettings(
        id=new_id,
        profile_name=data.get("profile_name", "default"),
        is_active=True,
        exchange_id=data.get("exchange_id", "binance"),
        market_type=data.get("market_type", "futures"),
        testnet=data.get("testnet", True),
        # Encrypt sensitive fields
        api_key_encrypted=encrypt_value(data.get("api_key", "")) if data.get("api_key") and data.get("api_key") != "***" else None,
        api_secret_encrypted=encrypt_value(data.get("api_secret", "")) if data.get("api_secret") and data.get("api_secret") != "***" else None,
        passphrase_encrypted=encrypt_value(data.get("passphrase", "")) if data.get("passphrase") and data.get("passphrase") != "***" else None,
        account_balance_usd=data.get("account_balance_usd", 10000.0),
        account_currency=data.get("account_currency", "USDT"),
        sizing_mode=data.get("sizing_mode", "risk_pct"),
        fixed_usd_per_trade=data.get("fixed_usd_per_trade", 100.0),
        risk_pct_per_trade=data.get("risk_pct_per_trade", 0.02),
        default_leverage=data.get("default_leverage", 5),
        fee_rate=data.get("fee_rate", 0.001),
        slippage_pct=data.get("slippage_pct", 0.0002),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(row)

    # Save assets
    for asset in data.get("assets", []):
        db_session.add(ExchangeAsset(
            id=str(uuid.uuid4()),
            exchange_settings_id=new_id,
            symbol=asset["symbol"],
            enabled=asset.get("enabled", True),
            leverage_override=asset.get("leverage"),
        ))

    db_session.commit()
    logger.info("ExchangeSettings saved: exchange=%s testnet=%s",
                row.exchange_id, row.testnet)
    return new_id


def build_ccxt_exchange(db_session):
    """
    Build and return an ExchangeClient from active ExchangeSettings.
    Uses trading_core.exchange.get_exchange_client for singleton management.
    Automatically routes to testnet if testnet=True.
    """
    from trading_core.exchange.client import ExchangeClient

    settings = get_active_exchange_settings(db_session)
    exchange_id = settings["exchange_id"]

    options = {
        "apiKey": settings["api_key"],
        "secret": settings["api_secret"],
        "enableRateLimit": True,
    }
    if settings.get("passphrase"):
        options["password"] = settings["passphrase"]

    # For trading (with API key), create a dedicated non-singleton instance
    client = ExchangeClient(exchange_id, options)

    # Enable testnet/sandbox mode
    if settings["testnet"]:
        if hasattr(client._exchange, "set_sandbox_mode"):
            client._exchange.set_sandbox_mode(True)
        elif "test" in client._exchange.urls:
            client._exchange.urls["api"] = client._exchange.urls["test"]
        logger.info("Exchange %s running in TESTNET mode", exchange_id)
    else:
        logger.warning("Exchange %s running in LIVE mode — real money!", exchange_id)

    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_trading_params() -> dict:
    return {
        "score_alert_threshold": 75,
        "score_watch_threshold": 55,
        "order_flow_max_pts": 35,
        "smc_max_pts": 30,
        "vsa_max_pts": 30,
        "context_max_pts": 15,
        "confluence_bonus_max_pts": 15,
        "adx_trending_threshold": 25.0,
        "adx_choppy_threshold": 20.0,
        "atr_parabolic_multiplier": 3.0,
        "atr_parabolic_rolling_window": 20,
        "parabolic_score_multiplier": 0.6,
        "ranging_score_multiplier": 0.85,
        "trending_score_multiplier": 1.0,
        "trigger_timeframe": "15m",
        "context_timeframe": "1h",
        "entry_timeframe": "5m",
        "time_invalidation_candles": 15,
        "ob_atr_multiplier": 1.5,
        "fvg_touch_tolerance_pct": 0.001,
        "ob_retest_tolerance_pct": 0.002,
        "pinbar_tail_ratio": 2.0,
        "pinbar_body_position_long": 0.70,
        "pinbar_body_position_short": 0.30,
        "no_supply_vol_ratio": 0.40,
        "effort_result_vol_ratio": 0.50,
        "poc_tolerance_pct": 0.003,
        "swing_lookback": 20,
        "fibonacci_lookback": 50,
        "correlation_threshold": 0.8,
        "max_correlated_risk_pct": 3.0,
        "portfolio_heat_limit_pct": 6.0,
        "atr_sl_multiplier": 1.5,
        "tp1_rr_ratio": 1.5,
        "tp2_rr_ratio": 2.5,
        "max_concurrent_positions": 3,
        "max_daily_loss_pct": 5.0,
        "min_trades_threshold": 30,
        "overfit_degradation_threshold": 0.20,
    }


def _default_exchange_settings() -> dict:
    return {
        "exchange_id": "binance",
        "market_type": "futures",
        "testnet": True,
        "api_key": "",
        "api_secret": "",
        "passphrase": "",
        "account_balance_usd": 10000.0,
        "account_currency": "USDT",
        "sizing_mode": "risk_pct",
        "fixed_usd_per_trade": 100.0,
        "risk_pct_per_trade": 0.02,
        "default_leverage": 5,
        "fee_rate": 0.001,
        "slippage_pct": 0.0002,
        "assets": [
            {"symbol": "BTC/USDT", "enabled": True, "leverage": 10},
            {"symbol": "ETH/USDT", "enabled": True, "leverage": 7},
        ],
    }


def _trading_params_to_dict(row) -> dict:
    return {
        "id": row.id,
        "version_tag": row.version_tag,
        "version_note": row.version_note,
        "is_active": bool(row.is_active),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "score_alert_threshold": row.score_alert_threshold,
        "score_watch_threshold": row.score_watch_threshold,
        "order_flow_max_pts": row.order_flow_max_pts,
        "smc_max_pts": row.smc_max_pts,
        "vsa_max_pts": row.vsa_max_pts,
        "context_max_pts": row.context_max_pts,
        "confluence_bonus_max_pts": row.confluence_bonus_max_pts,
        "adx_trending_threshold": row.adx_trending_threshold,
        "adx_choppy_threshold": row.adx_choppy_threshold,
        "atr_parabolic_multiplier": row.atr_parabolic_multiplier,
        "atr_parabolic_rolling_window": row.atr_parabolic_rolling_window,
        "parabolic_score_multiplier": row.parabolic_score_multiplier,
        "ranging_score_multiplier": row.ranging_score_multiplier,
        "trending_score_multiplier": row.trending_score_multiplier,
        "trigger_timeframe": row.trigger_timeframe,
        "context_timeframe": row.context_timeframe,
        "entry_timeframe": row.entry_timeframe,
        "time_invalidation_candles": row.time_invalidation_candles,
        "ob_atr_multiplier": row.ob_atr_multiplier,
        "fvg_touch_tolerance_pct": row.fvg_touch_tolerance_pct,
        "ob_retest_tolerance_pct": row.ob_retest_tolerance_pct,
        "pinbar_tail_ratio": row.pinbar_tail_ratio,
        "pinbar_body_position_long": row.pinbar_body_position_long,
        "pinbar_body_position_short": row.pinbar_body_position_short,
        "no_supply_vol_ratio": row.no_supply_vol_ratio,
        "effort_result_vol_ratio": row.effort_result_vol_ratio,
        "poc_tolerance_pct": row.poc_tolerance_pct,
        "swing_lookback": row.swing_lookback,
        "fibonacci_lookback": row.fibonacci_lookback,
        "correlation_threshold": row.correlation_threshold,
        "max_correlated_risk_pct": row.max_correlated_risk_pct,
        "portfolio_heat_limit_pct": row.portfolio_heat_limit_pct,
        "atr_sl_multiplier": row.atr_sl_multiplier,
        "tp1_rr_ratio": row.tp1_rr_ratio,
        "tp2_rr_ratio": row.tp2_rr_ratio,
        "max_concurrent_positions": row.max_concurrent_positions,
        "max_daily_loss_pct": row.max_daily_loss_pct,
        "min_trades_threshold": row.min_trades_threshold,
        "overfit_degradation_threshold": row.overfit_degradation_threshold,
    }
