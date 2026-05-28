"""Add issue_cycles table.

Revision ID: f1a2b3c4d5e6
Revises: ea199c990e64
Create Date: 2026-05-27 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "9e11df4f3c48"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "issue_cycles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "issue_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("issues.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cycle_number", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column(
            "regression_history_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("regression_history.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("cycle_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("triaged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fixed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_to_triage_h", sa.Float(), nullable=True),
        sa.Column("time_to_fix_h", sa.Float(), nullable=True),
        sa.Column("time_to_verify_h", sa.Float(), nullable=True),
    )
    op.create_index("ix_issue_cycles_issue_id", "issue_cycles", ["issue_id"])


def downgrade() -> None:
    op.drop_index("ix_issue_cycles_issue_id", table_name="issue_cycles")
    op.drop_table("issue_cycles")
