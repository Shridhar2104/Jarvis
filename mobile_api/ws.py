"""
mobile_api/ws.py — WebSocket endpoint for real-time JARVIS event streaming.

Clients connect to ws://<host>:8765/ws and receive JSON events as they
flow through the internal event bus:

  { "topic": "job.completed", "payload": { ... } }
  { "topic": "job.created",   "payload": { ... } }
  { "topic": "reminder.triggered", "payload": { ... } }
  { "topic": "focus.changed", "payload": { ... } }

Multiple clients are supported simultaneously.
"""

import asyncio
import json
import logging
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from events.bus import bus, Event

logger = logging.getLogger(__name__)
router = APIRouter()

# Topics broadcast to mobile clients
BROADCAST_TOPICS = {
    "job.created",
    "job.completed",
    "job.blocked",
    "job.failed",
    "reminder.triggered",
    "focus.changed",
    "routine.detected",
}

_clients: Set[WebSocket] = set()
_subscribed = False


def _ensure_subscribed() -> None:
    """Wire up bus subscriptions once at import time."""
    global _subscribed
    if _subscribed:
        return
    for topic in BROADCAST_TOPICS:
        bus.on(topic, _make_handler(topic))
    _subscribed = True


def _make_handler(topic: str):
    async def handler(event: Event) -> None:
        if not _clients:
            return
        message = json.dumps({"topic": event.topic, "payload": event.payload})
        dead = set()
        for ws in list(_clients):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        _clients.difference_update(dead)
    return handler


_ensure_subscribed()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _clients.add(ws)
    logger.info("Mobile WS client connected (%d total)", len(_clients))
    try:
        # Send a connection confirmation
        await ws.send_text(json.dumps({"topic": "connected", "payload": {"clients": len(_clients)}}))
        # Keep connection alive — client can send pings
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=30)
                if data == "ping":
                    await ws.send_text(json.dumps({"topic": "pong", "payload": {}}))
            except asyncio.TimeoutError:
                # Send keepalive
                await ws.send_text(json.dumps({"topic": "heartbeat", "payload": {}}))
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WS error")
    finally:
        _clients.discard(ws)
        logger.info("Mobile WS client disconnected (%d remaining)", len(_clients))
