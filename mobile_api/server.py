"""
mobile_api/server.py — FastAPI server for the JARVIS mobile companion.

Runs as an asyncio task alongside the main JARVIS loop.
Exposes:
  REST   GET  /api/jobs                  list recent jobs
  REST   GET  /api/jobs/{id}             single job
  REST   DELETE /api/jobs/{id}           cancel a job
  REST   GET  /api/reminders            list pending reminders
  REST   POST /api/reminders            create reminder
  REST   GET  /api/calendar             upcoming events
  REST   POST /api/command              publish voice.command to event bus
  REST   GET  /api/status               JARVIS health check
  WS     /ws                            real-time event stream
"""

import logging
import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mobile_api.routes import jobs, reminders, calendar_routes, command
from mobile_api.ws import router as ws_router

logger = logging.getLogger(__name__)

API_HOST: str = os.getenv("JARVIS_API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("JARVIS_API_PORT", "8765"))
API_KEY: str = os.getenv("JARVIS_API_KEY", "")  # empty = no auth (LAN-only default)

app = FastAPI(
    title="JARVIS Mobile API",
    version="1.0.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router,            prefix="/api/jobs",      tags=["jobs"])
app.include_router(reminders.router,       prefix="/api/reminders", tags=["reminders"])
app.include_router(calendar_routes.router, prefix="/api/calendar",  tags=["calendar"])
app.include_router(command.router,         prefix="/api",           tags=["command"])
app.include_router(ws_router,                                       tags=["websocket"])


@app.get("/api/status")
async def status():
    return {"status": "online", "service": "JARVIS v2.0"}


async def run_server() -> None:
    """Start uvicorn inside the existing asyncio event loop."""
    logger.info("JARVIS Mobile API starting on %s:%d", API_HOST, API_PORT)
    config = uvicorn.Config(
        app,
        host=API_HOST,
        port=API_PORT,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    await server.serve()
