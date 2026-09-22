"""Small factory helpers — create fixtures through the API wherever an endpoint exists.

Every helper returns a ``SimpleNamespace`` built from the API's JSON response,
so tests exercise the same paths a real client would and can still write
``project.id`` / ``issue.title`` instead of dict subscripting.
"""

import secrets
from types import SimpleNamespace

from httpx import AsyncClient


class Factories:
    def __init__(self, admin_client: AsyncClient):
        self.admin_client = admin_client

    async def user(
        self,
        *,
        role: str = "qa",
        name: str | None = None,
        username: str | None = None,
    ) -> SimpleNamespace:
        suffix = secrets.token_hex(4)
        payload = {
            "name": name or f"Test User {suffix}",
            "username": username or f"user-{suffix}",
            "role": role,
            "temporary_password": "test-password-123",
        }
        resp = await self.admin_client.post("/team/invite", json=payload)
        resp.raise_for_status()
        return SimpleNamespace(**resp.json())

    async def project(self, *, triage_lead_id: int | None = None, **overrides) -> SimpleNamespace:
        suffix = secrets.token_hex(4)
        payload = {
            "name": f"Test Project {suffix}",
            "slug": f"test-project-{suffix}",
            **overrides,
        }
        if triage_lead_id is not None:
            payload["triage_lead_id"] = triage_lead_id
        resp = await self.admin_client.post("/projects", json=payload)
        resp.raise_for_status()
        return SimpleNamespace(**resp.json())

    async def release(self, *, project_id: int, **overrides) -> SimpleNamespace:
        suffix = secrets.token_hex(4)
        payload = {"project_id": project_id, "version": f"0.0.{suffix}", **overrides}
        resp = await self.admin_client.post("/releases", json=payload)
        resp.raise_for_status()
        return SimpleNamespace(**resp.json())

    async def issue(
        self,
        *,
        release_id: int | None = None,
        project_id: int | None = None,
        client: AsyncClient | None = None,
        **overrides,
    ) -> SimpleNamespace:
        """File an issue. ``project_id`` defaults to the release's project
        when a ``release_id`` is given and ``project_id`` isn't (slice 03 —
        ``project_id`` is now required, independent of ``release_id``)."""
        if project_id is None:
            if release_id is not None:
                release_resp = await self.admin_client.get(f"/releases/{release_id}")
                release_resp.raise_for_status()
                project_id = release_resp.json()["project_id"]
            else:
                project_id = (await self.project()).id
        payload = {
            "title": f"Test issue {secrets.token_hex(4)}",
            "release_id": release_id,
            "project_id": project_id,
            **overrides,
        }
        resp = await (client or self.admin_client).post("/issues", json=payload)
        resp.raise_for_status()
        return SimpleNamespace(**resp.json())
