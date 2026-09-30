"""Personal queue (slice 10)

Revision ID: f2a3b4c5d6e7
Revises: d0e1f2a3b4c5
Create Date: 2026-09-30

docs/phase-2/10-personal-queue.md.

- ``queue_entries`` — one per queued item; ``position`` orders it within its
  group (pinned or rest); ``left_at`` marks a dormant entry (the item is Done).
- ``queue_history`` — the owner's append-only record of reorders, pins, unpins.
- ``issues.due_soon_notified_at`` / ``issues.overdue_notified_at`` — the
  assignee's due-date notices, once each.
- Backfill: every assignable user's open board-status items, in default order
  (priority, due date with none last, more reports first, oldest first).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("issues", sa.Column("due_soon_notified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("issues", sa.Column("overdue_notified_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "queue_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Float(precision=53), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pinned_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pin_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("issue_id", name="uq_queue_entries_issue_id"),
    )
    op.create_index("ix_queue_entries_user_active", "queue_entries", ["user_id", "left_at"])

    op.create_table(
        "queue_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="SET NULL"), nullable=True),
        sa.Column("old_index", sa.Integer(), nullable=True),
        sa.Column("new_index", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_queue_history_user_created", "queue_history", ["user_id", "created_at"])

    op.execute("""
        INSERT INTO queue_entries (user_id, issue_id, position, is_pinned, pin_locked)
        SELECT i.assignee_id, i.id,
               1024.0 * row_number() OVER (
                   PARTITION BY i.assignee_id
                   ORDER BY CASE i.priority
                                WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                                WHEN 'medium' THEN 3 WHEN 'low' THEN 4 ELSE 5 END,
                            i.due_date ASC NULLS LAST,
                            i.recurrence_count DESC,
                            i.created_at ASC,
                            i.id ASC
               ),
               false, false
        FROM issues i
        JOIN users u ON u.id = i.assignee_id
        WHERE i.deleted_at IS NULL
          AND u.role <> 'support'
          AND u.is_active
          AND i.status IN ('todo', 'rejected', 'in_progress', 'to_review', 'in_review', 'blocked')
    """)


def downgrade() -> None:
    op.drop_index("ix_queue_history_user_created", table_name="queue_history")
    op.drop_table("queue_history")
    op.drop_index("ix_queue_entries_user_active", table_name="queue_entries")
    op.drop_table("queue_entries")
    op.drop_column("issues", "overdue_notified_at")
    op.drop_column("issues", "due_soon_notified_at")
