"""
connection_manager.py
----------------------
Tracks currently-connected WebSocket clients and broadcasts messages to
all of them. Kept separate from api.py so it's testable on its own and
so api.py doesn't need to know HOW broadcasting works, just that it can
call manager.broadcast(text).

If one client's connection has gone bad (closed without us noticing yet),
broadcasting to it will raise — we catch that per-client so one dead
connection can't stop the message reaching everyone else.
"""

from __future__ import annotations

import logging
from fastapi import WebSocket

logger = logging.getLogger("connection_manager")


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("Client connected. Total connections: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("Client disconnected. Total connections: %d", len(self.active_connections))

    async def broadcast(self, message: str) -> None:
        """Send `message` to every connected client. Drops any dead connections it finds."""
        dead: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                logger.warning("Failed to send to a client — marking it dead")
                dead.append(connection)

        for connection in dead:
            self.disconnect(connection)

    def connection_count(self) -> int:
        return len(self.active_connections)
