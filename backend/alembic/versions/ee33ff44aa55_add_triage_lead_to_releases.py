"""add triage_lead_id to releases

Revision ID: ee33ff44aa55
Revises: dd22ee33ff44
Create Date: 2026-06-22

"""
from alembic import op
import sqlalchemy as sa

revision = 'ee33ff44aa55'
down_revision = 'dd22ee33ff44'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'releases',
        sa.Column(
            'triage_lead_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('releases', 'triage_lead_id')
