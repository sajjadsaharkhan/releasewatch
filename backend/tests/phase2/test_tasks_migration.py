"""Migration test for c4d5e6f7a8b9 (slice 03 — tasks and placement).

Mirrors test_status_migration.py's pattern: downgrade to the previous head,
insert a Phase-2-shaped (pre-slice-03) row with raw SQL, upgrade, and assert
the backfill through raw SQL (the ORM models only match the *new* schema).
Then proves the downgrade guard: with a null-``release_id`` issue present
(a hotfix or task), downgrade must refuse loudly rather than silently
corrupting data by forcing ``release_id`` back to ``NOT NULL``.

Always leaves the database back at ``head`` in a ``finally``, since every
other test's fixtures assume the current ORM models match the live schema.
"""

import asyncio
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.db.session import get_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PREVIOUS_HEAD = "b1c2d3e4f5a6"
NEW_HEAD = "c4d5e6f7a8b9"


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


async def _downgrade(rev: str) -> None:
    await asyncio.to_thread(command.downgrade, _alembic_config(), rev)


async def _upgrade(rev: str) -> None:
    await asyncio.to_thread(command.upgrade, _alembic_config(), rev)


@pytest.mark.asyncio
async def test_tasks_migration_backfills_and_seeds_general(factories, db_session, _bootstrap_admin):
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    admin_id = _bootstrap_admin.id  # read before rollback expires the ORM instance below

    engine = get_engine()
    # See test_status_migration.py — the fixture session holds an idle
    # transaction that would otherwise block the DDL below.
    await db_session.rollback()

    try:
        await _downgrade(PREVIOUS_HEAD)

        async with engine.begin() as conn:
            result = await conn.execute(text(
                "INSERT INTO issues (project_id, release_id, title, severity, status, "
                "reporter_id, labels, is_release_blocker, is_regression, regression_count) "
                "VALUES (:project_id, :release_id, :title, 'minor', 'new', :reporter_id, "
                "'{}', false, false, 0) RETURNING id"
            ), {
                "project_id": project.id, "release_id": release.id,
                "title": "pre-slice-03 bug", "reporter_id": admin_id,
            })
            legacy_issue_id = result.scalar_one()

        # ── Upgrade: backfill + seed ─────────────────────────────────────────
        await _upgrade(NEW_HEAD)

        async with engine.connect() as conn:
            issue_row = (await conn.execute(text(
                "SELECT type, priority, is_urgent, due_date, release_id "
                "FROM issues WHERE id = :id"
            ), {"id": legacy_issue_id})).mappings().one()
        assert issue_row["type"] == "bug"
        assert issue_row["priority"] is None
        assert issue_row["is_urgent"] is False
        assert issue_row["due_date"] is None
        assert issue_row["release_id"] == release.id

        async with engine.connect() as conn:
            project_row = (await conn.execute(text(
                "SELECT kind FROM projects WHERE id = :id"
            ), {"id": project.id})).mappings().one()
        assert project_row["kind"] == "product"

        async with engine.connect() as conn:
            general = (await conn.execute(text(
                "SELECT kind, triage_lead_id FROM projects WHERE slug = 'general'"
            ))).mappings().one()
        assert general["kind"] == "general"
        assert general["triage_lead_id"] == admin_id

        # ── Downgrade refuses loudly with a null-release_id row present ─────
        async with engine.begin() as conn:
            await conn.execute(text(
                "INSERT INTO issues (project_id, release_id, title, type, status, "
                "reporter_id, labels, is_release_blocker, is_regression, regression_count, "
                "is_urgent) "
                "VALUES (:project_id, NULL, 'a task with no release', 'task', 'todo', "
                ":reporter_id, '{}', false, false, 0, false)"
            ), {"project_id": project.id, "reporter_id": admin_id})

        with pytest.raises(Exception, match="Cannot downgrade"):
            await _downgrade(PREVIOUS_HEAD)

        # Nothing was left half-migrated — still at NEW_HEAD.
        async with engine.connect() as conn:
            current = (await conn.execute(
                text("SELECT version_num FROM alembic_version")
            )).scalar_one()
        assert current == NEW_HEAD
    finally:
        await _upgrade("head")
