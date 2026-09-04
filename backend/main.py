"""15-AI — JARVIS office backend entrypoint.

Run:  uvicorn main:app --reload
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.core.events.bus import bus
from app.core.runtime import lifecycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("main")

# ---- Socket.IO (async) -----------------------------------------------------
sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode="asgi")


@sio.event
async def connect(sid, environ):  # noqa: ANN001
    log.info("office UI connected: %s", sid)
    await sio.emit("office_event", {"event": "SystemEvent", "data": {"type": "client_connected", "sid": sid}})


@sio.event
async def disconnect(sid):  # noqa: ANN001
    log.info("office UI disconnected: %s", sid)


# ---- lifespan ---------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await lifecycle.startup()
    bus.attach_socketio(sio.emit)
    log.info("✅ 15-AI office is OPEN — JARVIS + 14 agents online")
    yield
    await lifecycle.shutdown()
    log.info("🔒 office closed")


api = FastAPI(title="15-AI — JARVIS Office", version="1.0.0", lifespan=lifespan)
api.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- routes ---------------------------------------------------------------
from app.api import agents, analytics, chat, memory, system, tasks  # noqa: E402

api.include_router(chat.router)
api.include_router(agents.router)
api.include_router(tasks.router)
api.include_router(memory.router)
api.include_router(analytics.router)
api.include_router(system.router)


@api.get("/")
async def root() -> dict:
    return {"service": "15-AI office", "jarvis": "online", "docs": "/docs"}


# ---- ASGI app (FastAPI + Socket.IO) ------------------------------------
app = socketio.ASGIApp(sio, other_asgi_app=api, socketio_path="socket.io")
