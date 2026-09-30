"""Releases and Stream (slice 09)

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-09-30

docs/phase-2/09-releases-and-stream.md.

- ``releases.overdue_notified_at`` — when the CTOs were told the release passed
  its target ship date; cleared when the date changes.
- ``release_events`` — the release page's Activity tab (lifecycle, dates, items
  added or removed, go/no-go, ship, edits). Separate from item timelines.
- ``inbox_items.issue_id`` becomes nullable and ``inbox_items.release_id`` is
  added, so a notification can be about a release alone (``release_shipped``,
  ``release_overdue``).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a6b7c8d9e0f1"
down_revision: Union[str, None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "releases",
        sa.Column("overdue_notified_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "release_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "release_id", sa.Integer(),
            sa.ForeignKey("releases.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "actor_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_release_events_release_created", "release_events", ["release_id", "created_at"],
    )

    op.alter_column("inbox_items", "issue_id", existing_type=sa.Integer(), nullable=True)
    op.add_column(
        "inbox_items",
        sa.Column(
            "release_id", sa.Integer(),
            sa.ForeignKey("releases.id", ondelete="CASCADE"), nullable=True,
        ),
    )
    op.create_index("ix_inbox_items_release_id", "inbox_items", ["release_id"])


def downgrade() -> None:
    op.drop_index("ix_inbox_items_release_id", table_name="inbox_items")
    op.drop_column("inbox_items", "release_id")
    # Release-only notifications have no issue to point at.
    op.execute("DELETE FROM inbox_items WHERE issue_id IS NULL")
    op.alter_column("inbox_items", "issue_id", existing_type=sa.Integer(), nullable=False)

    op.drop_index("ix_release_events_release_created", table_name="release_events")
    op.drop_table("release_events")
    op.drop_column("releases", "overdue_notified_at")
