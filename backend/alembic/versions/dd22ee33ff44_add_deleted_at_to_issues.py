"""Add deleted_at to issues for soft-delete support.

Revision ID: dd22ee33ff44
Revises: cc11dd22ee33
Create Date: 2026-06-22 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "dd22ee33ff44"
down_revision: Union[str, None] = "cc11dd22ee33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "issues",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("issues", "deleted_at")
