"""Search engine tables (slice 12, engine PRD Appendix A.4).

Derived data only (principle S5, BR-S15): every row can be rebuilt from the
items and their timelines by ``reindex_all``. Written only by
``app/tasks/search_index.py``.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: bge-m3's dense vector size. Another size needs a vector-dimension migration
#: (the e5-base fallback in 12's Further Notes is 768).
EMBEDDING_DIM = 1024


class SearchItem(Base):
    """One per indexed item: its filter columns and its folded keyword text."""

    __tablename__ = "search_items"
    __table_args__ = (
        Index(
            "ix_search_items_keyword_trgm",
            "keyword_text",
            postgresql_using="gin",
            postgresql_ops={"keyword_text": "gin_trgm_ops"},
        ),
    )

    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="CASCADE"), primary_key=True
    )
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Copied like the other filter columns (03a); never indexed as text.
    priority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    keyword_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    keyword_hash: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    #: The model the item's vectors came from; retrieval only reads rows of the
    #: model that embedded the query (BR-S16).
    embed_model: Mapped[str] = mapped_column(String(256), nullable=False)
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SearchVector(Base):
    """One embedded text: an item's title, one body chunk, or one used comment."""

    __tablename__ = "search_vectors"
    __table_args__ = (
        Index("ix_search_vectors_issue_kind", "issue_id", "kind"),
        Index(
            "ix_search_vectors_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False
    )
    #: ``title`` | ``body`` | ``talk``.
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    chunk_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timeline_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issue_timeline.id", ondelete="CASCADE"), nullable=True
    )
    #: Talk rows from internal notes; Support's queries skip them (BR-S06).
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    content_hash: Mapped[str] = mapped_column(String(32), nullable=False)
    embed_model: Mapped[str] = mapped_column(String(256), nullable=False)
    embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=False)


class CommentLabel(Base):
    """Whether a comment is used for search, and who decided (BR-S14)."""

    __tablename__ = "comment_labels"

    timeline_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issue_timeline.id", ondelete="CASCADE"), primary_key=True
    )
    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: this_problem | other_problem | process | ack | rule_kept | rule_dropped
    label: Mapped[str] = mapped_column(String(16), nullable=False)
    #: jev | rule
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(32), nullable=False)
    jev_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    classified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DuplicateHint(Base):
    """A stored possible duplicate of a New bug (slice 14, A.4, FR-S12).

    Written only by ``compute_duplicate_hints`` — replaced wholesale on each
    computation, never more than ``DUPLICATE_HINT_LIMIT`` rows. A dismissed
    pair is never stored again (BR-S12): dismissals live on in their own table.
    """

    __tablename__ = "duplicate_hints"
    __table_args__ = (
        UniqueConstraint("issue_id", "candidate_id", name="uq_duplicate_hints_pair"),
        Index("ix_duplicate_hints_issue", "issue_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False
    )
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    jev_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DuplicateDismissal(Base):
    """A triage lead's "Not a duplicate" — forever (slice 14, BR-S12, AC-S12).

    Never deleted by jobs, so a reindex or recomputation cannot bring the pair
    back. ``PK (issue_id, candidate_id)``: one dismissal per pair.
    """

    __tablename__ = "duplicate_dismissals"

    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="CASCADE"), primary_key=True
    )
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="CASCADE"), primary_key=True
    )
    dismissed_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    dismissed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
