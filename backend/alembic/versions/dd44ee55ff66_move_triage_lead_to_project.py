"""move triage_lead from release role to project designation

Revision ID: dd44ee55ff66
Revises: b7c8d9e0f1a2, aa11bb22cc33
Create Date: 2026-08-03

Merges: b7c8d9e0f1a2 (telegram delivery status) + aa11bb22cc33 (per-comment embeddings)
"""
from alembic import op
import sqlalchemy as sa

revision = 'dd44ee55ff66'
down_revision = ('b7c8d9e0f1a2', 'aa11bb22cc33')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Migrate existing triage_lead role users to developer
    op.execute("UPDATE users SET role = 'developer' WHERE role = 'triage_lead'")

    # 2. Add triage_lead_id to projects
    op.add_column(
        'projects',
        sa.Column(
            'triage_lead_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )

    # 3. Drop triage_lead_id from releases
    # PostgreSQL auto-names the FK as releases_triage_lead_id_fkey
    op.drop_constraint('releases_triage_lead_id_fkey', 'releases', type_='foreignkey')
    op.drop_column('releases', 'triage_lead_id')


def downgrade() -> None:
    # Restore triage_lead_id on releases
    op.add_column(
        'releases',
        sa.Column(
            'triage_lead_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )

    # Remove triage_lead_id from projects
    op.drop_constraint('projects_triage_lead_id_fkey', 'projects', type_='foreignkey')
    op.drop_column('projects', 'triage_lead_id')

    # Note: downgrade does NOT restore triage_lead role to users.
