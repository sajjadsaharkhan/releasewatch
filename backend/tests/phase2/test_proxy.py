"""Outgoing proxy (Settings → Configuration): Jev goes through it when enabled,
and the Test button probes a URL through the form's proxy."""

import httpx
import pytest

from app.config import settings
from app.core import proxy
from app.search import jev_settings

PROXY = "http://proxy.internal:8084"
JEV_URL = "https://api.typesafe.ai"


def cfg(**overrides) -> dict:
    return {"enabled": True, "http": PROXY, "https": PROXY, "no_proxy": "", **overrides}


# ── resolve ───────────────────────────────────────────────────────────────────


def test_resolve_off_or_empty_goes_direct():
    assert proxy.resolve(None, JEV_URL) is None
    assert proxy.resolve(cfg(enabled=False), JEV_URL) is None
    assert proxy.resolve(cfg(http="", https=""), JEV_URL) is None


def test_resolve_picks_by_scheme_and_falls_back_to_the_other():
    both = cfg(http="http://a:1", https="http://b:2")
    assert proxy.resolve(both, "https://x.com") == "http://b:2"
    assert proxy.resolve(both, "http://x.com") == "http://a:1"
    assert proxy.resolve(cfg(https=""), "https://x.com") == PROXY
    assert proxy.resolve(cfg(http=""), "http://x.com") == PROXY


@pytest.mark.parametrize(
    ("no_proxy", "bypassed"),
    [
        ("api.typesafe.ai", True),
        (".typesafe.ai", True),
        ("typesafe.ai", True),
        ("localhost, .typesafe.ai", True),
        ("*", True),
        ("notypesafe.ai", False),
        ("other.com", False),
        ("", False),
    ],
)
def test_resolve_honours_no_proxy(no_proxy, bypassed):
    assert (proxy.resolve(cfg(no_proxy=no_proxy), JEV_URL) is None) is bypassed


def test_mask_hides_the_password_only():
    assert proxy.mask("http://u:secret@p:8080") == "http://u:***@p:8080"
    assert proxy.mask(PROXY) == PROXY


def form(**overrides) -> dict:
    value = cfg(**overrides)
    return {"enabled": value["enabled"], "http": value["http"], "https": value["https"],
            "noProxy": value["no_proxy"]}


# ── Jev uses it ───────────────────────────────────────────────────────────────


async def save_proxy(admin, **overrides):
    resp = await admin.put("/settings/configuration", json={"proxy": form(**overrides)})
    assert resp.status_code == 200, resp.text


async def test_jev_client_uses_the_enabled_proxy(factories, db_session, monkeypatch):
    admin = factories.admin_client
    monkeypatch.setattr(settings, "JEV_BASE_URL", JEV_URL)
    saved = await admin.put("/settings/search/jev", json={"api_key": "tsk-proxy-test-1234"})
    assert saved.status_code == 200
    assert (await admin.post("/settings/search/jev/test")).json()["ok"]
    assert (await admin.put("/settings/search/jev", json={"enabled": True})).status_code == 200

    assert (await jev_settings.client(db_session)).proxy_url is None

    await save_proxy(admin)
    assert (await jev_settings.client(db_session)).proxy_url == PROXY

    await save_proxy(admin, no_proxy="api.typesafe.ai")
    assert (await jev_settings.client(db_session)).proxy_url is None

    await save_proxy(admin, enabled=False)
    assert (await jev_settings.client(db_session)).proxy_url is None


# ── Test button ───────────────────────────────────────────────────────────────


@pytest.fixture
def upstream(monkeypatch):
    """The probe's transport: ``upstream.answer`` is a status code or an exception."""

    class Upstream(httpx.AsyncBaseTransport):
        answer: int | Exception = 403
        urls: list[str] = []

        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            self.urls.append(str(request.url))
            if isinstance(self.answer, Exception):
                raise self.answer
            return httpx.Response(self.answer, request=request)

    fake = Upstream()
    fake.urls = []
    monkeypatch.setattr(proxy, "transport_override", fake)
    return fake


async def test_proxy_test_any_http_answer_is_ok(factories, upstream):
    resp = await factories.admin_client.post(
        "/settings/configuration/proxy/test",
        json={"url": f"{JEV_URL}/v1/systemone", "proxy": form()},
    )
    body = resp.json()
    assert resp.status_code == 200, resp.text
    assert body["ok"] is True and body["status_code"] == 403 and body["reason"] is None
    assert body["proxy"] == PROXY
    assert upstream.urls == [f"{JEV_URL}/v1/systemone"]


async def test_proxy_test_reports_why_it_failed(factories, upstream):
    admin = factories.admin_client
    for error, reason in [
        (httpx.ProxyError("refused"), "proxy_error"),
        (httpx.ReadTimeout("slow"), "timeout"),
        (httpx.ConnectError("down"), "network"),
    ]:
        upstream.answer = error
        body = (
            await admin.post(
                "/settings/configuration/proxy/test", json={"url": JEV_URL, "proxy": form()}
            )
        ).json()
        assert body["ok"] is False and body["reason"] == reason and body["status_code"] is None


async def test_proxy_test_needs_an_enabled_proxy_that_applies(factories, upstream):
    admin = factories.admin_client
    off = (
        await admin.post(
            "/settings/configuration/proxy/test",
            json={"url": JEV_URL, "proxy": form(enabled=False)},
        )
    ).json()
    assert off["ok"] is False and off["reason"] == "proxy_disabled"

    bypass = (
        await admin.post(
            "/settings/configuration/proxy/test",
            json={"url": JEV_URL, "proxy": form(no_proxy=".typesafe.ai")},
        )
    ).json()
    assert bypass["ok"] is False and bypass["reason"] == "no_proxy_for_url"
    assert upstream.urls == []  # neither went out


async def test_proxy_test_rejects_non_http_urls(factories, upstream):
    for url in ["api.typesafe.ai", "ftp://x.com", "file:///etc/passwd"]:
        resp = await factories.admin_client.post(
            "/settings/configuration/proxy/test", json={"url": url, "proxy": form()}
        )
        assert resp.status_code == 422, url


async def test_proxy_test_is_admin_only(factories, client_for, upstream):
    qa = await client_for(await factories.user(role="qa"))
    resp = await qa.post(
        "/settings/configuration/proxy/test", json={"url": JEV_URL, "proxy": form()}
    )
    assert resp.status_code == 403
    assert upstream.urls == []
