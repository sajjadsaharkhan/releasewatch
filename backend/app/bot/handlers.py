"""Telegram bot command handlers.

Each handler receives the incoming ``telegram.Message`` object and an active
``AsyncSession``.  Handlers reply directly to the chat via ``bot.send_message``.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot, Message
from telegram.constants import ParseMode

from app.db.models.telegram_integration import TelegramIntegration
from app.db.models.user import User
from app.db.models.issue import Issue

logger = logging.getLogger(__name__)


async def dispatch(message: Message, bot: Bot, db: AsyncSession) -> None:
    """Route an incoming message to the appropriate command handler."""
    text = (message.text or "").strip()
    chat_id = message.chat_id

    if text.startswith("/start"):
        await _handle_start(chat_id, bot)
    elif text.startswith("/integration"):
        parts = text.split(maxsplit=1)
        token = parts[1].strip() if len(parts) > 1 else ""
        await _handle_integration(message, bot, db, token)
    elif text.startswith("/status"):
        parts = text.split(maxsplit=1)
        issue_ref = parts[1].strip() if len(parts) > 1 else ""
        await _handle_status(chat_id, bot, db, issue_ref, message.from_user.id)
    elif text.startswith("/disconnect"):
        await _handle_disconnect(chat_id, bot, db, message.from_user.id)
    else:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                "Unknown command. Available commands:\n"
                "• /integration <token> — link your Releasewatch account\n"
                "• /status <issue\\-number> — check issue status\n"
                "• /disconnect — unlink your account"
            ),
            parse_mode=ParseMode.MARKDOWN_V2,
        )


async def _handle_start(chat_id: int, bot: Bot) -> None:
    await bot.send_message(
        chat_id=chat_id,
        text=(
            "👋 *Releasewatch Bot*\n\n"
            "I deliver issue notifications to your team\\.\n\n"
            "*Commands:*\n"
            "• `/integration <token>` — link your account \\(get token from your Profile page\\)\n"
            "• `/status <issue\\-number>` — quick issue lookup\n"
            "• `/disconnect` — unlink your Telegram account"
        ),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def _handle_integration(
    message: Message,
    bot: Bot,
    db: AsyncSession,
    token: str,
) -> None:
    """Link the sender's Telegram account to a Releasewatch user via a one-time token."""
    chat_id = message.chat_id
    tg_user = message.from_user

    if not token:
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Usage: `/integration <token>`\n\nGet your token from your Profile → Telegram tab\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    now = datetime.now(tz=timezone.utc)

    # Look up user by connect_token
    result = await db.execute(
        select(User).where(
            User.connect_token == token,
            User.connect_token_expires > now,
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Invalid or expired token\\. Generate a new one from your Profile → Telegram tab\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Check if this Telegram account is already linked to a different user
    existing = await db.execute(
        select(TelegramIntegration).where(
            TelegramIntegration.telegram_user_id == tg_user.id
        )
    )
    existing_integration = existing.scalar_one_or_none()
    if existing_integration and existing_integration.user_id != user.id:
        await bot.send_message(
            chat_id=chat_id,
            text="❌ This Telegram account is already linked to another Releasewatch user\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Build full name
    full_name_parts = [tg_user.first_name or "", tg_user.last_name or ""]
    full_name = " ".join(p for p in full_name_parts if p).strip() or None

    if existing_integration:
        # Re-linking same user — update existing row
        existing_integration.chat_id = chat_id
        existing_integration.telegram_username = tg_user.username
        existing_integration.telegram_full_name = full_name
        existing_integration.telegram_first_name = tg_user.first_name
        existing_integration.telegram_last_name = tg_user.last_name
        existing_integration.is_active = True
    else:
        integration = TelegramIntegration(
            user_id=user.id,
            telegram_user_id=tg_user.id,
            chat_id=chat_id,
            telegram_username=tg_user.username,
            telegram_full_name=full_name,
            telegram_first_name=tg_user.first_name,
            telegram_last_name=tg_user.last_name,
        )
        db.add(integration)

    # Clear the one-time token
    user.connect_token = None
    user.connect_token_expires = None
    await db.commit()

    handle_display = f"@{tg_user.username}" if tg_user.username else full_name or "your account"
    await bot.send_message(
        chat_id=chat_id,
        text=(
            f"✅ *Linked\\!*\n\n"
            f"Your Telegram account has been connected to *{_escape(user.name)}* on Releasewatch\\.\n"
            f"You'll receive notifications here as {_escape(handle_display)}\\."
        ),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    logger.info("Telegram linked: user_id=%s tg_user_id=%s", user.id, tg_user.id)


async def _handle_status(
    chat_id: int,
    bot: Bot,
    db: AsyncSession,
    issue_ref: str,
    tg_user_id: int,
) -> None:
    """Return the current status of an issue (requires a linked account)."""
    # Verify the sender is linked
    result = await db.execute(
        select(TelegramIntegration).where(
            TelegramIntegration.telegram_user_id == tg_user_id,
            TelegramIntegration.is_active.is_(True),
        )
    )
    integration = result.scalar_one_or_none()
    if integration is None:
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Your Telegram account is not linked\\. Use `/integration <token>` to connect\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if not issue_ref:
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Usage: `/status <issue\\-number>`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Support "42" or "ISSUE-42" or "issue-42" formats
    number_str = issue_ref.upper().removeprefix("ISSUE-").removeprefix("BUG-")
    if not number_str.isdigit():
        await bot.send_message(
            chat_id=chat_id,
            text=f"❌ Could not parse issue number from `{_escape(issue_ref)}`\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    res = await db.execute(
        select(Issue).where(Issue.issue_number == int(number_str))
    )
    issue = res.scalar_one_or_none()
    if issue is None:
        await bot.send_message(
            chat_id=chat_id,
            text=f"❌ Issue `{_escape(issue_ref)}` not found\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    regression_flag = "Yes" if issue.is_regression else "No"
    await bot.send_message(
        chat_id=chat_id,
        text=(
            f"📋 *Issue \\#{issue.issue_number}*\n"
            f"{_escape(issue.title)}\n\n"
            f"Status: `{_escape(str(issue.status))}` \\| Severity: `{_escape(str(issue.severity))}`\n"
            f"Regression: {regression_flag}"
        ),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def _handle_disconnect(
    chat_id: int,
    bot: Bot,
    db: AsyncSession,
    tg_user_id: int,
) -> None:
    """Unlink the sender's Telegram account from Releasewatch."""
    result = await db.execute(
        select(TelegramIntegration).where(
            TelegramIntegration.telegram_user_id == tg_user_id
        )
    )
    integration = result.scalar_one_or_none()
    if integration is None:
        await bot.send_message(
            chat_id=chat_id,
            text="ℹ️ Your Telegram account is not currently linked to any Releasewatch account\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    await db.delete(integration)
    await db.commit()

    await bot.send_message(
        chat_id=chat_id,
        text="✅ Your Telegram account has been unlinked from Releasewatch\\. You will no longer receive notifications here\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    logger.info("Telegram unlinked: tg_user_id=%s", tg_user_id)


def _escape(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in text)
