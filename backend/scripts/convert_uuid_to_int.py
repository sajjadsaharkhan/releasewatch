#!/usr/bin/env python3
"""
Convert all UUID primary keys to auto-increment integers in-place.

Preserves all existing data. Run once against a database that still has UUID PKs.

Usage (from backend/):
    python scripts/convert_uuid_to_int.py

Or with explicit DB URL:
    DATABASE_URL=postgresql://... python scripts/convert_uuid_to_int.py
"""

import asyncio
import os
import sys

# Allow running from the backend directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main() -> None:
    try:
        import asyncpg
    except ImportError:
        print("ERROR: asyncpg not installed. Run: pip install asyncpg")
        sys.exit(1)

    from app.config import settings

    # asyncpg needs plain postgresql:// not postgresql+asyncpg://
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    print(f"Connecting to database…")
    conn = await asyncpg.connect(db_url)

    try:
        print("Starting UUID → integer conversion (single transaction)…")
        async with conn.transaction():
            await _run_conversion(conn)
        print("\n✓ Conversion complete.")
    except Exception as exc:
        print(f"\n✗ Conversion failed: {exc}")
        raise
    finally:
        await conn.close()


async def _run_conversion(conn) -> None:
    # ── 1. Add new SERIAL columns for every PK ────────────────────────────────
    print("  [1/8] Adding new integer PK columns…")
    tables = [
        "users", "labels", "system_settings", "projects", "releases",
        "issues", "issue_timeline", "issue_attachments",
        "regression_history", "issue_cycles", "inbox_items",
    ]
    for table in tables:
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN _new_id SERIAL")

    # ── 2. Add new integer FK columns ─────────────────────────────────────────
    print("  [2/8] Adding new integer FK columns…")
    fk_additions = [
        # (table, column)
        ("projects",          "_new_created_by_id"),
        ("releases",          "_new_project_id"),
        ("releases",          "_new_go_nogo_by_id"),
        ("releases",          "_new_created_by_id"),
        ("issues",            "_new_project_id"),
        ("issues",            "_new_release_id"),
        ("issues",            "_new_reporter_id"),
        ("issues",            "_new_assignee_id"),
        ("issues",            "_new_parent_issue_id"),
        ("issue_timeline",    "_new_issue_id"),
        ("issue_timeline",    "_new_actor_id"),
        ("issue_attachments", "_new_issue_id"),
        ("issue_attachments", "_new_uploaded_by_id"),
        ("regression_history","_new_issue_id"),
        ("regression_history","_new_release_id"),
        ("regression_history","_new_detected_by_id"),
        ("regression_history","_new_previous_fix_by_id"),
        ("regression_history","_new_previous_fix_timeline_id"),
        ("issue_cycles",      "_new_issue_id"),
        ("issue_cycles",      "_new_regression_history_id"),
        ("inbox_items",       "_new_user_id"),
        ("inbox_items",       "_new_actor_id"),
        ("inbox_items",       "_new_issue_id"),
        ("inbox_items",       "_new_timeline_id"),
    ]
    for table, col in fk_additions:
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} INTEGER")

    # ── 3. Populate FK columns via UUID→int joins ──────────────────────────────
    print("  [3/8] Mapping FK references to new integer IDs…")
    updates = [
        # projects
        "UPDATE projects p SET _new_created_by_id = u._new_id FROM users u WHERE p.created_by_id = u.id",
        # releases
        "UPDATE releases r SET _new_project_id   = p._new_id FROM projects p WHERE r.project_id   = p.id",
        "UPDATE releases r SET _new_go_nogo_by_id = u._new_id FROM users u    WHERE r.go_nogo_by_id = u.id",
        "UPDATE releases r SET _new_created_by_id = u._new_id FROM users u    WHERE r.created_by_id = u.id",
        # issues
        "UPDATE issues i SET _new_project_id      = p._new_id FROM projects p WHERE i.project_id      = p.id",
        "UPDATE issues i SET _new_release_id      = r._new_id FROM releases r WHERE i.release_id      = r.id",
        "UPDATE issues i SET _new_reporter_id     = u._new_id FROM users u    WHERE i.reporter_id     = u.id",
        "UPDATE issues i SET _new_assignee_id     = u._new_id FROM users u    WHERE i.assignee_id     = u.id",
        "UPDATE issues child SET _new_parent_issue_id = parent._new_id FROM issues parent WHERE child.parent_issue_id = parent.id",
        # issue_timeline
        "UPDATE issue_timeline t SET _new_issue_id = i._new_id FROM issues i WHERE t.issue_id = i.id",
        "UPDATE issue_timeline t SET _new_actor_id = u._new_id FROM users u  WHERE t.actor_id = u.id",
        # issue_attachments
        "UPDATE issue_attachments a SET _new_issue_id       = i._new_id FROM issues i WHERE a.issue_id       = i.id",
        "UPDATE issue_attachments a SET _new_uploaded_by_id = u._new_id FROM users u  WHERE a.uploaded_by_id = u.id",
        # regression_history
        "UPDATE regression_history rh SET _new_issue_id              = i._new_id FROM issues i         WHERE rh.issue_id              = i.id",
        "UPDATE regression_history rh SET _new_release_id            = r._new_id FROM releases r       WHERE rh.release_id            = r.id",
        "UPDATE regression_history rh SET _new_detected_by_id        = u._new_id FROM users u          WHERE rh.detected_by_id        = u.id",
        "UPDATE regression_history rh SET _new_previous_fix_by_id    = u._new_id FROM users u          WHERE rh.previous_fix_by_id    = u.id",
        "UPDATE regression_history rh SET _new_previous_fix_timeline_id = t._new_id FROM issue_timeline t WHERE rh.previous_fix_timeline_id = t.id",
        # issue_cycles
        "UPDATE issue_cycles c SET _new_issue_id            = i._new_id  FROM issues i            WHERE c.issue_id            = i.id",
        "UPDATE issue_cycles c SET _new_regression_history_id = rh._new_id FROM regression_history rh WHERE c.regression_history_id = rh.id",
        # inbox_items
        "UPDATE inbox_items ii SET _new_user_id    = u._new_id FROM users u         WHERE ii.user_id    = u.id",
        "UPDATE inbox_items ii SET _new_actor_id   = u._new_id FROM users u         WHERE ii.actor_id   = u.id",
        "UPDATE inbox_items ii SET _new_issue_id   = i._new_id FROM issues i        WHERE ii.issue_id   = i.id",
        "UPDATE inbox_items ii SET _new_timeline_id = t._new_id FROM issue_timeline t WHERE ii.timeline_id = t.id",
    ]
    for sql in updates:
        await conn.execute(sql)

    # ── 4. Drop all FK constraints ─────────────────────────────────────────────
    print("  [4/8] Dropping FK constraints…")
    fk_rows = await conn.fetch("""
        SELECT tc.table_name, tc.constraint_name
        FROM information_schema.table_constraints tc
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = 'public'
    """)
    for row in fk_rows:
        await conn.execute(
            f'ALTER TABLE {row["table_name"]} DROP CONSTRAINT IF EXISTS {row["constraint_name"]}'
        )

    # ── 5. Drop old UUID PK constraints ───────────────────────────────────────
    print("  [5/8] Dropping UUID primary key constraints…")
    pk_rows = await conn.fetch("""
        SELECT tc.table_name, tc.constraint_name
        FROM information_schema.table_constraints tc
        WHERE tc.constraint_type = 'PRIMARY KEY'
        AND tc.table_schema = 'public'
        AND tc.table_name = ANY($1)
    """, tables)
    for row in pk_rows:
        await conn.execute(
            f'ALTER TABLE {row["table_name"]} DROP CONSTRAINT IF EXISTS {row["constraint_name"]}'
        )

    # ── 6. Swap PK columns: drop UUID id, rename _new_id → id ─────────────────
    print("  [6/8] Swapping PK columns (UUID → integer)…")
    for table in tables:
        await conn.execute(f"ALTER TABLE {table} DROP COLUMN id")
        await conn.execute(f"ALTER TABLE {table} RENAME COLUMN _new_id TO id")
        await conn.execute(f"ALTER TABLE {table} ADD PRIMARY KEY (id)")

    # ── 7. Swap FK columns ─────────────────────────────────────────────────────
    print("  [7/8] Swapping FK columns…")
    fk_swaps = [
        # (table, old_column, new_column, not_null)
        ("projects",           "created_by_id",            "_new_created_by_id",             False),
        ("releases",           "project_id",               "_new_project_id",                True),
        ("releases",           "go_nogo_by_id",            "_new_go_nogo_by_id",             False),
        ("releases",           "created_by_id",            "_new_created_by_id",             False),
        ("issues",             "project_id",               "_new_project_id",                True),
        ("issues",             "release_id",               "_new_release_id",                True),
        ("issues",             "reporter_id",              "_new_reporter_id",               False),
        ("issues",             "assignee_id",              "_new_assignee_id",               False),
        ("issues",             "parent_issue_id",          "_new_parent_issue_id",           False),
        ("issue_timeline",     "issue_id",                 "_new_issue_id",                  True),
        ("issue_timeline",     "actor_id",                 "_new_actor_id",                  False),
        ("issue_attachments",  "issue_id",                 "_new_issue_id",                  True),
        ("issue_attachments",  "uploaded_by_id",           "_new_uploaded_by_id",            False),
        ("regression_history", "issue_id",                 "_new_issue_id",                  True),
        ("regression_history", "release_id",               "_new_release_id",                True),
        ("regression_history", "detected_by_id",           "_new_detected_by_id",            False),
        ("regression_history", "previous_fix_by_id",       "_new_previous_fix_by_id",        False),
        ("regression_history", "previous_fix_timeline_id", "_new_previous_fix_timeline_id",  False),
        ("issue_cycles",       "issue_id",                 "_new_issue_id",                  True),
        ("issue_cycles",       "regression_history_id",    "_new_regression_history_id",     False),
        ("inbox_items",        "user_id",                  "_new_user_id",                   True),
        ("inbox_items",        "actor_id",                 "_new_actor_id",                  False),
        ("inbox_items",        "issue_id",                 "_new_issue_id",                  True),
        ("inbox_items",        "timeline_id",              "_new_timeline_id",               False),
    ]
    for table, old_col, new_col, not_null in fk_swaps:
        await conn.execute(f"ALTER TABLE {table} DROP COLUMN {old_col}")
        await conn.execute(f"ALTER TABLE {table} RENAME COLUMN {new_col} TO {old_col}")
        if not_null:
            await conn.execute(f"ALTER TABLE {table} ALTER COLUMN {old_col} SET NOT NULL")

    # ── 8. Recreate FK constraints and indexes ─────────────────────────────────
    print("  [8/8] Recreating FK constraints and indexes…")
    ddl = """
        ALTER TABLE projects ADD CONSTRAINT fk_projects_created_by
            FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE releases ADD CONSTRAINT fk_releases_project
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
        ALTER TABLE releases ADD CONSTRAINT fk_releases_go_nogo_by
            FOREIGN KEY (go_nogo_by_id) REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE releases ADD CONSTRAINT fk_releases_created_by
            FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE issues ADD CONSTRAINT fk_issues_project
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
        ALTER TABLE issues ADD CONSTRAINT fk_issues_release
            FOREIGN KEY (release_id) REFERENCES releases(id) ON DELETE CASCADE;
        ALTER TABLE issues ADD CONSTRAINT fk_issues_reporter
            FOREIGN KEY (reporter_id) REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE issues ADD CONSTRAINT fk_issues_assignee
            FOREIGN KEY (assignee_id) REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE issues ADD CONSTRAINT fk_issues_parent
            FOREIGN KEY (parent_issue_id) REFERENCES issues(id) ON DELETE SET NULL;
        ALTER TABLE issue_timeline ADD CONSTRAINT fk_timeline_issue
            FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE;
        ALTER TABLE issue_timeline ADD CONSTRAINT fk_timeline_actor
            FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE issue_attachments ADD CONSTRAINT fk_attachments_issue
            FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE;
        ALTER TABLE issue_attachments ADD CONSTRAINT fk_attachments_uploader
            FOREIGN KEY (uploaded_by_id) REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE regression_history ADD CONSTRAINT fk_regression_issue
            FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE;
        ALTER TABLE regression_history ADD CONSTRAINT fk_regression_release
            FOREIGN KEY (release_id) REFERENCES releases(id) ON DELETE CASCADE;
        ALTER TABLE regression_history ADD CONSTRAINT fk_regression_detected_by
            FOREIGN KEY (detected_by_id) REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE regression_history ADD CONSTRAINT fk_regression_prev_fix_by
            FOREIGN KEY (previous_fix_by_id) REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE regression_history ADD CONSTRAINT fk_regression_prev_timeline
            FOREIGN KEY (previous_fix_timeline_id) REFERENCES issue_timeline(id) ON DELETE SET NULL;
        ALTER TABLE issue_cycles ADD CONSTRAINT fk_cycles_issue
            FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE;
        ALTER TABLE issue_cycles ADD CONSTRAINT fk_cycles_regression
            FOREIGN KEY (regression_history_id) REFERENCES regression_history(id) ON DELETE SET NULL;
        ALTER TABLE inbox_items ADD CONSTRAINT fk_inbox_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        ALTER TABLE inbox_items ADD CONSTRAINT fk_inbox_actor
            FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE inbox_items ADD CONSTRAINT fk_inbox_issue
            FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE;
        ALTER TABLE inbox_items ADD CONSTRAINT fk_inbox_timeline
            FOREIGN KEY (timeline_id) REFERENCES issue_timeline(id) ON DELETE SET NULL;

        CREATE INDEX IF NOT EXISTS ix_users_username          ON users(username);
        CREATE INDEX IF NOT EXISTS ix_users_telegram_user_id  ON users(telegram_user_id);
        CREATE INDEX IF NOT EXISTS ix_users_connect_token     ON users(connect_token);
        CREATE INDEX IF NOT EXISTS ix_labels_name             ON labels(name);
        CREATE INDEX IF NOT EXISTS ix_projects_slug           ON projects(slug);
        CREATE INDEX IF NOT EXISTS ix_releases_project_id     ON releases(project_id);
        CREATE INDEX IF NOT EXISTS ix_issues_project_id       ON issues(project_id);
        CREATE INDEX IF NOT EXISTS ix_issues_release_id       ON issues(release_id);
        CREATE INDEX IF NOT EXISTS ix_issues_reporter_id      ON issues(reporter_id);
        CREATE INDEX IF NOT EXISTS ix_issues_assignee_id      ON issues(assignee_id);
        CREATE INDEX IF NOT EXISTS ix_issue_timeline_issue_id ON issue_timeline(issue_id);
        CREATE INDEX IF NOT EXISTS ix_issue_attachments_issue_id ON issue_attachments(issue_id);
        CREATE INDEX IF NOT EXISTS ix_regression_history_issue_id   ON regression_history(issue_id);
        CREATE INDEX IF NOT EXISTS ix_regression_history_release_id ON regression_history(release_id);
        CREATE INDEX IF NOT EXISTS ix_issue_cycles_issue_id   ON issue_cycles(issue_id);
        CREATE INDEX IF NOT EXISTS ix_inbox_items_actor_id    ON inbox_items(actor_id);
        CREATE INDEX IF NOT EXISTS ix_inbox_items_issue_id    ON inbox_items(issue_id);
        CREATE INDEX IF NOT EXISTS ix_inbox_items_user_is_read ON inbox_items(user_id, is_read);
        CREATE INDEX IF NOT EXISTS ix_system_settings_category ON system_settings(category);
        CREATE INDEX IF NOT EXISTS ix_system_settings_key     ON system_settings(key);
    """
    for stmt in (s.strip() for s in ddl.split(";") if s.strip()):
        await conn.execute(stmt)

    # ── Stamp Alembic to the new migration ────────────────────────────────────
    try:
        await conn.execute("DELETE FROM alembic_version")
        await conn.execute(
            "INSERT INTO alembic_version (version_num) VALUES ('2f6a6c816018')"
        )
        print("  Alembic version stamped → 2f6a6c816018")
    except Exception:
        pass  # alembic_version table may not exist in all setups


if __name__ == "__main__":
    asyncio.run(main())
