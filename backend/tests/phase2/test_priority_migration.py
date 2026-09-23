"""Migration test for the priority half of b1c2d3e4f5a6 (03a Part 1).

A Phase 1 fixture with one bug per old severity is upgraded and asserted
against the 03a mapping table — including the release-blocker side effect of
``blocker`` — then downgraded and asserted back.

Same pattern as test_status_migration.py: raw SQL only (the ORM models match
the new schema), and always leaves the database at ``head``.
"""

import asyncio
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.db.session import get_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PREVIOUS_HEAD = "a7c4e1b93f20"
NEW_HEAD = "b1c2d3e4f5a6"

#: Phase 1 severity -> (priority, is_release_blocker after upgrade).
MAPPING = {
    "blocker": ("critical", True),
    "critical": ("critical", False),
    "major": ("high", False),
    "minor": ("medium", False),
    "enhancement": ("low", False),
}


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


async def _downgrade(rev: str) -> None:
    await asyncio.to_thread(command.downgrade, _alembic_config(), rev)


async def _upgrade(rev: str) -> None:
    await asyncio.to_thread(command.upgrade, _alembic_config(), rev)


@pytest.mark.asyncio
async def test_priority_migration_maps_every_phase1_severity(factories, db_session):
    reporter = await factories.user(role="qa")
    project = await factories.project()
    release = await factories.release(project_id=project.id)

    engine = get_engine()
    # See test_status_migration.py — the fixture session's idle transaction
    # would block the DDL below.
    await db_session.rollback()

    try:
        await _downgrade(PREVIOUS_HEAD)

        ids: dict[str, int] = {}
        async with engine.begin() as conn:
            for severity in MAPPING:
                result = await conn.execute(text(
                    "INSERT INTO issues (project_id, release_id, title, severity, status, "
                    "reporter_id, labels, is_release_blocker, is_regression, regression_count) "
                    "VALUES (:project_id, :release_id, :title, :severity, 'new', :reporter_id, "
                    "'{}', false, false, 0) RETURNING id"
                ), {
                    "project_id": project.id, "release_id": release.id,
                    "title": f"phase1 {severity}", "severity": severity,
                    "reporter_id": reporter.id,
                })
                ids[severity] = result.scalar_one()

        await _upgrade(NEW_HEAD)

        async with engine.connect() as conn:
            columns = set((await conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'issues'"
            ))).scalars().all())
            rows = (await conn.execute(text(
                "SELECT id, priority, is_release_blocker FROM issues WHERE id = ANY(:ids)"
            ), {"ids": list(ids.values())})).mappings().all()
            by_id = {r["id"]: r for r in rows}

        assert "severity" not in columns
        for severity, (priority, is_blocker) in MAPPING.items():
            row = by_id[ids[severity]]
            assert row["priority"] == priority, severity
            assert row["is_release_blocker"] is is_blocker, severity

        # A New bug nobody rated may now have no priority (BR-16).
        async with engine.begin() as conn:
            await conn.execute(text(
                "UPDATE issues SET priority = NULL WHERE id = :id"
            ), {"id": ids["minor"]})

        # ── Downgrade: best-effort reverse ──────────────────────────────────
        await _downgrade(PREVIOUS_HEAD)

        async with engine.connect() as conn:
            rows = (await conn.execute(text(
                "SELECT id, severity FROM issues WHERE id = ANY(:ids)"
            ), {"ids": list(ids.values())})).mappings().all()
            severity_by_id = {r["id"]: r["severity"] for r in rows}

        # blocker vs. critical can't be told apart once both are critical.
        assert severity_by_id[ids["blocker"]] == "critical"
        assert severity_by_id[ids["critical"]] == "critical"
        assert severity_by_id[ids["major"]] == "major"
        assert severity_by_id[ids["minor"]] == "minor"  # null -> minor
        assert severity_by_id[ids["enhancement"]] == "enhancement"
    finally:
        await _upgrade("head")
