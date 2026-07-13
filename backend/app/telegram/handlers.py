"""Telegram bot command handlers.

Each handler receives a raw ``message`` dict from the Telegram Bot API and a
``TelegramClient`` instance.  Handlers reply directly to the chat.

Message dict shape (relevant fields):
    {
        "message_id": int,
        "from": {"id": int, "username": str, "first_name": str, "last_name": str},
        "chat": {"id": int},
        "text": str,
    }
"""

import logging
from datetime import datetime, timezone
from html import escape as html_escape
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.telegram_integration import TelegramIntegration
from app.db.models.user import User
from app.db.models.issue import Issue
from app.telegram.client import TelegramClient

logger = logging.getLogger(__name__)


async def dispatch(message: dict[str, Any], client: TelegramClient, db: AsyncSession) -> None:
    """Route an incoming message to the appropriate command handler."""
    text = (message.get("text") or "").strip()
    chat_id: int = message["chat"]["id"]

    if text.startswith("/start"):
        await _handle_start(chat_id, client)
    elif text.startswith("/integration"):
        parts = text.split(maxsplit=1)
        token = parts[1].strip() if len(parts) > 1 else ""
        await _handle_integration(message, client, db, token)
    elif text.startswith("/status"):
        parts = text.split(maxsplit=1)
        issue_ref = parts[1].strip() if len(parts) > 1 else ""
        tg_user_id: int = message["from"]["id"]
        await _handle_status(chat_id, client, db, issue_ref, tg_user_id)
    elif text.startswith("/disconnect"):
        tg_user_id = message["from"]["id"]
        await _handle_disconnect(chat_id, client, db, tg_user_id)
    else:
        await client.send_message(
            chat_id=chat_id,
            text=(
                "Unknown command. Available commands:\n"
                "• /integration &lt;token&gt; — link your Releasewatch account\n"
                "• /status &lt;issue-number&gt; — check issue status\n"
                "• /disconnect — unlink your account"
            ),
            parse_mode="HTML",
        )


async def _handle_start(chat_id: int, client: TelegramClient) -> None:
    await client.send_message(
        chat_id=chat_id,
        text=(
            "<b>👋 Releasewatch Bot</b>\n\n"
            "I deliver issue notifications to your team.\n\n"
            "<b>Commands:</b>\n"
            "• <code>/integration &lt;token&gt;</code> — link your account (get token from your Profile page)\n"
            "• <code>/status &lt;issue-number&gt;</code> — quick issue lookup\n"
            "• <code>/disconnect</code> — unlink your Telegram account"
        ),
        parse_mode="HTML",
    )


async def _handle_integration(
    message: dict[str, Any],
    client: TelegramClient,
    db: AsyncSession,
    token: str,
) -> None:
    chat_id: int = message["chat"]["id"]
    tg_user: dict[str, Any] = message.get("from") or {}

    if not token:
        await client.send_message(
            chat_id=chat_id,
            text="❌ Usage: <code>/integration &lt;token&gt;</code>\n\nGet your token from your Profile → Telegram tab.",
            parse_mode="HTML",
        )
        return

    now = datetime.now(tz=timezone.utc)

    result = await db.execute(
        select(User).where(
            User.connect_token == token,
            User.connect_token_expires > now,
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        await client.send_message(
            chat_id=chat_id,
            text="❌ Invalid or expired token. Generate a new one from your Profile → Telegram tab.",
            parse_mode="HTML",
        )
        return

    tg_user_id: int = tg_user["id"]
    existing = await db.execute(
        select(TelegramIntegration).where(TelegramIntegration.telegram_user_id == tg_user_id)
    )
    existing_integration = existing.scalar_one_or_none()
    if existing_integration and existing_integration.user_id != user.id:
        await client.send_message(
            chat_id=chat_id,
            text="❌ This Telegram account is already linked to another Releasewatch user.",
            parse_mode="HTML",
        )
        return

    first_name = tg_user.get("first_name") or ""
    last_name = tg_user.get("last_name") or ""
    full_name = " ".join(p for p in [first_name, last_name] if p).strip() or None
    username = tg_user.get("username")

    if existing_integration:
        existing_integration.chat_id = chat_id
        existing_integration.telegram_username = username
        existing_integration.telegram_full_name = full_name
        existing_integration.telegram_first_name = first_name or None
        existing_integration.telegram_last_name = last_name or None
        existing_integration.is_active = True
    else:
        db.add(
            TelegramIntegration(
                user_id=user.id,
                telegram_user_id=tg_user_id,
                chat_id=chat_id,
                telegram_username=username,
                telegram_full_name=full_name,
                telegram_first_name=first_name or None,
                telegram_last_name=last_name or None,
            )
        )

    user.connect_token = None
    user.connect_token_expires = None
    await db.commit()

    handle_display = f"@{username}" if username else full_name or "your account"
    await client.send_message(
        chat_id=chat_id,
        text=(
            f"✅ <b>Linked!</b>\n\n"
            f"Your Telegram account has been connected to <b>{html_escape(user.name)}</b> on Releasewatch.\n"
            f"You'll receive notifications here as {html_escape(handle_display)}."
        ),
        parse_mode="HTML",
    )
    logger.info("Telegram linked: user_id=%s tg_user_id=%s", user.id, tg_user_id)


async def _handle_status(
    chat_id: int,
    client: TelegramClient,
    db: AsyncSession,
    issue_ref: str,
    tg_user_id: int,
) -> None:
    result = await db.execute(
        select(TelegramIntegration).where(
            TelegramIntegration.telegram_user_id == tg_user_id,
            TelegramIntegration.is_active.is_(True),
        )
    )
    if result.scalar_one_or_none() is None:
        await client.send_message(
            chat_id=chat_id,
            text="❌ Your Telegram account is not linked. Use <code>/integration &lt;token&gt;</code> to connect.",
            parse_mode="HTML",
        )
        return

    if not issue_ref:
        await client.send_message(
            chat_id=chat_id,
            text="❌ Usage: <code>/status &lt;issue-number&gt;</code>",
            parse_mode="HTML",
        )
        return

    number_str = issue_ref.upper().removeprefix("ISSUE-").removeprefix("BUG-")
    if not number_str.isdigit():
        await client.send_message(
            chat_id=chat_id,
            text=f"❌ Could not parse issue number from <code>{html_escape(issue_ref)}</code>.",
            parse_mode="HTML",
        )
        return

    res = await db.execute(
        select(Issue)
        .where(Issue.issue_number == int(number_str))
        .options(selectinload(Issue.project), selectinload(Issue.release))
    )
    issue = res.scalar_one_or_none()
    if issue is None:
        await client.send_message(
            chat_id=chat_id,
            text=f"❌ Issue <code>{html_escape(issue_ref)}</code> not found.",
            parse_mode="HTML",
        )
        return

    project_name = html_escape(issue.project.name) if issue.project else "—"
    release_version = html_escape(issue.release.version) if issue.release else "—"
    blocker_line = "\n🚨 <b>Release blocker</b>" if issue.is_release_blocker else ""
    regression_line = (
        f"\n🔁 Regression · appeared {issue.regression_count}×" if issue.is_regression else ""
    )

    await client.send_message(
        chat_id=chat_id,
        text=(
            f"📋 <b>Issue #{issue.issue_number} — {html_escape(issue.title)}</b>\n"
            f"📦 <b>{project_name}</b> · <code>{release_version}</code>\n"
            f"\n"
            f"Status: <code>{html_escape(str(issue.status))}</code> · "
            f"Severity: <code>{html_escape(str(issue.severity))}</code>"
            f"{blocker_line}"
            f"{regression_line}"
        ),
        parse_mode="HTML",
    )


async def _handle_disconnect(
    chat_id: int,
    client: TelegramClient,
    db: AsyncSession,
    tg_user_id: int,
) -> None:
    result = await db.execute(
        select(TelegramIntegration).where(TelegramIntegration.telegram_user_id == tg_user_id)
    )
    integration = result.scalar_one_or_none()
    if integration is None:
        await client.send_message(
            chat_id=chat_id,
            text="ℹ️ Your Telegram account is not currently linked to any Releasewatch account.",
            parse_mode="HTML",
        )
        return

    await db.delete(integration)
    await db.commit()

    await client.send_message(
        chat_id=chat_id,
        text="✅ Your Telegram account has been unlinked from Releasewatch. You will no longer receive notifications here.",
        parse_mode="HTML",
    )
    logger.info("Telegram unlinked: tg_user_id=%s", tg_user_id)
