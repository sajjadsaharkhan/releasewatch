"""support intake

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-09-23

Slice 05 (docs/phase-2/05-support-intake.md): adds `issues.source`
(internal|support, existing rows internal) and `issues.recurrence_count`
(default 1 — incremented from 06/07), plus the per-project support templates
and their ordered fields. Template field values are never stored as columns
(BR-34): the composed description is the record.

Written by hand, following d6e7f8a9b0c1's lead.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = 'd6e7f8a9b0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── issues: source, recurrence_count ──────────────────────────────────
    # Transient server defaults backfill existing rows, then drop so the ORM
    # defaults are the single source.
    op.add_column('issues', sa.Column(
        'source', sa.String(length=16), nullable=False, server_default='internal',
    ))
    op.add_column('issues', sa.Column(
        'recurrence_count', sa.Integer(), nullable=False, server_default='1',
    ))
    op.create_index('ix_issues_source', 'issues', ['source'])
    op.alter_column('issues', 'source', existing_type=sa.String(length=16), server_default=None)
    op.alter_column('issues', 'recurrence_count', existing_type=sa.Integer(), server_default=None)

    # ── support_templates ────────────────────────────────────────────────────
    op.create_table(
        'support_templates',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            'project_id', sa.Integer(),
            sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True,
        ),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column(
            'created_by_id', sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True,
        ),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(),
        ),
        sa.UniqueConstraint('project_id', 'name', name='uq_support_templates_project_name'),
    )

    # ── support_template_fields ──────────────────────────────────────────────
    op.create_table(
        'support_template_fields',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            'template_id', sa.Integer(),
            sa.ForeignKey('support_templates.id', ondelete='CASCADE'), nullable=False, index=True,
        ),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=120), nullable=False),
        sa.Column('field_type', sa.String(length=16), nullable=False),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('help_text', sa.Text(), nullable=True),
        sa.Column('options', postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint(
            'template_id', 'position', name='uq_support_template_fields_template_position',
            deferrable=True, initially='DEFERRED',
        ),
    )


def downgrade() -> None:
    op.drop_table('support_template_fields')
    op.drop_table('support_templates')
    op.drop_index('ix_issues_source', table_name='issues')
    op.drop_column('issues', 'recurrence_count')
    op.drop_column('issues', 'source')
