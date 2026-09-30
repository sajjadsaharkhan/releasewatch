"""Backfill a ``created`` release event for every existing release

Revision ID: c9d0e1f2a3b4
Revises: a6b7c8d9e0f1
Create Date: 2026-09-30

Slice 09 follow-up: the Activity tab now starts with "created" (in Planning).
New releases write it in ``ReleaseService.create``; this gives releases created
before that one too, stamped with the release's own ``created_at`` and creator.
Idempotent — a release that already has a ``created`` event is skipped.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "a6b7c8d9e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO release_events (release_id, actor_id, event_type, meta, created_at)
        SELECT r.id, r.created_by_id, 'created',
               jsonb_build_object('version', r.version, 'status', 'planning', 'backfilled', true),
               r.created_at
        FROM releases r
        WHERE r.kind = 'release'
          AND NOT EXISTS (
              SELECT 1 FROM release_events e
              WHERE e.release_id = r.id AND e.event_type = 'created'
          )
    """)


def downgrade() -> None:
    op.execute(
        "DELETE FROM release_events WHERE event_type = 'created' AND meta ->> 'backfilled' = 'true'"
    )
