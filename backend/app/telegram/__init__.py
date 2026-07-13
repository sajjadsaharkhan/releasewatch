"""Telegram integration — standalone bot module.

All Telegram concerns live here:
- ``client``    raw httpx-based Bot API client (no third-party Telegram library)
- ``config``    DB-backed token / proxy loader
- ``templates`` notification message templates
- ``sender``    notification delivery (used by Celery tasks)
- ``handlers``  bot command handlers
- ``poller``    long-poll loop (runs as a standalone process via run_bot.py)

Other services enqueue notifications through Celery tasks; the bot process is
completely decoupled from the API server.
"""
