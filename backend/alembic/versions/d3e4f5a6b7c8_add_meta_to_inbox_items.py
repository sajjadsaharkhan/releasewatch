"""add meta jsonb to inbox_items

Revision ID: d3e4f5a6b7c8
Revises: 2f6a6c816018
Create Date: 2026-05-29 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "2f6a6c816018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("inbox_items", sa.Column("meta", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("inbox_items", "meta")
