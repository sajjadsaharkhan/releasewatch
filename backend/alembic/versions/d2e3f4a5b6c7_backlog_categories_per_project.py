"""backlog categories per project

Revision ID: d2e3f4a5b6c7
Revises: b0c1d2e3f4a5
Create Date: 2026-09-28

Slice 08 follow-up (2026-09-28 decisions): backlog categories become rows a
project owns instead of a fixed three-value enum.

- ``backlog_categories`` — per project: name, icon, color, position,
  ``is_default``. One fixed Default per project (partial unique index); names
  unique per project ignoring case.
- Every existing project gets its Default; every existing issue points at its
  project's Default (nothing is in production yet, so the old three values are
  not carried over — 2026-09-28).
- ``issues.backlog_category_id`` NOT NULL with a composite FK
  ``(project_id, backlog_category_id)`` → ``backlog_categories (project_id, id)``:
  an issue can only ever use a category of its own project.
- ``issues.backlog_category`` (the enum string) is dropped.

New projects get their Default from an ORM ``after_insert`` hook
(``app/db/models/backlog_category.py``).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, None] = 'b0c1d2e3f4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'backlog_categories',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            'project_id', sa.Integer(),
            sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False,
        ),
        sa.Column('name', sa.String(40), nullable=False),
        sa.Column('icon', sa.String(40), nullable=False, server_default='inbox'),
        sa.Column('color', sa.String(16), nullable=False, server_default='zinc'),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.UniqueConstraint('project_id', 'id', name='uq_backlog_categories_project_id_id'),
    )
    op.create_index('ix_backlog_categories_project_id', 'backlog_categories', ['project_id'])
    op.create_index(
        'uq_backlog_categories_one_default', 'backlog_categories', ['project_id'],
        unique=True, postgresql_where=sa.text('is_default'),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_backlog_categories_project_name "
        "ON backlog_categories (project_id, lower(name))"
    )

    op.execute(
        """
        INSERT INTO backlog_categories (project_id, name, icon, color, position, is_default)
        SELECT id, 'Default', 'inbox', 'zinc', 0, true FROM projects
        WHERE NOT EXISTS (
            SELECT 1 FROM backlog_categories c WHERE c.project_id = projects.id AND c.is_default
        )
        """
    )

    op.add_column('issues', sa.Column('backlog_category_id', sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE issues AS i SET backlog_category_id = c.id
        FROM backlog_categories c
        WHERE c.project_id = i.project_id AND c.is_default AND i.backlog_category_id IS NULL
        """
    )
    op.alter_column('issues', 'backlog_category_id', nullable=False)
    op.create_index('ix_issues_backlog_category_id', 'issues', ['backlog_category_id'])
    op.create_foreign_key(
        'fk_issues_backlog_category_same_project', 'issues', 'backlog_categories',
        ['project_id', 'backlog_category_id'], ['project_id', 'id'],
        onupdate='CASCADE',
    )
    op.drop_column('issues', 'backlog_category')


def downgrade() -> None:
    op.add_column('issues', sa.Column('backlog_category', sa.String(32), nullable=True))
    op.drop_constraint('fk_issues_backlog_category_same_project', 'issues', type_='foreignkey')
    op.drop_index('ix_issues_backlog_category_id', table_name='issues')
    op.drop_column('issues', 'backlog_category_id')
    op.drop_table('backlog_categories')
