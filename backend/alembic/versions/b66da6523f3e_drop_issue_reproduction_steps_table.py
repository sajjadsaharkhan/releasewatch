"""drop_issue_reproduction_steps_table

Revision ID: b66da6523f3e
Revises: 4df586727a4d
Create Date: 2026-05-24 13:27:16.401773
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b66da6523f3e'
down_revision: Union[str, None] = '4df586727a4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the issue_reproduction_steps table - no longer needed, steps stored as JSON on issues
    op.drop_table('issue_reproduction_steps')


def downgrade() -> None:
    # Recreate the table if rolling back
    op.create_table(
        'issue_reproduction_steps',
        sa.Column('id', postgresql.UUID(), autoincrement=False, nullable=False),
        sa.Column('issue_id', postgresql.UUID(), autoincrement=False, nullable=False),
        sa.Column('step_order', sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column('description', sa.Text(), autoincrement=False, nullable=False),
        sa.Column('expected_result', sa.Text(), autoincrement=False, nullable=True),
        sa.Column('actual_result', sa.Text(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['issue_id'], ['issues.id'], name='issue_reproduction_steps_issue_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='issue_reproduction_steps_pkey'),
        sa.Index('issue_reproduction_steps_issue_id_idx', 'issue_id')
    )
