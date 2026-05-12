"""
Exchange API routes — delegate to MockExchange (server-side).
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_mock_exchange
from api.schemas import (
    AccountStateResponse, CreateOrderRequest, OrderResponse,
    PositionResponse, PriceResponse,
)
from trading_core.exchange.interface import OrderSide, OrderType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/exchange", tags=["exchange"])


def _order_to_response(order) -> OrderResponse:
    return OrderResponse(
        order_id=order.order_id,
        symbol=order.symbol,
        side=order.side.value,
        order_type=order.order_type.value,
        amount=order.amount,
        price=order.price,
        status=order.status.value,
        filled_amount=order.filled_amount,
        fill_price=order.fill_price,
        fee=order.fee,
        created_at=order.created_at.isoformat(),
        filled_at=order.filled_at.isoformat() if order.filled_at else None,
        client_order_id=order.client_order_id,
    )


def _position_to_response(pos, current_price: float = 0.0) -> PositionResponse:
    return PositionResponse(
        symbol=pos.symbol,
        direction=pos.direction,
        entry_price=pos.entry_price,
        amount=pos.amount,
        leverage=pos.leverage,
        stop_loss=pos.stop_loss,
        take_profit_1=pos.take_profit_1,
        take_profit_2=pos.take_profit_2,
        current_price=current_price,
        unrealized_pnl=round(pos.unrealized_pnl(current_price), 4),
        unrealized_pnl_pct=round(pos.unrealized_pnl_pct(current_price), 2),
        opened_at=pos.opened_at.isoformat(),
        signal_id=pos.signal_id,
    )


@router.post("/orders", response_model=OrderResponse)
async def create_order(
    req: CreateOrderRequest,
    exchange=Depends(get_mock_exchange),
):
    if exchange is None:
        raise HTTPException(status_code=503, detail="Exchange not initialized")
    try:
        side = OrderSide(req.side)
        order_type = OrderType(req.order_type)
        order = await exchange.create_order(
            symbol=req.symbol,
            side=side,
            order_type=order_type,
            amount=req.amount,
            price=req.price,
            client_order_id=req.client_order_id,
            metadata=req.metadata,
        )
        return _order_to_response(order)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("create_order failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/orders/{order_id}")
async def cancel_order(
    order_id: str,
    symbol: str = Query(...),
    exchange=Depends(get_mock_exchange),
):
    if exchange is None:
        raise HTTPException(status_code=503, detail="Exchange not initialized")
    result = await exchange.cancel_order(order_id, symbol)
    if not result:
        raise HTTPException(status_code=404, detail="Order not found or not cancellable")
    return {"cancelled": True, "order_id": order_id}


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    symbol: str = Query(...),
    exchange=Depends(get_mock_exchange),
):
    if exchange is None:
        raise HTTPException(status_code=503, detail="Exchange not initialized")
    order = await exchange.get_order(order_id, symbol)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_to_response(order)


@router.get("/orders", response_model=List[OrderResponse])
async def get_open_orders(
    symbol: Optional[str] = Query(None),
    exchange=Depends(get_mock_exchange),
):
    if exchange is None:
        raise HTTPException(status_code=503, detail="Exchange not initialized")
    orders = await exchange.get_open_orders(symbol)
    return [_order_to_response(o) for o in orders]


@router.get("/positions/{symbol}", response_model=Optional[PositionResponse])
async def get_position(
    symbol: str,
    exchange=Depends(get_mock_exchange),
):
    if exchange is None:
        raise HTTPException(status_code=503, detail="Exchange not initialized")
    pos = await exchange.get_position(symbol)
    if pos is None:
        return None
    price = await exchange.get_current_price(symbol)
    return _position_to_response(pos, price)


@router.get("/positions", response_model=List[PositionResponse])
async def get_all_positions(
    exchange=Depends(get_mock_exchange),
):
    if exchange is None:
        raise HTTPException(status_code=503, detail="Exchange not initialized")
    positions = await exchange.get_all_positions()
    result = []
    for pos in positions:
        price = await exchange.get_current_price(pos.symbol)
        result.append(_position_to_response(pos, price))
    return result


@router.get("/account", response_model=AccountStateResponse)
async def get_account(
    exchange=Depends(get_mock_exchange),
):
    if exchange is None:
        raise HTTPException(status_code=503, detail="Exchange not initialized")
    state = await exchange.get_account_state()
    return AccountStateResponse(**state.to_dict())


@router.get("/price/{symbol}", response_model=PriceResponse)
async def get_price(
    symbol: str,
    exchange=Depends(get_mock_exchange),
):
    if exchange is None:
        raise HTTPException(status_code=503, detail="Exchange not initialized")
    price = await exchange.get_current_price(symbol)
    return PriceResponse(symbol=symbol, price=price)
