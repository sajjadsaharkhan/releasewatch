"""Switch issue_embeddings to 384-dim for local ONNX model (bge-small-en-v1.5).

Revision ID: b2c3d4e5f6a7
Revises: a0b1c2d3e4f5
Create Date: 2026-06-20

Vectors from the previous model (1536-dim) are incompatible with 384-dim space,
so the table is truncated — a reindex will repopulate it with the local model.
"""

from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("TRUNCATE issue_embeddings")
    op.execute("DROP INDEX IF EXISTS issue_embeddings_hnsw")
    op.execute("ALTER TABLE issue_embeddings ALTER COLUMN embedding TYPE vector(384)")
    op.execute(
        "CREATE INDEX issue_embeddings_hnsw "
        "ON issue_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("TRUNCATE issue_embeddings")
    op.execute("DROP INDEX IF EXISTS issue_embeddings_hnsw")
    op.execute("ALTER TABLE issue_embeddings ALTER COLUMN embedding TYPE vector(1536)")
    op.execute(
        "CREATE INDEX issue_embeddings_hnsw "
        "ON issue_embeddings USING hnsw (embedding vector_cosine_ops)"
    )
