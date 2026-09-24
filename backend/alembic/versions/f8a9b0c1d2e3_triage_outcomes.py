"""triage outcomes

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-09-24

Slice 06 (docs/phase-2/06-triage-outcomes.md):

- ``issue_subscribers`` — who hears an item's Support-audience events. Every
  existing item is backfilled with its reporter (reason ``reporter``).
- ``regression_history.release_id`` becomes nullable and gains ``source``
  (``action`` | ``merge``, existing rows ``action``) — a merge into a Done bug
  records a regression cycle even without a release (BR-49, D12).

Downgrade drops the release-less cycles: the NOT NULL column can't hold them.

Written by hand, following e7f8a9b0c1d2's lead.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'issue_subscribers',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('issue_id', sa.Integer(), sa.ForeignKey('issues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reason', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('issue_id', 'user_id', name='uq_issue_subscribers_issue_user'),
    )
    op.create_index('ix_issue_subscribers_issue_id', 'issue_subscribers', ['issue_id'])
    op.create_index('ix_issue_subscribers_user_id', 'issue_subscribers', ['user_id'])
    # Idempotent backfill: every item's reporter, once.
    op.execute(
        """
        INSERT INTO issue_subscribers (issue_id, user_id, reason, created_at)
        SELECT id, reporter_id, 'reporter', created_at FROM issues
        WHERE reporter_id IS NOT NULL
        ON CONFLICT (issue_id, user_id) DO NOTHING
        """
    )

    op.alter_column('regression_history', 'release_id', existing_type=sa.Integer(), nullable=True)
    op.add_column('regression_history', sa.Column(
        'source', sa.String(length=16), nullable=False, server_default='action',
    ))
    op.alter_column('regression_history', 'source', existing_type=sa.String(length=16), server_default=None)


def downgrade() -> None:
    op.drop_column('regression_history', 'source')
    op.execute("DELETE FROM regression_history WHERE release_id IS NULL")
    op.alter_column('regression_history', 'release_id', existing_type=sa.Integer(), nullable=False)

    op.drop_index('ix_issue_subscribers_user_id', table_name='issue_subscribers')
    op.drop_index('ix_issue_subscribers_issue_id', table_name='issue_subscribers')
    op.drop_table('issue_subscribers')
