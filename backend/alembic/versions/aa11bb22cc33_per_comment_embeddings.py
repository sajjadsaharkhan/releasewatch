"""Per-comment embeddings: change unique constraint to (issue_id, field_group, content_hash).

Revision ID: aa11bb22cc33
Revises: b2c3d4e5f6a7
Create Date: 2026-06-20
"""

from alembic import op

revision = "aa11bb22cc33"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_issue_embeddings_issue_group", "issue_embeddings", type_="unique")
    op.create_unique_constraint(
        "uq_issue_embeddings_issue_group_hash",
        "issue_embeddings",
        ["issue_id", "field_group", "content_hash"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_issue_embeddings_issue_group_hash", "issue_embeddings", type_="unique")
    op.create_unique_constraint(
        "uq_issue_embeddings_issue_group",
        "issue_embeddings",
        ["issue_id", "field_group"],
    )
