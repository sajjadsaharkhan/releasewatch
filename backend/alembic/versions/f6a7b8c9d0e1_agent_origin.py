"""Agent origin (slice 17, prd-mcp.md A.3).

``via_mcp_token_id`` on items, timeline entries and attachments: the MCP token
the row was created through. Agent content = the column is set. The token row
is never deleted (slice 15), so ``RESTRICT`` keeps the audit trail intact.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("issues", "issue_timeline", "issue_attachments")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("via_mcp_token_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_via_mcp_token_id", table, "mcp_tokens",
            ["via_mcp_token_id"], ["id"], ondelete="RESTRICT",
        )
    op.create_index(
        "ix_issues_agent", "issues", ["project_id"],
        postgresql_where=sa.text("via_mcp_token_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_issues_agent", table_name="issues")
    for table in reversed(_TABLES):
        op.drop_constraint(f"fk_{table}_via_mcp_token_id", table, type_="foreignkey")
        op.drop_column(table, "via_mcp_token_id")
