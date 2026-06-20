"""Add semantic search: pgvector extension, issue_embeddings table, issues.search_tsv

Revision ID: a0b1c2d3e4f5
Revises: f1g2h3i4j5k6
Create Date: 2026-06-20 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, None] = "f1g2h3i4j5k6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # issue_embeddings — one row per (issue, field_group); dim=1536 matches
    # text-embedding-3-small default. Changing dim requires a managed reindex
    # (see SEMANTIC_SEARCH_PLAN.md §6).
    op.execute("""
        CREATE TABLE issue_embeddings (
            id          bigserial PRIMARY KEY,
            issue_id    integer NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
            project_id  integer NOT NULL,
            field_group varchar(16) NOT NULL,
            embedding   vector(1536) NOT NULL,
            content_hash varchar(64) NOT NULL,
            model       varchar(128) NOT NULL,
            updated_at  timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_issue_embeddings_issue_group UNIQUE (issue_id, field_group)
        )
    """)

    op.execute("CREATE INDEX ix_issue_embeddings_issue_id  ON issue_embeddings (issue_id)")
    op.execute("CREATE INDEX ix_issue_embeddings_project_id ON issue_embeddings (project_id)")

    # HNSW index for fast approximate nearest-neighbour with cosine distance.
    # Prefer HNSW over ivfflat at this scale (no min-rows requirement for good recall).
    op.execute(
        "CREATE INDEX issue_embeddings_hnsw "
        "ON issue_embeddings USING hnsw (embedding vector_cosine_ops)"
    )

    # Full-text search column on issues — weights title (A) over description (B).
    # GENERATED ALWAYS AS STORED means Postgres maintains it automatically.
    op.execute("""
        ALTER TABLE issues ADD COLUMN search_tsv tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(title,'')), 'A') ||
            setweight(to_tsvector('english', coalesce(description,'')), 'B')
        ) STORED
    """)

    op.execute("CREATE INDEX ix_issues_search_tsv ON issues USING GIN (search_tsv)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_issues_search_tsv")
    op.execute("ALTER TABLE issues DROP COLUMN IF EXISTS search_tsv")
    op.execute("DROP TABLE IF EXISTS issue_embeddings")
    op.execute("DROP EXTENSION IF EXISTS vector")
