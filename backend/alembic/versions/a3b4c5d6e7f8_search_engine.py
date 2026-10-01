"""Search engine tables (slice 12)

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-10-01

docs/phase-2/12-search-engine-core.md, engine PRD Appendix A.4.

- ``pg_trgm`` for the keyword channel.
- ``search_items`` — filter columns + folded keyword text (GIN trigram index).
- ``search_vectors`` — title / body-chunk / talk vectors, ``vector(1024)`` for
  bge-m3 (HNSW cosine index).
- ``comment_labels`` — whether a comment is used for search, and by what rule.

All three hold derived data, rebuilt by ``reindex_all``. Downgrade drops them.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "search_items",
        sa.Column(
            "issue_id",
            sa.Integer(),
            sa.ForeignKey("issues.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("priority", sa.String(16), nullable=True),
        sa.Column("is_cancelled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("keyword_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("keyword_hash", sa.String(32), nullable=False, server_default=""),
        sa.Column("embed_model", sa.String(256), nullable=False),
        sa.Column(
            "indexed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_search_items_project_id", "search_items", ["project_id"])
    op.create_index(
        "ix_search_items_keyword_trgm",
        "search_items",
        ["keyword_text"],
        postgresql_using="gin",
        postgresql_ops={"keyword_text": "gin_trgm_ops"},
    )

    op.create_table(
        "search_vectors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("chunk_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "timeline_id",
            sa.Integer(),
            sa.ForeignKey("issue_timeline.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("content_hash", sa.String(32), nullable=False),
        sa.Column("embed_model", sa.String(256), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.CheckConstraint("kind IN ('title', 'body', 'talk')", name="ck_search_vectors_kind"),
    )
    op.create_index("ix_search_vectors_issue_kind", "search_vectors", ["issue_id", "kind"])
    op.create_index(
        "ix_search_vectors_embedding_hnsw",
        "search_vectors",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "comment_labels",
        sa.Column(
            "timeline_id",
            sa.Integer(),
            sa.ForeignKey("issue_timeline.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("label", sa.String(16), nullable=False),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("content_hash", sa.String(32), nullable=False),
        sa.Column("jev_model", sa.String(64), nullable=True),
        sa.Column(
            "classified_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "label IN ('this_problem', 'other_problem', 'process', 'ack', 'rule_kept', 'rule_dropped')",
            name="ck_comment_labels_label",
        ),
        sa.CheckConstraint("source IN ('jev', 'rule')", name="ck_comment_labels_source"),
    )
    op.create_index("ix_comment_labels_issue_id", "comment_labels", ["issue_id"])


def downgrade() -> None:
    op.drop_table("comment_labels")
    op.drop_table("search_vectors")
    op.drop_table("search_items")
