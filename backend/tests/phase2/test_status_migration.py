"""Migration test for b1c2d3e4f5a6 (unified status model).

Builds a Phase 1-shaped dataset at the previous head (a7c4e1b93f20) — one row
per old status, plus the duplicate and needs-clarification cases — upgrades,
and asserts the mapping through raw SQL (the ORM models only match the *new*
schema, so they can't be used against the downgraded database). Then
downgrades and asserts the old statuses return.

This is the only test in the suite that changes the DB schema mid-run. It
always leaves the database back at ``head`` in a ``finally``, since every
other test's fixtures assume the current ORM models match the live schema.
"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.db.session import get_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PREVIOUS_HEAD = "a7c4e1b93f20"
NEW_HEAD = "b1c2d3e4f5a6"


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


async def _downgrade(rev: str) -> None:
    await asyncio.to_thread(command.downgrade, _alembic_config(), rev)


async def _upgrade(rev: str) -> None:
    await asyncio.to_thread(command.upgrade, _alembic_config(), rev)


@pytest.mark.asyncio
async def test_status_migration_upgrade_and_downgrade(factories, db_session):
    # Build users/projects/releases through the API while at head — this
    # migration doesn't touch those tables, so they're unaffected by the
    # downgrade below.
    reporter = await factories.user(role="qa")
    prev_assignee = await factories.user(role="developer")
    fixer = await factories.user(role="developer")
    project = await factories.project()
    release = await factories.release(project_id=project.id)

    engine = get_engine()

    # `factories`' bootstrap admin (`db_session.refresh(admin)`, in conftest.py)
    # leaves this fixture session idle-in-transaction holding a read lock —
    # harmless for ordinary DML tests, but it blocks the ALTER TABLE below
    # (a DROP CONSTRAINT on issues<->users) indefinitely. Nothing else needs
    # this session, so close it out before touching DDL.
    await db_session.rollback()

    try:
        await _downgrade(PREVIOUS_HEAD)

        # Insert one issue per old status directly — the ORM models no
        # longer match this schema, so raw SQL only.
        async with engine.begin() as conn:
            async def _insert_issue(key: str, status: str, **extra) -> int:
                cols = {
                    "project_id": project.id,
                    "release_id": release.id,
                    "title": f"phase1 {key}",
                    "severity": extra.pop("severity", "minor"),
                    "status": status,
                    "reporter_id": reporter.id,
                    "labels": [],
                    "is_release_blocker": False,
                    "is_regression": extra.pop("is_regression", False),
                    "regression_count": extra.pop("regression_count", 0),
                    **extra,
                }
                col_names = ", ".join(cols)
                placeholders = ", ".join(f":{k}" for k in cols)
                result = await conn.execute(
                    text(f"INSERT INTO issues ({col_names}) VALUES ({placeholders}) RETURNING id"),
                    cols,
                )
                return result.scalar_one()

            new_id = await _insert_issue("new", "new", severity="enhancement")
            triaged_id = await _insert_issue("triaged", "triaged", assignee_id=fixer.id)
            fixed_id = await _insert_issue("fixed", "fixed", assignee_id=fixer.id)
            now = datetime.now(UTC)
            verified_id = await _insert_issue(
                "verified", "verified", assignee_id=fixer.id, verified_at=now,
            )
            closed_id = await _insert_issue(
                "closed", "closed", assignee_id=fixer.id, closed_at=now,
            )
            duplicate_id = await _insert_issue(
                "duplicate", "closed", parent_issue_id=new_id, closed_at=now,
            )
            regression_id = await _insert_issue(
                "regression", "regression", assignee_id=fixer.id,
                is_regression=True, regression_count=1,
            )
            needs_info_id = await _insert_issue("needs_info", "blocked", assignee_id=reporter.id)
            plain_blocked_id = await _insert_issue("plain_blocked", "blocked", assignee_id=fixer.id)

            # Timeline events the migration reads: the "fixed" issue's actor
            # (for review_requested_by_id), and the needs_info issue's latest
            # needs_clarification event (for the assignee restore).
            timeline_cols = "issue_id, actor_id, event_type, meta, is_internal, created_at"
            await conn.execute(text(
                f"INSERT INTO issue_timeline ({timeline_cols}) "
                "VALUES (:issue_id, :actor_id, 'fixed', '{}'::jsonb, false, now())"
            ), {"issue_id": fixed_id, "actor_id": fixer.id})
            await conn.execute(text(
                f"INSERT INTO issue_timeline ({timeline_cols}) "
                "VALUES (:issue_id, :actor_id, 'needs_clarification', "
                "jsonb_build_object('prev_assignee_id', CAST(:prev_assignee_id AS text)), "
                "false, now())"
            ), {
                "issue_id": needs_info_id, "actor_id": fixer.id,
                "prev_assignee_id": str(prev_assignee.id),
            })

        # ── Upgrade: run the migration ──────────────────────────────────────
        await _upgrade(NEW_HEAD)

        async with engine.connect() as conn:
            rows = (await conn.execute(text(
                "SELECT id, status, severity, cancel_reason, blocked_from_status, "
                "review_requested_by_id, completed_at, assignee_id "
                "FROM issues WHERE id = ANY(:ids)"
            ), {"ids": [
                new_id, triaged_id, fixed_id, verified_id, closed_id,
                duplicate_id, regression_id, needs_info_id, plain_blocked_id,
            ]})).mappings().all()
            by_id = {r["id"]: r for r in rows}

        assert by_id[new_id]["status"] == "new"
        assert by_id[new_id]["severity"] == "minor"  # enhancement -> minor

        assert by_id[triaged_id]["status"] == "todo"

        assert by_id[fixed_id]["status"] == "in_review"
        assert by_id[fixed_id]["review_requested_by_id"] == fixer.id

        assert by_id[verified_id]["status"] == "done"
        assert by_id[verified_id]["completed_at"] is not None

        assert by_id[closed_id]["status"] == "done"
        assert by_id[closed_id]["completed_at"] is not None

        assert by_id[duplicate_id]["status"] == "cancelled"
        assert by_id[duplicate_id]["cancel_reason"] == "duplicate"

        assert by_id[regression_id]["status"] == "in_progress"

        assert by_id[needs_info_id]["status"] == "needs_info"
        assert by_id[needs_info_id]["assignee_id"] == prev_assignee.id

        assert by_id[plain_blocked_id]["status"] == "blocked"
        assert by_id[plain_blocked_id]["blocked_from_status"] == "in_progress"

        # ── Downgrade: best-effort reverse ──────────────────────────────────
        await _downgrade(PREVIOUS_HEAD)

        async with engine.connect() as conn:
            downgraded_ids = [
                new_id, triaged_id, fixed_id, verified_id, needs_info_id, duplicate_id,
            ]
            rows = (await conn.execute(
                text("SELECT id, status FROM issues WHERE id = ANY(:ids)"),
                {"ids": downgraded_ids},
            )).mappings().all()
            by_id = {r["id"]: r["status"] for r in rows}

        assert by_id[new_id] == "new"
        assert by_id[triaged_id] == "triaged"
        assert by_id[fixed_id] == "fixed"
        assert by_id[verified_id] == "verified"
        assert by_id[needs_info_id] == "blocked"
        assert by_id[duplicate_id] == "closed"
    finally:
        # Every other test's fixtures assume the ORM's current models match
        # the live schema — always leave the database at head.
        await _upgrade("head")
