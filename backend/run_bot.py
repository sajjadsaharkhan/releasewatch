"""Standalone Telegram bot process.

Runs two co-located processes:
  1. Celery worker — handles the ``notifications`` queue (sends Telegram messages)
  2. Poller         — long-polls Telegram for incoming commands

Both are started together and torn down together on SIGTERM / SIGINT.
All Telegram I/O lives here; the main worker never touches the Bot API.

Run with:  python run_bot.py
Docker:    command: python run_bot.py
"""

import asyncio
import logging
import signal
import subprocess
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def _start_notification_worker() -> subprocess.Popen:
    """Spawn a Celery worker that only handles the notifications queue."""
    proc = subprocess.Popen(
        [
            "celery", "-A", "app.tasks.celery_app", "worker",
            "--loglevel=info",
            "--concurrency=2",
            "-Q", "notifications",
            "--hostname", "bot-notifications@%h",
        ],
        # Inherit stdout/stderr so logs appear in `docker compose logs bot`
        stdout=None,
        stderr=None,
    )
    logger.info("Notification worker started (pid=%s)", proc.pid)
    return proc


async def main() -> None:
    from app.db.session import init_engine, close_engine
    from app.core.redis_client import init_redis, close_redis
    from app.telegram.poller import start_polling

    await init_engine()
    await init_redis()

    notification_worker = _start_notification_worker()

    # Drain any notifications that accumulated while the bot was offline.
    # Small delay lets the notification worker finish its own startup first.
    await asyncio.sleep(5)
    try:
        from app.tasks.notifications import flush_telegram_notifications
        flush_telegram_notifications.apply_async(queue="notifications")
        logger.info("Startup flush enqueued — retrying any pending inbox notifications")
    except Exception as exc:
        logger.warning("Could not enqueue startup flush: %s", exc)

    logger.info("Bot process ready — starting Telegram poller")
    loop = asyncio.get_running_loop()
    poll_task = asyncio.create_task(start_polling(), name="telegram-bot-poller")

    def _shutdown(sig: signal.Signals) -> None:
        logger.info("Received %s — shutting down bot process", sig.name)
        poll_task.cancel()
        notification_worker.terminate()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown, sig)

    try:
        await poll_task
    except asyncio.CancelledError:
        pass
    finally:
        notification_worker.wait()
        await close_redis()
        await close_engine()
        logger.info("Bot process stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
