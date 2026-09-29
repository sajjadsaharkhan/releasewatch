"""releases: Stream and Release containers (08a Part 1)

Revision ID: e4f5a6b7c8d9
Revises: d2e3f4a5b6c7
Create Date: 2026-09-30

PRD v3 §8.1: every project has one Stream and any number of Releases, both
rows of ``releases``.

- ``releases.kind`` (stream | release, default release) with a partial unique
  index — one Stream per project.
- ``releases.status`` takes the v3 lifecycle values (planning | development |
  qa | released | cancelled) and is null for the Stream (check constraint).
  Existing rows are mapped: active → development, blocked → qa,
  archived → released.
- ``releases.code_freeze_date`` and ``releases.released_at``.
- One Stream is created for every existing project; new projects get theirs
  from an ORM ``after_insert`` hook (``app/db/models/release.py``).

No data migration beyond that: Phase 2 has not shipped; rebuild dev databases
with ``make db-reset``.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('releases', sa.Column(
        'kind', sa.String(length=16), nullable=False, server_default='release',
    ))
    op.add_column('releases', sa.Column('code_freeze_date', sa.Date(), nullable=True))
    op.add_column('releases', sa.Column('released_at', sa.DateTime(timezone=True), nullable=True))

    op.alter_column('releases', 'status', existing_type=sa.String(length=32), nullable=True)
    op.execute("""
        UPDATE releases SET status = CASE status
            WHEN 'active' THEN 'development'
            WHEN 'blocked' THEN 'qa'
            WHEN 'archived' THEN 'released'
            ELSE status END
    """)
    op.execute("UPDATE releases SET released_at = updated_at WHERE status = 'released'")

    op.execute("""
        INSERT INTO releases (project_id, kind, version, status, go_nogo_status, created_at, updated_at)
        SELECT id, 'stream', 'Stream', NULL, 'pending', now(), now() FROM projects
    """)

    op.create_index(
        'uq_releases_one_stream_per_project', 'releases', ['project_id'],
        unique=True, postgresql_where=sa.text("kind = 'stream'"),
    )
    op.create_check_constraint(
        'ck_releases_status_by_kind', 'releases',
        "(kind = 'stream' AND status IS NULL) OR (kind = 'release' AND status IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint('ck_releases_status_by_kind', 'releases', type_='check')
    op.drop_index('uq_releases_one_stream_per_project', table_name='releases')
    # Items in a Stream go back to having no release (the FK is SET NULL).
    op.execute("DELETE FROM releases WHERE kind = 'stream'")
    op.execute("""
        UPDATE releases SET status = CASE status
            WHEN 'planning' THEN 'active'
            WHEN 'development' THEN 'active'
            WHEN 'qa' THEN 'active'
            WHEN 'cancelled' THEN 'archived'
            ELSE status END
    """)
    op.alter_column('releases', 'status', existing_type=sa.String(length=32), nullable=False)
    op.drop_column('releases', 'released_at')
    op.drop_column('releases', 'code_freeze_date')
    op.drop_column('releases', 'kind')
