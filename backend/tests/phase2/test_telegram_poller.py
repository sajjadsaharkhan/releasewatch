"""Telegram poller self-healing: a client that keeps failing on the network is
rebuilt, and polling resumes from the same offset (2026-10-12 incident — the
poller timed out for ~44 h on a wedged connection pool until a restart)."""

import asyncio

import httpx
import pytest

from app.telegram import poller


class FakeClient:
    """``wedged`` clients time out on every poll; healthy ones return one
    update, then stop the loop on the next poll."""

    instances: list["FakeClient"] = []
    wedged_count = 1

    def __init__(self, token: str, proxy_url: str | None = None) -> None:
        self.wedged = len(FakeClient.instances) < FakeClient.wedged_count
        self.offsets: list[int | None] = []
        self.closed = False
        FakeClient.instances.append(self)

    async def get_updates(self, offset=None, timeout=30):
        self.offsets.append(offset)
        if self.wedged:
            if len(self.offsets) > 10:  # never rebuilt: end the loop so the test fails, not hangs
                raise asyncio.CancelledError
            raise httpx.PoolTimeout("")
        if len(self.offsets) > 1:
            raise asyncio.CancelledError
        return [{"update_id": 41}]

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_poller(monkeypatch: pytest.MonkeyPatch):
    FakeClient.instances = []
    FakeClient.wedged_count = 1

    async def token():
        return "123:abc"

    async def no_proxy():
        return None

    async def granted():
        return True

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(poller, "TelegramClient", FakeClient)
    monkeypatch.setattr(poller, "load_bot_token", token)
    monkeypatch.setattr(poller, "load_proxy_url", no_proxy)
    monkeypatch.setattr(poller, "_try_acquire_lock", granted)
    monkeypatch.setattr(poller, "_refresh_lock", noop)
    monkeypatch.setattr(poller, "_release_lock", noop)
    monkeypatch.setattr(poller.asyncio, "sleep", noop)
    return FakeClient


async def test_a_wedged_client_is_rebuilt_after_repeated_network_errors(fake_poller):
    await poller.start_polling()

    wedged, fresh = fake_poller.instances
    assert len(wedged.offsets) == poller._MAX_NETWORK_ERRORS
    assert wedged.closed
    # The new client picks up where polling stopped, then keeps going.
    assert fresh.offsets == [None, 42]


async def test_a_client_that_stays_wedged_is_rebuilt_again(fake_poller):
    fake_poller.wedged_count = 2

    await poller.start_polling()

    first, second, third = fake_poller.instances
    assert first.closed and second.closed
    assert len(second.offsets) == poller._MAX_NETWORK_ERRORS
    assert third.offsets == [None, 42]
