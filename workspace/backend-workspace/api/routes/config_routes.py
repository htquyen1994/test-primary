"""
Config Management API Routes
==============================
Group A — Trading Parameters: versioned, DB-stored, hot-reloadable.
Group B — Exchange Settings: encrypted credentials, assets, position sizing.

Endpoints:
  GET  /api/config/trading              — active trading params
  PUT  /api/config/trading              — save new version
  GET  /api/config/trading/history      — version history
  POST /api/config/trading/{id}/activate — rollback to version
  GET  /api/config/exchange             — active exchange settings (keys masked)
  PUT  /api/config/exchange             — save exchange settings
  GET  /api/config/exchanges            — list supported exchanges
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import require_api_key
from db.connection import get_session
from config.config_service import (
    get_active_trading_params,
    save_trading_params,
    get_trading_params_history,
    activate_trading_params_version,
    get_exchange_settings_for_api,
    save_exchange_settings,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["config"])

# ---------------------------------------------------------------------------
# Supported exchanges (ccxt)
# ---------------------------------------------------------------------------

SUPPORTED_EXCHANGES = [
    {"id": "binance",  "name": "Binance",  "futures": True,  "spot": True,  "testnet": True},
    {"id": "bybit",    "name": "Bybit",    "futures": True,  "spot": True,  "testnet": True},
    {"id": "gate",     "name": "Gate.io",  "futures": True,  "spot": True,  "testnet": False},
    {"id": "bingx",    "name": "BingX",    "futures": True,  "spot": True,  "testnet": False},
    {"id": "okx",      "name": "OKX",      "futures": True,  "spot": True,  "testnet": True,  "needs_passphrase": True},
    {"id": "bitget",   "name": "Bitget",   "futures": True,  "spot": True,  "testnet": False, "needs_passphrase": True},
    {"id": "mexc",     "name": "MEXC",     "futures": True,  "spot": True,  "testnet": False},
    {"id": "kucoin",   "name": "KuCoin",   "futures": True,  "spot": True,  "testnet": False, "needs_passphrase": True},
]

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TradingParamsSaveRequest(BaseModel):
    version_tag: str = Field(..., description="e.g. 'v1.1-aggressive'")
    version_note: Optional[str] = Field(None, description="Why this version was created")
    # Scoring
    score_alert_threshold: int = Field(75, ge=50, le=100)
    score_watch_threshold: int = Field(55, ge=30, le=90)
    # Regime
    adx_trending_threshold: float = Field(25.0, gt=0)
    adx_choppy_threshold: float = Field(20.0, gt=0)
    atr_parabolic_multiplier: float = Field(3.0, gt=1.0)
    parabolic_score_multiplier: float = Field(0.6, gt=0, le=1.0)
    ranging_score_multiplier: float = Field(0.85, gt=0, le=1.0)
    trending_score_multiplier: float = Field(1.0, gt=0, le=1.0)
    # Timeframes
    trigger_timeframe: str = Field("15m")
    context_timeframe: str = Field("1h")
    time_invalidation_candles: int = Field(15, ge=5, le=50)
    # Strategy
    ob_atr_multiplier: float = Field(1.5, gt=0)
    pinbar_tail_ratio: float = Field(2.0, gt=1.0)
    # SL/TP — user-configurable; ScoringService reads these from DB
    atr_sl_multiplier: float = Field(1.5, gt=0, description="SL = ATR x this multiplier")
    tp1_rr_ratio: float = Field(2.0, gt=1.0, description="TP1 gross R:R (e.g. 2.0 = 2x SL)")
    tp2_rr_ratio: float = Field(3.0, gt=1.0, description="TP2 gross R:R (e.g. 3.0 = 3x SL)")
    min_net_rr: float = Field(1.5, gt=0, description="ALERT suppressed when net R:R < this")
    # Risk
    correlation_threshold: float = Field(0.8, gt=0, le=1.0)
    max_correlated_risk_pct: float = Field(3.0, gt=0)
    portfolio_heat_limit_pct: float = Field(6.0, gt=0)
    max_concurrent_positions: int = Field(3, ge=1, le=10)
    max_daily_loss_pct: float = Field(5.0, gt=0)


class AssetConfig(BaseModel):
    symbol: str
    enabled: bool = True
    leverage: Optional[int] = Field(None, ge=1, le=125)


class ExchangeSettingsSaveRequest(BaseModel):
    profile_name: str = Field("default")
    exchange_id: str = Field("binance", description="ccxt exchange id")
    market_type: str = Field("futures", pattern="^(futures|spot)$")
    testnet: bool = Field(True, description="MUST be true for paper trading")
    # Credentials — send empty string to keep existing, "***" to keep existing
    api_key: str = Field("", description="Leave empty or '***' to keep existing")
    api_secret: str = Field("", description="Leave empty or '***' to keep existing")
    passphrase: str = Field("", description="Required by OKX, Bitget, KuCoin")
    # Account
    account_balance_usd: float = Field(10000.0, gt=0)
    account_currency: str = Field("USDT")
    # Position sizing
    sizing_mode: str = Field("risk_pct", pattern="^(fixed_usd|risk_pct|kelly)$")
    fixed_usd_per_trade: float = Field(100.0, gt=0, description="USD per trade when mode=fixed_usd")
    risk_pct_per_trade: float = Field(0.02, gt=0, le=0.1, description="2% = 0.02")
    default_leverage: int = Field(5, ge=1, le=125)
    fee_rate: float = Field(0.001, gt=0)
    slippage_pct: float = Field(0.0002, ge=0)
    assets: List[AssetConfig] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Routes — Trading Parameters (Group A)
# ---------------------------------------------------------------------------

@router.get("/trading")
def get_trading_params(db: Session = Depends(get_session)):
    """Get active trading parameters."""
    return get_active_trading_params(db)


@router.put("/trading")
def update_trading_params(
    body: TradingParamsSaveRequest,
    db: Session = Depends(get_session),
    _: None = Depends(require_api_key),
):
    """
    Save a new version of trading parameters.
    The new version becomes active immediately.
    Old version is kept in history for rollback.
    """
    params = body.model_dump()
    version_tag = params.pop("version_tag")
    version_note = params.pop("version_note", None)

    new_id = save_trading_params(params, version_tag, version_note or "", db)
    return {"status": "saved", "version_id": new_id, "version_tag": version_tag}


@router.get("/trading/history")
def get_params_history(limit: int = 20, db: Session = Depends(get_session)):
    """Get version history of trading parameters."""
    return get_trading_params_history(db, limit=limit)


@router.post("/trading/{version_id}/activate")
def activate_params_version(version_id: str, db: Session = Depends(get_session), _: None = Depends(require_api_key)):
    """Rollback to a previous version of trading parameters."""
    success = activate_trading_params_version(version_id, db)
    if not success:
        raise HTTPException(status_code=404, detail=f"Version {version_id} not found")
    return {"status": "activated", "version_id": version_id}


# ---------------------------------------------------------------------------
# Routes — Exchange Settings (Group B)
# ---------------------------------------------------------------------------

@router.get("/exchange")
def get_exchange_settings(db: Session = Depends(get_session)):
    """
    Get active exchange settings.
    API keys are masked as '***' in the response.
    """
    return get_exchange_settings_for_api(db)


@router.put("/exchange")
def update_exchange_settings(
    body: ExchangeSettingsSaveRequest,
    db: Session = Depends(get_session),
    _: None = Depends(require_api_key),
):
    """
    Save exchange settings.
    - API keys are encrypted before storage.
    - Send '***' or empty string to keep existing credentials.
    - testnet=true is the safe default — set false only for live trading.
    """
    data = body.model_dump()
    new_id = save_exchange_settings(data, db)
    return {
        "status": "saved",
        "settings_id": new_id,
        "exchange": body.exchange_id,
        "testnet": body.testnet,
        "warning": "Set testnet=false only after thorough testing on testnet." if not body.testnet else None,
    }


@router.get("/exchanges")
def list_supported_exchanges():
    """List all supported exchanges with their capabilities."""
    return {"exchanges": SUPPORTED_EXCHANGES}


@router.get("/exchange/test-connection")
def test_exchange_connection(db: Session = Depends(get_session)):
    """
    Test the current exchange connection.
    Returns exchange info if successful.
    """
    try:
        from config.config_service import build_ccxt_exchange
        exchange = build_ccxt_exchange(db)
        markets = exchange.load_markets()
        return {
            "status": "connected",
            "exchange": exchange.id,
            "testnet": exchange.sandbox if hasattr(exchange, "sandbox") else "unknown",
            "markets_count": len(markets),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Connection failed: {str(exc)}"
        )
