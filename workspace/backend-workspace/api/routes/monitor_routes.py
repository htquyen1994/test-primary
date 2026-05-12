"""
Monitor Routes — Proxy to mock-exchange-workspace + pending orders.

Exposes exchange/audit data from mock-exchange-workspace (port 8001)
through backend-workspace (port 8000) so the frontend only talks to one origin.

All proxy routes forward to MOCK_EXCHANGE_URL env var (default: http://localhost:8001).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response

logger = logging.getLogger(__name__)

router = APIRouter()

# Base URL for mock-exchange-workspace
MOCK_EXCHANGE_URL = os.environ.get("MOCK_EXCHANGE_URL", "http://localhost:8001")

_http = httpx.AsyncClient(timeout=10.0, base_url=MOCK_EXCHANGE_URL)


async def _proxy_get(path: str, params: dict | None = None) -> dict | list:
    """Forward a GET request to mock-exchange-workspace."""
    try:
        r = await _http.get(path, params=params or {})
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"mock-exchange-workspace unreachable: {e}",
        )


async def _proxy_delete(path: str, params: dict | None = None) -> dict:
    try:
        r = await _http.delete(path, params=params or {})
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"mock-exchange-workspace unreachable: {e}")


# ---------------------------------------------------------------------------
# Exchange — positions
# ---------------------------------------------------------------------------

@router.get("/api/exchange/positions")
async def get_all_positions():
    """All open positions with real-time unrealized PnL from mock exchange."""
    return await _proxy_get("/exchange/positions")


@router.get("/api/exchange/positions/{symbol}")
async def get_position(symbol: str):
    """Single position for a symbol."""
    return await _proxy_get(f"/exchange/positions/{symbol}")


# ---------------------------------------------------------------------------
# Exchange — orders
# ---------------------------------------------------------------------------

@router.get("/api/exchange/orders")
async def get_open_orders(symbol: Optional[str] = Query(None)):
    """Open orders (PENDING, OPEN) on the exchange."""
    params = {"symbol": symbol} if symbol else {}
    return await _proxy_get("/exchange/orders", params)


@router.get("/api/exchange/orders/{order_id}")
async def get_order(order_id: str, symbol: str = Query(...)):
    return await _proxy_get(f"/exchange/orders/{order_id}", {"symbol": symbol})


@router.delete("/api/exchange/orders/{order_id}")
async def cancel_order(order_id: str, symbol: str = Query(...)):
    """Cancel a pending/open order."""
    return await _proxy_delete(f"/exchange/orders/{order_id}", {"symbol": symbol})


# ---------------------------------------------------------------------------
# Exchange — account
# ---------------------------------------------------------------------------

@router.get("/api/exchange/account")
async def get_account():
    """Account balance, equity, used margin, total realized PnL."""
    return await _proxy_get("/exchange/account")


# ---------------------------------------------------------------------------
# Pending orders — in-flight Celery trade executions
# ---------------------------------------------------------------------------

@router.get("/api/orders/pending")
async def get_pending_orders():
    """
    List all signals currently being executed (Celery task in-flight).
    Reads Redis keys trade:status:* and returns entries with status != Filled/Failed.
    Merged with exchange PENDING/OPEN orders for a unified view.
    """
    from trading_core.cache import get_redis
    r = get_redis()

    # 1. In-flight Celery executions from Redis trade:status:*
    pending_executions = []
    try:
        for key in r.scan_iter("trade:status:*"):
            raw = r.get(key)
            if raw:
                data = json.loads(raw)
                status = data.get("status", "")
                if status not in ("Filled", "Failed", "Rejected"):
                    pending_executions.append(data)
    except Exception as exc:
        logger.warning("Redis scan for pending orders failed: %s", exc)

    # 2. Exchange PENDING/OPEN orders (SL, TP waiting to fill)
    exchange_orders: list = []
    try:
        all_orders = await _proxy_get("/exchange/orders")
        exchange_orders = [
            o for o in (all_orders if isinstance(all_orders, list) else [])
            if o.get("status") in ("PENDING", "OPEN")
        ]
    except HTTPException:
        pass  # mock-exchange unavailable — return what we have

    return {
        "executions": pending_executions,
        "exchange_orders": exchange_orders,
    }


# ---------------------------------------------------------------------------
# Audit — signals
# ---------------------------------------------------------------------------

@router.get("/api/audit/signals")
async def list_audit_signals(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    symbol: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
    regime: Optional[str] = Query(None),
    from_ts: Optional[str] = Query(None, alias="from"),
    to_ts: Optional[str] = Query(None, alias="to"),
):
    """
    Paginated signal audit log.
    result: SIGNAL | NO_SIGNAL
    regime: TRENDING | RANGING | PARABOLIC | CHOPPY
    """
    params = {k: v for k, v in {
        "page": page, "limit": limit,
        "symbol": symbol, "result": result, "regime": regime,
        "from": from_ts, "to": to_ts,
    }.items() if v is not None}
    return await _proxy_get("/audit/signals", params)


@router.get("/api/audit/signals/{signal_id}")
async def get_audit_signal(signal_id: int):
    """Full signal audit detail including post-hoc price outcome."""
    return await _proxy_get(f"/audit/signals/{signal_id}")


# ---------------------------------------------------------------------------
# Audit — trades
# ---------------------------------------------------------------------------

@router.get("/api/audit/trades")
async def list_audit_trades(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    outcome: Optional[str] = Query(None),
    verdict: Optional[str] = Query(None),
):
    """
    Paginated trade audit log.
    outcome: WIN | LOSS | BREAKEVEN
    verdict: GOOD_SIGNAL | BAD_SIGNAL | ACCEPTABLE
    """
    params = {k: v for k, v in {
        "page": page, "limit": limit,
        "outcome": outcome, "verdict": verdict,
    }.items() if v is not None}
    return await _proxy_get("/audit/trades", params)


@router.get("/api/audit/trades/{trade_id}")
async def get_audit_trade(trade_id: int):
    """Full trade audit detail with entry/exit prices, PnL, SL hit reason."""
    return await _proxy_get(f"/audit/trades/{trade_id}")


# ---------------------------------------------------------------------------
# Audit — analytics
# ---------------------------------------------------------------------------

@router.get("/api/audit/analytics/performance")
async def get_audit_performance():
    """Aggregate performance report from audit engine."""
    return await _proxy_get("/audit/analytics/performance")


@router.get("/api/audit/analytics/tuning")
async def get_audit_tuning():
    """Tuning recommendations from audit analysis engine."""
    return await _proxy_get("/audit/analytics/tuning")
