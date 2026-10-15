"""MCP tokens (slice 15, prd-mcp.md A.2).

One table. The kill switch is a ``system_settings`` row written by the
Settings → MCP API; with no row, MCP is off (a new installation starts
disabled, so an Admin turns it on deliberately).

Revision ID: e5f6a7b8c9d0
Revises: d3f7a1b9c5e2
Create Date: 2026-10-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd3f7a1b9c5e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mcp_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("token_hash", sa.CHAR(64), nullable=False),
        sa.Column("token_prefix", sa.String(12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("expiry_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_mcp_tokens_token_hash"),
    )
    op.create_index("ix_mcp_tokens_user_id", "mcp_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_mcp_tokens_user_id", table_name="mcp_tokens")
    op.drop_table("mcp_tokens")
    op.execute("DELETE FROM system_settings WHERE category = 'mcp'")
    # The token notices (``mcp_token_created`` / ``mcp_token_expiring``) are
    # event types the older code doesn't know.
    op.execute("DELETE FROM inbox_items WHERE event_type LIKE 'mcp_token_%'")
