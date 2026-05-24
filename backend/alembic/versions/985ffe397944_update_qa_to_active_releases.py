"""update_qa_to_active_releases

Revision ID: 985ffe397944
Revises: 40ed5c82016a
Create Date: 2026-05-24 12:23:12.968356
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '985ffe397944'
down_revision: Union[str, None] = '40ed5c82016a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update any existing 'qa' status releases to 'active'
    op.execute(
        sa.text("UPDATE releases SET status = 'active' WHERE status = 'qa'")
    )


def downgrade() -> None:
    # Revert 'active' releases back to 'qa' (only those that were originally 'qa')
    # Note: This is a best-effort revert since we can't distinguish which were originally 'qa'
    op.execute(
        sa.text("UPDATE releases SET status = 'qa' WHERE status = 'active'")
    )
