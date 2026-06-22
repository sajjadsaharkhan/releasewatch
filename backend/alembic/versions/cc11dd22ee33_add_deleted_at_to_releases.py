"""Add deleted_at to releases for soft-delete support.

Revision ID: cc11dd22ee33
Revises: aa11bb22cc33
Create Date: 2026-06-22 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "cc11dd22ee33"
down_revision: Union[str, None] = "aa11bb22cc33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "releases",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("releases", "deleted_at")
