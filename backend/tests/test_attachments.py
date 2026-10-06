"""Attachment presign on issues without a release.

Backlog and tech-debt items are filed with ``release_id = NULL``. The presign
endpoints used to fetch the release unconditionally, so every upload on such
an issue died with ``NoResultFound`` → 500 (bug-344: seven failed presigns on
issue 335 while release-scoped issues uploaded fine). Signing itself is local
crypto against real credentials, so the s3 service is recorded, not called.
"""

from typing import Any

import pytest

from app.core.s3 import s3_service


@pytest.fixture
def presign_recorder(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Capture generate_presigned_upload kwargs; return a plausible result."""
    calls: list[dict[str, Any]] = []

    def fake_generate(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "upload_url": "https://s3.example/upload",
            "fields": {"key": "attachments/chat/no-release/344/abc/file.mp4"},
            "s3_key": "attachments/chat/no-release/344/abc/file.mp4",
            "file_id": "abc",
            "public_url": "https://cdn.example/file.mp4",
        }

    monkeypatch.setattr(s3_service, "generate_presigned_upload", fake_generate)
    return calls


@pytest.mark.asyncio
async def test_presign_works_on_issue_without_release(
    factories, client_for, presign_recorder
):
    """Backlog/tech-debt item (release_id NULL) presigns instead of 500ing."""
    project = await factories.project()
    issue = await factories.issue(project_id=project.id, release_id=None)

    admin = factories.admin_client
    resp = await admin.post(
        f"/issues/{issue.id}/attachments/presign",
        json={"filename": "error.mp4", "mime_type": "video/mp4"},
    )
    assert resp.status_code == 200
    assert resp.json()["s3_key"]
    assert presign_recorder[0]["release_version"] is None


def test_s3_key_uses_no_release_segment_when_release_missing():
    """build_key falls back to a no-release segment for a None version."""
    s3_key, _ = s3_service.build_key(
        "attachment",
        filename="error.mp4",
        project_slug="chat",
        release_version=None,
        issue_number=344,
    )
    assert s3_key.startswith("attachments/chat/no-release/344/")


@pytest.mark.asyncio
async def test_presign_still_passes_release_version_when_present(
    factories, presign_recorder
):
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    issue = await factories.issue(release_id=release.id)

    admin = factories.admin_client
    resp = await admin.post(
        f"/issues/{issue.id}/attachments/presign",
        json={"filename": "shot.png", "mime_type": "image/png"},
    )
    assert resp.status_code == 200
    assert presign_recorder[0]["release_version"] == release.version


@pytest.mark.asyncio
async def test_multipart_start_works_on_issue_without_release(
    factories, monkeypatch: pytest.MonkeyPatch
):
    """The multipart path shares the same unconditional release fetch."""
    monkeypatch.setattr(
        s3_service,
        "create_multipart_upload",
        lambda **kwargs: {
            "upload_id": "u1",
            "s3_key": "attachments/chat/no-release/344/abc/big.bin",
            "file_id": "abc",
        },
    )
    project = await factories.project()
    issue = await factories.issue(project_id=project.id, release_id=None)

    admin = factories.admin_client
    resp = await admin.post(
        f"/issues/{issue.id}/attachments/multipart/start",
        json={
            "filename": "big.bin",
            "mime_type": "application/octet-stream",
            "total_size_bytes": 600 * 1024 * 1024,
        },
    )
    assert resp.status_code == 200
