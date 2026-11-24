"""Support channel — per-project Telegram topic (slice 21, PRD v3.1 §8.11)

Revision ID: a4b5c6d7e8f9
Revises: e2f3a4b5c6d7
Create Date: 2026-11-24

Four nullable/defaulted columns on ``projects`` (chat id, topic id, enabled,
tested-at) and one new table, ``support_channel_posts`` — the outbox the
channel's posts are written to and sent from. No data moves: every project
starts with the channel off.

Down drops the table and the four columns (and with them any channel config).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("support_chat_id", sa.BigInteger(), nullable=True))
    op.add_column("projects", sa.Column("support_thread_id", sa.Integer(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("support_channel_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "projects", sa.Column("support_channel_tested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "support_channel_posts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=True),
        sa.Column("batch_id", sa.String(64), nullable=True),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("first_status", sa.String(24), nullable=True),
        sa.Column("last_status", sa.String(24), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_support_channel_posts_project_id", "support_channel_posts", ["project_id"])
    op.create_index(
        "ix_support_channel_posts_due", "support_channel_posts", ["not_before"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    # One batch row per (project, batch).
    op.create_index(
        "uq_support_channel_posts_batch", "support_channel_posts", ["project_id", "batch_id"],
        unique=True, postgresql_where=sa.text("batch_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_support_channel_posts_batch", table_name="support_channel_posts")
    op.drop_index("ix_support_channel_posts_due", table_name="support_channel_posts")
    op.drop_index("ix_support_channel_posts_project_id", table_name="support_channel_posts")
    op.drop_table("support_channel_posts")
    op.drop_column("projects", "support_channel_tested_at")
    op.drop_column("projects", "support_channel_enabled")
    op.drop_column("projects", "support_thread_id")
    op.drop_column("projects", "support_chat_id")
