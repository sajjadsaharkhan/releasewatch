"""Outgoing HTTP proxy: ``system_settings`` category ``proxy``, key ``config``
(``{enabled, http, https, no_proxy}``), edited in Settings → Configuration.

``resolve`` turns the setting into the proxy URL for one target URL (or None for
"go direct"); ``for_url`` reads the setting first. ``probe`` is the Settings →
Test button: one GET through the proxy, reporting what came back.
"""

import time
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.system_setting import SystemSetting

PROBE_TIMEOUT = 10.0

#: Test seam: tests replace the transport so a probe never leaves the process.
transport_override: httpx.AsyncBaseTransport | None = None


def mask(url: str) -> str:
    """Hide the password in a proxy URL so it is safe to return to the frontend."""
    try:
        parsed = urlparse(url)
        if parsed.password:
            host = f"{parsed.hostname}:{parsed.port}" if parsed.port else (parsed.hostname or "")
            netloc = f"{parsed.username}:***@{host}" if parsed.username else f"***@{host}"
            return urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        pass
    return url


def _bypassed(host: str, no_proxy: str) -> bool:
    for entry in (e.strip().lower() for e in (no_proxy or "").split(",")):
        if not entry:
            continue
        if entry == "*":
            return True
        entry = entry.lstrip(".")
        if host == entry or host.endswith("." + entry):
            return True
    return False


def resolve(value: dict | None, target_url: str) -> str | None:
    """The proxy to use for ``target_url``, or None: disabled, no URL set for
    its scheme, or the host is in ``no_proxy``. A scheme without its own proxy
    URL falls back to the other one."""
    if not value or not value.get("enabled"):
        return None
    target = urlparse(target_url)
    if _bypassed((target.hostname or "").lower(), value.get("no_proxy") or ""):
        return None
    http, https = value.get("http") or "", value.get("https") or ""
    url = (https or http) if target.scheme == "https" else (http or https)
    return url.strip() or None


async def load(db: AsyncSession) -> dict | None:
    row = (
        await db.execute(
            select(SystemSetting).where(
                SystemSetting.category == "proxy",
                SystemSetting.key == "config",
                SystemSetting.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    return row.value if row else None


async def for_url(db: AsyncSession, target_url: str) -> str | None:
    return resolve(await load(db), target_url)


@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    #: Any HTTP answer counts (a 401/403/405 still proves the route works).
    status_code: int | None = None
    #: ``proxy_error``, ``timeout``, ``invalid_url``, ``network``.
    reason: str | None = None
    latency_ms: int = 0


async def probe(target_url: str, proxy_url: str) -> ProbeResult:
    start = time.perf_counter()

    def ms() -> int:
        return round((time.perf_counter() - start) * 1000)

    try:
        async with httpx.AsyncClient(
            timeout=PROBE_TIMEOUT,
            follow_redirects=False,
            transport=transport_override,
            proxy=None if transport_override else proxy_url,
        ) as client:
            resp = await client.get(target_url)
    except httpx.ProxyError:
        return ProbeResult(False, reason="proxy_error", latency_ms=ms())
    except httpx.TimeoutException:
        return ProbeResult(False, reason="timeout", latency_ms=ms())
    except (httpx.InvalidURL, httpx.UnsupportedProtocol):
        return ProbeResult(False, reason="invalid_url", latency_ms=ms())
    except httpx.HTTPError:
        return ProbeResult(False, reason="network", latency_ms=ms())
    return ProbeResult(True, status_code=resp.status_code, latency_ms=ms())
