"""
api.py
------
FastAPI layer on top of everything built in Days 1-4.

Key idea: the polling loop (fetch -> detect -> publish) is UNCHANGED from
main.py. It runs in a background thread here instead of the foreground,
and gets one extra event-bus subscriber: broadcast_ball, which pushes
each new ball out to every connected WebSocket client. Printing and DB
persistence keep working exactly as before, completely independently.

Run with:
    uvicorn api:app --reload --port 8000

Endpoints:
    GET  /                          -> health check
    GET  /matches                   -> list of match_ids we have history for
    GET  /matches/{match_id}/history -> full ball-by-ball log for a match
    WS   /ws/{match_id}             -> live ball-by-ball updates (JSON per ball)

Try the WebSocket without writing any frontend code yet: open
test_client.html (included) in a browser.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import config
import db
from cricket_api import CricketAPIClient, CricketAPIError, NoLiveMatchError
from models import Ball, Match
from ball_detector import BallDetector
from event_bus import EventBus
from connection_manager import ConnectionManager

logger = logging.getLogger("api")

NEW_BALL_EVENT = "new_ball"

bus = EventBus()
manager = ConnectionManager()
main_event_loop: Optional[asyncio.AbstractEventLoop] = None


# --------------------------------------------------------------------------- #
# Subscribers (same pattern as Day 4's main.py — this is the payoff of the
# event bus: adding "broadcast over websocket" required zero changes to the
# polling/detection code, only a new subscriber function).
# --------------------------------------------------------------------------- #
def persist_ball(match_id: str, ball: Ball) -> None:
    db.save_ball(match_id, ball)


def ball_to_dict(match_id: str, ball: Ball) -> dict:
    return {
        "match_id": match_id,
        "team": ball.team,
        "over": ball.over,
        "runs_scored": ball.runs_scored,
        "wickets_added": ball.wickets_added,
        "total_runs": ball.total_runs,
        "total_wickets": ball.total_wickets,
        "event_type": ball.event_type.value,
        "summary": ball.summary(),
        "timestamp": ball.timestamp.isoformat(),
    }


def broadcast_ball(match_id: str, ball: Ball) -> None:
    """
    Called from the background polling THREAD, not the asyncio event loop.
    manager.broadcast() is a coroutine and must run on the event loop, so
    we hand it off with run_coroutine_threadsafe rather than calling it
    directly (that would raise — you can't await from a plain thread).
    """
    if main_event_loop is None:
        return
    message = json.dumps(ball_to_dict(match_id, ball))
    asyncio.run_coroutine_threadsafe(manager.broadcast(message), main_event_loop)


def resolve_match_id(client: CricketAPIClient) -> str:
    if config.MATCH_ID:
        return config.MATCH_ID
    return client.find_live_match_id()


# --------------------------------------------------------------------------- #
# Background polling loop — identical logic to main.py's run_loop, now
# living in a daemon thread so it doesn't block the FastAPI server.
# --------------------------------------------------------------------------- #
def polling_worker() -> None:
    db.init_db()
    client = CricketAPIClient()
    detector = BallDetector()
    match_id: Optional[str] = None
    previous_state: Optional[Match] = None

    while True:
        try:
            if match_id is None:
                match_id = resolve_match_id(client)
                db.ensure_match(match_id)
                previous_state = db.get_last_match_state(match_id)
                logger.info("Polling worker tracking match_id=%s", match_id)

            payload = client.get_match_info(match_id)
            current_state = Match.from_payload(match_id, payload)

            events = detector.detect(previous_state, current_state)
            for ball in events:
                bus.publish(NEW_BALL_EVENT, match_id, ball)

            previous_state = current_state

        except NoLiveMatchError:
            logger.info("No live match right now. Retrying in %ss...", config.POLL_INTERVAL_SECONDS)
            match_id = None
        except CricketAPIError as exc:
            logger.error("API error: %s. Will retry.", exc)
        except Exception:
            logger.exception("Unexpected error in polling worker — continuing")

        time.sleep(config.POLL_INTERVAL_SECONDS)


# --------------------------------------------------------------------------- #
# FastAPI app
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_event_loop
    main_event_loop = asyncio.get_event_loop()

    bus.subscribe(NEW_BALL_EVENT, persist_ball)
    bus.subscribe(NEW_BALL_EVENT, broadcast_ball)

    thread = threading.Thread(target=polling_worker, daemon=True)
    thread.start()
    logger.info("Background polling thread started.")

    yield  # app runs

    logger.info("Shutting down.")


app = FastAPI(title="IPL Live Score API", lifespan=lifespan)

# Permissive CORS for local development so test_client.html / a future
# frontend on a different port can connect. Tighten this before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    return {
        "status": "ok",
        "active_websocket_connections": manager.connection_count(),
    }


@app.get("/matches")
def list_matches() -> list[str]:
    return db.list_known_matches()


@app.get("/matches/{match_id}/history")
def match_history(match_id: str) -> list[dict]:
    balls = db.get_ball_history(match_id)
    return [ball_to_dict(match_id, b) for b in balls]


@app.websocket("/ws/{match_id}")
async def websocket_endpoint(websocket: WebSocket, match_id: str) -> None:
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect clients to send anything, but we need to
            # await something to detect disconnects promptly.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
