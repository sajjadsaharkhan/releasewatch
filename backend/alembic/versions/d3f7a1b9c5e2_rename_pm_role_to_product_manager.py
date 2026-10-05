"""Rename the ``pm`` role to ``product_manager``.

The role is a plain string column, so this is a data-only change. The
duplicate-detection dataset's ``dd-pm`` user (if present) follows the role.

Revision ID: d3f7a1b9c5e2
Revises: c5e9f3a7b2d1
Create Date: 2026-10-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd3f7a1b9c5e2'
down_revision: Union[str, None] = 'c5e9f3a7b2d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE users SET role = 'product_manager' WHERE role = 'pm'")
    op.execute("UPDATE users SET username = 'dd-product_manager' WHERE username = 'dd-pm'")


def downgrade() -> None:
    op.execute("UPDATE users SET role = 'pm' WHERE role = 'product_manager'")
    op.execute("UPDATE users SET username = 'dd-pm' WHERE username = 'dd-product_manager'")
