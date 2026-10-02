"""drop the structured reason from triage rejections

Revision ID: a7c3d9e1f2b4
Revises: 8ea5104b5b90
Create Date: 2026-10-02

The Reject triage outcome no longer stores a structured reason — the triager's
comment is the explanation. This clears ``issues.cancel_reason`` on bugs that
were cancelled by a triage Reject (their ``triaged`` timeline event says so).
A bug cancelled any other way keeps its reason, and the timeline history is
left untouched.

Reversible: the cleared values are copied into ``triage_reject_reason_backup``
first, and the downgrade puts them back and drops the table.

Written by hand.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a7c3d9e1f2b4'
down_revision: Union[str, None] = '8ea5104b5b90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FROM_TRIAGE_REJECT = """
    i.cancel_reason IN ('user_error', 'expected_behavior', 'cannot_reproduce')
    AND EXISTS (
        SELECT 1 FROM issue_timeline t
        WHERE t.issue_id = i.id AND t.event_type = 'triaged' AND t.meta->>'outcome' = 'reject'
    )
"""


def upgrade() -> None:
    op.create_table(
        'triage_reject_reason_backup',
        sa.Column('issue_id', sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column('cancel_reason', sa.String(length=32), nullable=False),
    )
    op.execute(f"""
        INSERT INTO triage_reject_reason_backup (issue_id, cancel_reason)
        SELECT i.id, i.cancel_reason FROM issues i WHERE {_FROM_TRIAGE_REJECT}
    """)
    op.execute("""
        UPDATE issues SET cancel_reason = NULL
        WHERE id IN (SELECT issue_id FROM triage_reject_reason_backup)
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE issues i SET cancel_reason = b.cancel_reason
        FROM triage_reject_reason_backup b WHERE b.issue_id = i.id
    """)
    op.drop_table('triage_reject_reason_backup')
