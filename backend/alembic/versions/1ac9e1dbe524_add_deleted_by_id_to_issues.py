"""add_deleted_by_id_to_issues

Revision ID: 1ac9e1dbe524
Revises: dd44ee55ff66
Create Date: 2026-08-03 18:30:15.461788
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '1ac9e1dbe524'
down_revision: Union[str, None] = 'dd44ee55ff66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('issues', sa.Column('deleted_by_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_issues_deleted_by_id_users',
        'issues', 'users',
        ['deleted_by_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_issues_deleted_by_id_users', 'issues', type_='foreignkey')
    op.drop_column('issues', 'deleted_by_id')
