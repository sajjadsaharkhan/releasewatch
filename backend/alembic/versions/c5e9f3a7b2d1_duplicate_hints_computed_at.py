"""when a New bug's duplicate hints were last computed

Revision ID: c5e9f3a7b2d1
Revises: b4d8e2f6a1c9
Create Date: 2026-10-02

``issues.duplicate_hints_computed_at`` is set by every successful hint run,
including one that finds nothing. Null means "never judged" — opening such a
New bug asks for a run, so hints appear on open even for bugs filed before Jev
was switched on. Existing New bugs that already have stored hints are stamped
so they are not recomputed; the rest stay null.

Written by hand.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c5e9f3a7b2d1'
down_revision: Union[str, None] = 'b4d8e2f6a1c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('issues', sa.Column('duplicate_hints_computed_at', sa.DateTime(timezone=True), nullable=True))
    op.execute("""
        UPDATE issues SET duplicate_hints_computed_at = now()
        WHERE id IN (SELECT DISTINCT issue_id FROM duplicate_hints)
    """)


def downgrade() -> None:
    op.drop_column('issues', 'duplicate_hints_computed_at')
