"""Migration test for d0e1f2a3b4c5 (09a — To review and Rejected).

The revision is data-only, so the fixture is built through the API at head:
downgrading turns it into the 08a shape (returned items in To do, no To
review), and upgrading again must find the returned-not-picked-up item.
Always leaves the database back at ``head``.
"""

import asyncio
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.db.session import get_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PREVIOUS_HEAD = "c9d0e1f2a3b4"


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


async def _statuses(engine, ids: dict[str, int]) -> dict[str, str]:
    async with engine.connect() as conn:
        rows = (await conn.execute(
            text("SELECT id, status FROM issues WHERE id = ANY(:ids)"),
            {"ids": list(ids.values())},
        )).all()
    by_id = dict(rows)
    return {name: by_id[i] for name, i in ids.items()}


@pytest.mark.asyncio
async def test_rejected_migration_upgrade_and_downgrade(factories, db_session):
    admin = factories.admin_client
    project = await factories.project()
    stream_id = await factories.stream_id(project_id=project.id)

    async def task(*steps):
        item = await factories.issue(project_id=project.id, type="task", release_id=stream_id)
        for to in steps:
            resp = await admin.post(f"/issues/{item.id}/transition", json={"to": to})
            assert resp.status_code == 200, resp.text
        return item.id

    async def reject(issue_id):
        resp = await admin.post(f"/issues/{issue_id}/reject", json={"comment": "Broken."})
        assert resp.status_code == 200, resp.text

    ids = {
        "returned_waiting": await task("in_progress", "in_review"),
        "returned_in_progress": await task("in_progress", "in_review"),
        "in_review": await task("in_progress", "in_review"),
        "to_review": await task("in_progress", "to_review"),
        "plain_todo": await task(),
    }
    await reject(ids["returned_waiting"])
    await reject(ids["returned_in_progress"])
    resp = await admin.post(
        f"/issues/{ids['returned_in_progress']}/transition", json={"to": "in_progress"},
    )
    assert resp.status_code == 200, resp.text

    engine = get_engine()
    await db_session.rollback()
    try:
        await asyncio.to_thread(command.downgrade, _alembic_config(), PREVIOUS_HEAD)
        assert await _statuses(engine, ids) == {
            "returned_waiting": "todo",
            "returned_in_progress": "in_progress",
            "in_review": "in_review",
            "to_review": "in_review",
            "plain_todo": "todo",
        }

        await asyncio.to_thread(command.upgrade, _alembic_config(), "head")
        assert await _statuses(engine, ids) == {
            "returned_waiting": "rejected",
            "returned_in_progress": "in_progress",
            "in_review": "in_review",
            "to_review": "in_review",
            "plain_todo": "todo",
        }
    finally:
        await asyncio.to_thread(command.upgrade, _alembic_config(), "head")
