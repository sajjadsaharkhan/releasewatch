"""WebSocket endpoints — live dashboard events and per-user inbox push."""

import asyncio
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.config import settings
from app.core.auth import verify_token
from app.core.redis_client import get_redis_raw

router = APIRouter()
logger = logging.getLogger(__name__)


async def _authenticate_ws(token: str | None) -> str | None:
    """Validate JWT from query param. Returns user_id string or None on failure."""
    if not token:
        return None
    try:
        payload = verify_token(token)
        return payload.get("sub")
    except Exception:
        return None


@router.websocket("/dashboard")
async def ws_dashboard(
    websocket: WebSocket,
    token: str | None = Query(None),
):
    """Live dashboard feed: new issues, status changes, blocker flags (all projects).

    Redis channel: ``rw:dashboard``

    Auth: pass JWT as ``?token=<access_token>``.
    """
    user_id = await _authenticate_ws(token)
    if not user_id:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    redis = await get_redis_raw()
    pubsub = redis.pubsub()
    await pubsub.subscribe("rw:dashboard")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"].decode())
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ws_dashboard error for user %s: %s", user_id, exc)
    finally:
        await pubsub.unsubscribe("rw:dashboard")
        await pubsub.close()


@router.websocket("/inbox")
async def ws_inbox(
    websocket: WebSocket,
    token: str | None = Query(None),
):
    """Live inbox push — new inbox items for the authenticated user.

    Redis channel: ``rw:inbox:{user_id}``

    Auth: pass JWT as ``?token=<access_token>``.
    """
    user_id = await _authenticate_ws(token)
    if not user_id:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    channel = f"rw:inbox:{user_id}"
    redis = await get_redis_raw()
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"].decode())
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ws_inbox error for user %s: %s", user_id, exc)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
