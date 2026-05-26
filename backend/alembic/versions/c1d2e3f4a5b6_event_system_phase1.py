"""Add environment_name to issues; rename inbox fix_ready to fixed; add new inbox event types

Revision ID: c1d2e3f4a5b6
Revises: a1b2c3d4e5f6
Create Date: 2026-05-25 00:00:00.000000

Changes:
- issues.environment_name VARCHAR(32) nullable (production|staging|development|local|qa)
- inbox_items: data-migrate event_type 'fix_ready' -> 'fixed'
  (event_type is VARCHAR(32), no native enum to ALTER — just a data update)
- No DDL needed for new TimelineEventType or InboxEventType string values
  since both columns are VARCHAR(32) and accept any string.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add environment_name to issues
    op.add_column('issues', sa.Column('environment_name', sa.String(length=32), nullable=True))

    # Rename fix_ready → fixed in inbox_items (data migration)
    op.execute("UPDATE inbox_items SET event_type = 'fixed' WHERE event_type = 'fix_ready'")


def downgrade() -> None:
    op.execute("UPDATE inbox_items SET event_type = 'fix_ready' WHERE event_type = 'fixed'")
    op.drop_column('issues', 'environment_name')
