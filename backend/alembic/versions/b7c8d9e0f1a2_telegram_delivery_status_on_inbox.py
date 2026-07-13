"""Add Telegram delivery tracking columns to inbox_items.

Revision ID: a1b2c3d4e5f6
Revises: ff44aa55bb66
Create Date: 2026-07-13 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "ff44aa55bb66"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "inbox_items",
        sa.Column("telegram_status", sa.String(16), nullable=True),
    )
    op.add_column(
        "inbox_items",
        sa.Column(
            "telegram_retry_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "inbox_items",
        sa.Column("telegram_next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "inbox_items",
        sa.Column("telegram_error", sa.String(512), nullable=True),
    )

    # Partial index — only rows that still need delivery attention
    op.create_index(
        "ix_inbox_items_telegram_pending",
        "inbox_items",
        ["telegram_status", "telegram_next_retry_at"],
        postgresql_where=sa.text("telegram_status IN ('pending', 'failed')"),
    )


def downgrade() -> None:
    op.drop_index("ix_inbox_items_telegram_pending", table_name="inbox_items")
    op.drop_column("inbox_items", "telegram_error")
    op.drop_column("inbox_items", "telegram_next_retry_at")
    op.drop_column("inbox_items", "telegram_retry_count")
    op.drop_column("inbox_items", "telegram_status")
