"""Telegram Bot webhook endpoint — receives updates from the Telegram Bot API."""

import hashlib
import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.telegram import TelegramService
from app.db.session import get_db

router = APIRouter()
logger = logging.getLogger(__name__)
_tg = TelegramService()


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Receive Telegram Bot API update events.

    Validates the ``X-Telegram-Bot-Api-Secret-Token`` header against the
    configured ``TELEGRAM_BOT_TOKEN`` before processing any update.

    Handles:
    - ``/connect {token}`` — pair a Telegram user to their Releasewatch account
    - ``/start`` — send a help message
    - ``/status {issue_id}`` — quick issue status lookup
    """
    # Validate webhook secret (Telegram sends first 256 chars of bot token SHA256)
    expected = hmac.new(
        settings.TELEGRAM_BOT_TOKEN.encode(),
        b"",
        hashlib.sha256,
    ).hexdigest()[:256] if settings.TELEGRAM_BOT_TOKEN else None

    if expected and x_telegram_bot_api_secret_token != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret")

    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True}

    telegram_user_id: int = message["from"]["id"]
    text: str = message.get("text", "").strip()

    try:
        if text.startswith("/connect "):
            token = text[len("/connect "):].strip()
            await _tg.handle_connect_command(telegram_user_id, token, db)
        elif text.startswith("/status "):
            issue_id = text[len("/status "):].strip()
            await _tg.handle_status_command(telegram_user_id, issue_id, db)
        elif text.startswith("/start"):
            await _tg.send_raw(
                telegram_user_id,
                "👋 *Releasewatch Bot*\n\n"
                "• `/connect <token>` — link your account (get token from Settings)\n"
                "• `/status BUG-042` — quick issue lookup",
            )
    except Exception:
        logger.exception("Error handling Telegram update %s", update.get("update_id"))

    return {"ok": True}
