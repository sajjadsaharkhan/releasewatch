"""Verified status — Done means on production (slice 19, PRD v3.1 BR-74)

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-11-24

``issues.status`` is a plain ``String(32)``, so the new ``verified`` status needs
no DDL — only the data moves. Up (BR-74): every Done item inside a Release that
is not Released becomes Verified, keeping its ``verified_at`` (and its cycles'),
and loses ``completed_at`` — it is not on production. Their queue entries were
dormant already (Done); any that is not is marked dormant with its pin cleared.
Done items in a Released release and in the Stream stay Done.

A data move is not an action: no timeline events are written. The count of
moved rows is logged.

Down: ``verified → done`` with ``completed_at`` = ``verified_at`` (the v3 shape,
where release items were Done at verification). Idempotent both ways.
"""

import logging
from typing import Sequence, Union

from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

log = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    bind = op.get_bind()
    moved = bind.exec_driver_sql("""
        WITH moved AS (
            UPDATE issues i
            SET status = 'verified',
                verified_at = COALESCE(i.verified_at, i.completed_at),
                completed_at = NULL
            FROM releases r
            WHERE i.release_id = r.id
              AND r.kind = 'release'
              AND r.status <> 'released'
              AND i.status = 'done'
            RETURNING i.id
        ), dormant AS (
            UPDATE queue_entries q
            SET left_at = COALESCE(q.left_at, now()),
                is_pinned = false, pin_locked = false,
                pinned_by_id = NULL, pinned_at = NULL
            FROM moved
            WHERE q.issue_id = moved.id
              AND (q.left_at IS NULL OR q.is_pinned)
            RETURNING q.id
        )
        SELECT count(*) FROM moved
    """).scalar_one()
    log.info("verified_status: %s Done item(s) in unshipped releases became Verified", moved)


def downgrade() -> None:
    bind = op.get_bind()
    moved = bind.exec_driver_sql("""
        UPDATE issues
        SET status = 'done',
            completed_at = COALESCE(verified_at, updated_at)
        WHERE status = 'verified'
    """).rowcount
    log.info("verified_status: %s Verified item(s) became Done", moved)
