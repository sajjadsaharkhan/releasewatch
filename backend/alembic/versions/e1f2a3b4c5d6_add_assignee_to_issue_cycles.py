"""Add assignee_id to issue_cycles for per-cycle rework attribution.

Revision ID: e1f2a3b4c5d6
Revises: d3e4f5a6b7c8
Create Date: 2026-05-30 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "issue_cycles",
        sa.Column(
            "assignee_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_issue_cycles_assignee_id", "issue_cycles", ["assignee_id"])


def downgrade() -> None:
    op.drop_index("ix_issue_cycles_assignee_id", table_name="issue_cycles")
    op.drop_column("issue_cycles", "assignee_id")
