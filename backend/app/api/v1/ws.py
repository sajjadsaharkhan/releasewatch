"""WebSocket endpoints — live dashboard events, inbox push, and upload progress."""

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


@router.websocket("/upload")
async def ws_upload_progress(
    websocket: WebSocket,
    token: str | None = Query(None),
):
    """Bidirectional upload progress tracking.

    Clients can:
    1. Subscribe to progress updates for a specific upload_id
    2. Send progress updates when uploading directly to S3

    Message format (client -> server):
    {
        "action": "subscribe" | "update",
        "upload_id": "uuid",
        "progress": 0-100,  // only for "update"
        "bytes_uploaded": 12345,  // only for "update"
        "total_bytes": 50000  // only for "update"
    }

    Message format (server -> client):
    {
        "upload_id": "uuid",
        "progress": 0-100,
        "bytes_uploaded": 12345,
        "total_bytes": 50000,
        "status": "uploading" | "completed" | "failed"
    }

    Redis channel: ``rw:upload:{user_id}``

    Auth: pass JWT as ``?token=<access_token>``.
    """
    user_id = await _authenticate_ws(token)
    if not user_id:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    channel = f"rw:upload:{user_id}"
    redis = await get_redis_raw()
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    # Track active subscriptions
    active_uploads: dict[str, dict] = {}

    async def _listen_to_redis():
        """Listen for progress updates from other clients/servers."""
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"].decode())
                    upload_id = data.get("upload_id")
                    if upload_id in active_uploads:
                        await websocket.send_json(data)
                        # Update local state
                        active_uploads[upload_id] = data
        except Exception as exc:
            logger.warning("ws_upload redis listener error: %s", exc)

    async def _listen_to_client():
        """Listen for messages from the WebSocket client."""
        try:
            while True:
                data = await websocket.receive_json()
                action = data.get("action")

                if action == "subscribe":
                    # Client wants to track a specific upload
                    upload_id = data.get("upload_id")
                    if upload_id:
                        active_uploads[upload_id] = {"upload_id": upload_id, "progress": 0}

                elif action == "update":
                    # Client is uploading and reporting progress
                    upload_id = data.get("upload_id")
                    if upload_id:
                        progress_data = {
                            "upload_id": upload_id,
                            "progress": data.get("progress", 0),
                            "bytes_uploaded": data.get("bytes_uploaded", 0),
                            "total_bytes": data.get("total_bytes", 0),
                            "status": data.get("status", "uploading"),
                        }
                        active_uploads[upload_id] = progress_data
                        # Broadcast to Redis for other tabs/clients
                        await redis.publish(channel, json.dumps(progress_data))

        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.warning("ws_upload client listener error: %s", exc)

    try:
        # Run both listeners concurrently
        await asyncio.gather(
            _listen_to_redis(),
            _listen_to_client(),
        )
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ws_upload error for user %s: %s", user_id, exc)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
