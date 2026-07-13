"""IssueEmbedding ORM model — per-field-group embedding vectors for semantic search."""

from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Canonical field group names
FIELD_GROUPS = ("core", "repro", "talk")


class IssueEmbedding(Base):
    """One embedding vector per (issue, field_group) pair.

    Groups:
      core  — title + description + labels (highest signal, weight 0.55)
      repro — reproduction_steps + env fields + curl_command (weight 0.25)
      talk  — aggregated comment bodies (weight 0.20)

    A content_hash per row lets the indexer skip re-embedding unchanged groups.
    The model column tracks which embedding model produced each vector so stale
    rows can be found quickly after a model change.
    """

    __tablename__ = "issue_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    field_group: Mapped[str] = mapped_column(String(16), nullable=False)
    embedding = mapped_column(Vector(384), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(tz=timezone.utc),
    )

    issue = relationship("Issue", back_populates="embeddings")

    __table_args__ = (
        UniqueConstraint("issue_id", "field_group", "content_hash", name="uq_issue_embeddings_issue_group_hash"),
    )

    def __repr__(self) -> str:
        return f"<IssueEmbedding issue={self.issue_id} group={self.field_group!r}>"
