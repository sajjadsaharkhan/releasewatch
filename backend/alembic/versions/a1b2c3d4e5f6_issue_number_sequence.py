"""Add global issue_number sequence starting at 10

Revision ID: a1b2c3d4e5f6
Revises: ea199c990e64
Create Date: 2026-05-24 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'b66da6523f3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS issue_number_seq START WITH 10 INCREMENT BY 1")
    # Advance the sequence past any existing issue_number values
    op.execute("""
        SELECT setval('issue_number_seq',
            GREATEST(10, COALESCE((SELECT MAX(issue_number) FROM issues), 9))
        )
    """)
    op.execute("ALTER TABLE issues ALTER COLUMN issue_number SET DEFAULT nextval('issue_number_seq')")


def downgrade() -> None:
    op.execute("ALTER TABLE issues ALTER COLUMN issue_number DROP DEFAULT")
    op.execute("DROP SEQUENCE IF EXISTS issue_number_seq")
