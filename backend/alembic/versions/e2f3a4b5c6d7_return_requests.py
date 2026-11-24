"""Return requests — Support's Problem is back (slice 20, PRD v3.1 §8.10)

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-11-24

Two new tables and nothing else: ``return_requests`` (one row per request,
with a partial unique index so an item has at most one Pending request,
BR-69) and ``return_request_entries`` (one row per press of Problem is back).
Statuses, the new timeline / inbox event types and the new subscription
reason are plain strings, so they need no DDL. No data moves.

Down drops both tables (and with them any recorded requests).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "return_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("requested_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_comment_id", sa.Integer(), sa.ForeignKey("issue_timeline.id", ondelete="SET NULL"), nullable=True),
        sa.Column("start_comment_id", sa.Integer(), sa.ForeignKey("issue_timeline.id", ondelete="SET NULL"), nullable=True),
        sa.Column("via_mcp_token_id", sa.Integer(), sa.ForeignKey("mcp_tokens.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_return_requests_issue_id", "return_requests", ["issue_id"])
    op.create_index(
        "uq_return_requests_one_pending", "return_requests", ["issue_id"],
        unique=True, postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_table(
        "return_request_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("return_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("comment_id", sa.Integer(), sa.ForeignKey("issue_timeline.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_return_request_entries_request_id", "return_request_entries", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_return_request_entries_request_id", table_name="return_request_entries")
    op.drop_table("return_request_entries")
    op.drop_index("uq_return_requests_one_pending", table_name="return_requests")
    op.drop_index("ix_return_requests_issue_id", table_name="return_requests")
    op.drop_table("return_requests")
