"""tasks and placement

Revision ID: d6e7f8a9b0c1
Revises: b1c2d3e4f5a6
Create Date: 2026-09-23

Slice 03 (docs/phase-2/03-tasks-and-placement.md): adds `issues.type`
(bug|task, D-defaulted to bug), makes `issues.release_id` nullable with its
FK changed CASCADE -> SET NULL (D7 — a release can be deleted without
deleting the work items filed against it), and adds `due_date`. Priority is
the shared column from b1c2d3e4f5a6 (03a Part 1), so tasks add none of their
own. Adds `projects.kind` (product|internal|general, defaulted to
product) and seeds a General project with the first active admin (by id) as
triage lead, or a null lead if no admin exists.

Written by hand, following b1c2d3e4f5a6's lead. Rewritten for 03a under a new
revision id (was c4d5e6f7a8b9) so a database migrated with the old version
fails loudly instead of keeping a stale schema — rebuild it with
`make db-reset`.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd6e7f8a9b0c1'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── issues: type, due_date ─────────────────────────────────────────────
    # NOT NULL + a transient server_default backfills existing rows in place;
    # the default is then dropped so the ORM's Python-side defaults are the
    # single source (raw inserts must state a type explicitly).
    op.add_column('issues', sa.Column(
        'type', sa.String(length=16), nullable=False, server_default='bug',
    ))
    op.add_column('issues', sa.Column('due_date', sa.Date(), nullable=True))

    # ── issues.release_id: nullable, FK CASCADE -> SET NULL (D7, BR-26) ───────
    op.alter_column('issues', 'release_id', existing_type=sa.Integer(), nullable=True)
    op.drop_constraint('issues_release_id_fkey', 'issues', type_='foreignkey')
    op.create_foreign_key(
        'fk_issues_release_id_releases', 'issues', 'releases',
        ['release_id'], ['id'], ondelete='SET NULL',
    )

    # ── projects.kind ───────────────────────────────────────────────────────
    op.add_column('projects', sa.Column(
        'kind', sa.String(length=16), nullable=False, server_default='product',
    ))

    # ── Drop the transient backfill defaults ────────────────────────────────
    op.alter_column('issues', 'type', existing_type=sa.String(length=16), server_default=None)
    op.alter_column('projects', 'kind', existing_type=sa.String(length=16), server_default=None)

    # ── Seed the General project (FR-02) ───────────────────────────────────
    op.execute("""
        INSERT INTO projects (name, slug, color, description, kind, default_labels, triage_lead_id, created_at)
        SELECT 'General', 'general', '#6366f1', NULL, 'general', ARRAY[]::text[],
               (SELECT id FROM users WHERE role = 'admin' AND is_active = true ORDER BY id ASC LIMIT 1),
               now()
        WHERE NOT EXISTS (SELECT 1 FROM projects WHERE slug = 'general')
    """)


def downgrade() -> None:
    # The downgrade cannot invent a release for a hotfix or a task, so it
    # refuses loudly rather than corrupting data (spec: "Migration test").
    conn = op.get_bind()
    null_release_count = conn.execute(
        sa.text("SELECT count(*) FROM issues WHERE release_id IS NULL")
    ).scalar()
    if null_release_count:
        raise RuntimeError(
            f"Cannot downgrade d6e7f8a9b0c1: {null_release_count} issue(s) have "
            "release_id IS NULL (hotfixes or tasks). Assign a release to each "
            "before downgrading, or accept losing that data."
        )

    # Best-effort reverse — deletes the seeded General project outright,
    # which is only reachable here because the guard above already proved
    # no issue has a null release_id (so General, if unused, has none either).
    op.execute("DELETE FROM projects WHERE slug = 'general'")
    op.drop_column('projects', 'kind')

    op.drop_constraint('fk_issues_release_id_releases', 'issues', type_='foreignkey')
    op.alter_column('issues', 'release_id', existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        'issues_release_id_fkey', 'issues', 'releases',
        ['release_id'], ['id'], ondelete='CASCADE',
    )

    op.drop_column('issues', 'due_date')
    op.drop_column('issues', 'type')
