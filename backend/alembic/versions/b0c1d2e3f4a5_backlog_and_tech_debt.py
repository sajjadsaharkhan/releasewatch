"""backlog and technical debt

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-09-24

Slice 08 (docs/phase-2/08-backlog-and-tech-debt.md, FR-23–29, BR-04–06, BR-36):

- ``issues.backlog_category`` — feature_request | improvement | future_work.
  Kept when the item leaves the backlog, so a demoted item gets it back.
- ``issues.backlog_rank`` — midpoint-ranked position in its project's backlog.
  Also kept when the item leaves.
- ``issues.is_tech_debt`` — the technical-debt flag (tasks only, BR-36).

Backlog membership is derived, never stored (BR-04). Items that are already
backlog members get ranks in created order (1024 apart, per project); their
category stays null ("Uncategorized") until someone sets one.

Written by hand, following e7f8a9b0c1d2's lead.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b0c1d2e3f4a5'
down_revision: Union[str, None] = 'a9b0c1d2e3f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('issues', sa.Column('backlog_category', sa.String(32), nullable=True))
    op.add_column('issues', sa.Column('backlog_rank', sa.Float(precision=53), nullable=True))
    op.add_column(
        'issues',
        sa.Column('is_tech_debt', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index('ix_issues_project_backlog_rank', 'issues', ['project_id', 'backlog_rank'])
    op.create_index(
        'ix_issues_is_tech_debt', 'issues', ['is_tech_debt'],
        postgresql_where=sa.text('is_tech_debt'),
    )

    # Idempotent: only rows without a rank are touched.
    op.execute(
        """
        UPDATE issues AS i
        SET backlog_rank = ranked.rn * 1024
        FROM (
            SELECT id, row_number() OVER (
                PARTITION BY project_id ORDER BY created_at, id
            ) AS rn
            FROM issues
            WHERE backlog_rank IS NULL
              AND release_id IS NULL
              AND deleted_at IS NULL
              AND status IN ('todo', 'in_progress', 'in_review', 'blocked')
        ) AS ranked
        WHERE i.id = ranked.id
        """
    )


def downgrade() -> None:
    op.drop_index('ix_issues_is_tech_debt', table_name='issues')
    op.drop_index('ix_issues_project_backlog_rank', table_name='issues')
    op.drop_column('issues', 'is_tech_debt')
    op.drop_column('issues', 'backlog_rank')
    op.drop_column('issues', 'backlog_category')
