"""
ConnectionManager — WebSocket broadcast for positions + audit feed.
Handles disconnects gracefully.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections for two channels."""

    def __init__(self) -> None:
        self._position_connections: Set[WebSocket] = set()
        self._audit_connections: Set[WebSocket] = set()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect_positions(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._position_connections.add(websocket)
        logger.debug("WS positions: new connection (total=%d)", len(self._position_connections))

    async def connect_audit(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._audit_connections.add(websocket)
        logger.debug("WS audit: new connection (total=%d)", len(self._audit_connections))

    def disconnect_positions(self, websocket: WebSocket) -> None:
        self._position_connections.discard(websocket)
        logger.debug("WS positions: disconnected (total=%d)", len(self._position_connections))

    def disconnect_audit(self, websocket: WebSocket) -> None:
        self._audit_connections.discard(websocket)
        logger.debug("WS audit: disconnected (total=%d)", len(self._audit_connections))

    # ------------------------------------------------------------------
    # Broadcast
    # ------------------------------------------------------------------

    async def broadcast_positions(self, message: str) -> None:
        await self._broadcast(self._position_connections, message)

    async def broadcast_audit(self, message: str) -> None:
        await self._broadcast(self._audit_connections, message)

    async def _broadcast(self, connections: Set[WebSocket], message: str) -> None:
        dead: list[WebSocket] = []
        for ws in list(connections):
            try:
                await ws.send_text(message)
            except Exception as exc:
                logger.debug("WS send failed (will disconnect): %s", exc)
                dead.append(ws)
        for ws in dead:
            connections.discard(ws)

    @property
    def positions_count(self) -> int:
        return len(self._position_connections)

    @property
    def audit_count(self) -> int:
        return len(self._audit_connections)
