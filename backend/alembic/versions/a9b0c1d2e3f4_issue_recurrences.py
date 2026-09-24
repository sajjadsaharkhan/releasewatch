"""issue recurrences

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-09-24

Slice 07 (docs/phase-2/07-recurrence.md): ``issue_recurrences`` — one row per
Report recurrence action, so reports (slice 11) can count recurrences over
time. ``issues.recurrence_count`` (slice 05) stays the number the UI shows.

Written by hand, following e7f8a9b0c1d2's lead.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a9b0c1d2e3f4'
down_revision: Union[str, None] = 'f8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'issue_recurrences',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('issue_id', sa.Integer(), sa.ForeignKey('issues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reported_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('timeline_id', sa.Integer(), sa.ForeignKey('issue_timeline.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_issue_recurrences_issue_id', 'issue_recurrences', ['issue_id'])
    op.create_index('ix_issue_recurrences_reported_by_id', 'issue_recurrences', ['reported_by_id'])
    op.create_index('ix_issue_recurrences_created_at', 'issue_recurrences', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_issue_recurrences_created_at', table_name='issue_recurrences')
    op.drop_index('ix_issue_recurrences_reported_by_id', table_name='issue_recurrences')
    op.drop_index('ix_issue_recurrences_issue_id', table_name='issue_recurrences')
    op.drop_table('issue_recurrences')
