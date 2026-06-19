"""Create telegram_integrations table and migrate data from users.

Revision ID: f1g2h3i4j5k6
Revises: e1f2a3b4c5d6
Create Date: 2026-06-16 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1g2h3i4j5k6"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create telegram_integrations table
    op.create_table(
        "telegram_integrations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_username", sa.String(128), nullable=True),
        sa.Column("telegram_full_name", sa.String(256), nullable=True),
        sa.Column("telegram_first_name", sa.String(128), nullable=True),
        sa.Column("telegram_last_name", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_event_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("telegram_user_id"),
    )
    op.create_index("ix_telegram_integrations_user_id", "telegram_integrations", ["user_id"])
    op.create_index(
        "ix_telegram_integrations_telegram_user_id",
        "telegram_integrations",
        ["telegram_user_id"],
    )

    # 2. Backfill from existing users that have telegram_user_id set
    op.execute(
        """
        INSERT INTO telegram_integrations
            (user_id, telegram_user_id, chat_id, telegram_username, created_at, is_active)
        SELECT
            id,
            telegram_user_id,
            telegram_user_id,
            telegram_handle,
            COALESCE(telegram_connected_at, now()),
            true
        FROM users
        WHERE telegram_user_id IS NOT NULL
        """
    )

    # 3. Drop migrated columns from users
    op.drop_index("ix_users_telegram_user_id", table_name="users", if_exists=True)
    op.drop_column("users", "telegram_user_id")
    op.drop_column("users", "telegram_handle")
    op.drop_column("users", "telegram_connected_at")


def downgrade() -> None:
    # 1. Re-add columns to users
    op.add_column(
        "users",
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("telegram_handle", sa.String(128), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("telegram_connected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_telegram_user_id", "users", ["telegram_user_id"], unique=True)

    # 2. Restore data
    op.execute(
        """
        UPDATE users u
        SET
            telegram_user_id = ti.telegram_user_id,
            telegram_handle  = ti.telegram_username,
            telegram_connected_at = ti.created_at
        FROM telegram_integrations ti
        WHERE ti.user_id = u.id
        """
    )

    # 3. Drop new table
    op.drop_index("ix_telegram_integrations_telegram_user_id", table_name="telegram_integrations")
    op.drop_index("ix_telegram_integrations_user_id", table_name="telegram_integrations")
    op.drop_table("telegram_integrations")
