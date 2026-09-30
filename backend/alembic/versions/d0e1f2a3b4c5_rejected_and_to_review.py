"""To review and Rejected statuses (09a)

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-30

``issues.status`` is a plain ``String(32)``, so the two new statuses need no
DDL — only the returned items change. Up: an item that came back and nobody
has picked up yet (``todo``, current cycle not ``planned``, ``picked_up_at``
null) becomes ``rejected``. Items already In progress keep their status; the
cycle badge says they came back. Down: ``rejected → todo``, ``to_review →
in_review``. Reject comments keep their ``meta.return_reason`` either way.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE issues i
        SET status = 'rejected'
        FROM issue_cycles c
        WHERE c.id = i.current_cycle_id
          AND i.status = 'todo'
          AND c.start_reason <> 'planned'
          AND c.picked_up_at IS NULL
    """)


def downgrade() -> None:
    op.execute("UPDATE issues SET status = 'todo' WHERE status = 'rejected'")
    op.execute("UPDATE issues SET status = 'in_review' WHERE status = 'to_review'")
