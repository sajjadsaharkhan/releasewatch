"""Timestamp columns default to the insert time.

Like ``users.created_at`` (b8c9d0e1f2a3), these defaulted to the literal string
``'now()'``, which Postgres turns into one timestamp when the table is created —
so every project, release, label and attachment written without an explicit
time carries that moment. Only the defaults change: rows already written keep
their value (the real times can't be recovered).

Revision ID: c0d1e2f3a4b5
Revises: b8c9d0e1f2a3
Create Date: 2026-10-24
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'c0d1e2f3a4b5'
down_revision: Union[str, None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (
    ("issues", "created_at"),
    ("issues", "updated_at"),
    ("issue_attachments", "created_at"),
    ("labels", "created_at"),
    ("projects", "created_at"),
    ("releases", "created_at"),
    ("releases", "updated_at"),
)


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT now()")


def downgrade() -> None:
    # The original definition: the string 'now()', frozen when this runs.
    for table, column in _COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT 'now()'")
