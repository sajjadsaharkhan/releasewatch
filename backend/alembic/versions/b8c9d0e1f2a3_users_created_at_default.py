"""users.created_at defaults to the insert time (TASK-575).

The column's default was the literal string ``'now()'``, which Postgres turns
into a timestamp once — when the table was created — so every user carried
that moment instead of when they joined. What's new counts a note published no
later than the day someone joined as seen, so it needs the real join time.
Only the default changes: existing rows keep their (frozen) value, which reads
as "joined long ago" and so still shows them every note.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-24
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN created_at SET DEFAULT now()")


def downgrade() -> None:
    # The original definition: the string 'now()', frozen when this runs.
    op.execute("ALTER TABLE users ALTER COLUMN created_at SET DEFAULT 'now()'")
