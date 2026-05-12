"""
WebSocket routes.
  WS /ws/positions   — real-time position price + unrealized PnL
  WS /ws/audit-feed  — real-time signal/trade events
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.deps import get_ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/positions")
async def ws_positions(websocket: WebSocket):
    manager = get_ws_manager()
    if manager is None:
        await websocket.close(code=1011)
        return
    await manager.connect_positions(websocket)
    try:
        # Keep connection open; TickerFeed broadcasts to this manager
        while True:
            # Receive any client pings; ignore content
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Echo back as keepalive
                await websocket.send_text('{"type":"pong"}')
            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_text('{"type":"ping"}')
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("WS positions closed: %s", exc)
    finally:
        manager.disconnect_positions(websocket)


@router.websocket("/ws/audit-feed")
async def ws_audit_feed(websocket: WebSocket):
    manager = get_ws_manager()
    if manager is None:
        await websocket.close(code=1011)
        return
    await manager.connect_audit(websocket)
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                await websocket.send_text('{"type":"pong"}')
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text('{"type":"ping"}')
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("WS audit-feed closed: %s", exc)
    finally:
        manager.disconnect_audit(websocket)
