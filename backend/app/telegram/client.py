"""Raw httpx-based Telegram Bot API client.

Deliberately avoids python-telegram-bot so we have direct control over the
proxy transport and connection parameters.  Supports HTTP, HTTPS, and SOCKS5
proxies (httpx[socks] must be installed for SOCKS).
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TELEGRAM_BASE = "https://api.telegram.org"


class TelegramAPIError(Exception):
    """Raised when the Telegram API returns ok=false."""


class TelegramClient:
    """Minimal async Telegram Bot API client backed by httpx.

    Parameters
    ----------
    token:
        Bot token from @BotFather.
    proxy_url:
        Optional proxy URL.  Supports ``http://``, ``https://``, and
        ``socks5://`` schemes.  Passed directly to httpx's transport layer.
    """

    def __init__(self, token: str, proxy_url: str | None = None) -> None:
        self._base = f"{_TELEGRAM_BASE}/bot{token}"
        timeout = httpx.Timeout(connect=10.0, read=35.0, write=10.0, pool=5.0)
        if proxy_url:
            transport = httpx.AsyncHTTPTransport(proxy=proxy_url)
            self._http = httpx.AsyncClient(transport=transport, timeout=timeout)
        else:
            self._http = httpx.AsyncClient(timeout=timeout)

    async def get_updates(
        self,
        offset: int | None = None,
        timeout: int = 30,
        allowed_updates: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": allowed_updates or ["message"],
        }
        if offset is not None:
            payload["offset"] = offset
        r = await self._http.post(f"{self._base}/getUpdates", json=payload)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise TelegramAPIError(f"getUpdates failed: {data.get('description')}")
        return data["result"]

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
    ) -> None:
        r = await self._http.post(
            f"{self._base}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise TelegramAPIError(f"sendMessage failed: {data.get('description')}")

    async def close(self) -> None:
        await self._http.aclose()
