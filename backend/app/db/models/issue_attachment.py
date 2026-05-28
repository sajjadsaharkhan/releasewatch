"""IssueAttachment ORM model — files uploaded against an issue."""

import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AttachmentType(str, enum.Enum):
    """High-level category of the uploaded artefact."""

    screenshot = "screenshot"
    recording = "recording"
    log = "log"
    curl_export = "curl_export"
    other = "other"


class IssueAttachment(Base):
    """Reference to a file stored in S3, scoped to an issue.

    The actual binary is never stored in the database; only the S3 key and
    metadata are persisted here.  Pre-signed download URLs are generated on
    demand by ``S3Service``.
    """

    __tablename__ = "issue_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    s3_key: Mapped[str] = mapped_column(
        String(1024), nullable=False, unique=True,
        doc="Full S3 object key including path prefix."
    )
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    attachment_type: Mapped[AttachmentType] = mapped_column(
        String(32), nullable=False, default=AttachmentType.other
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    issue = relationship("Issue", back_populates="attachments")
    uploader = relationship("User", foreign_keys=[uploaded_by_id])

    def __repr__(self) -> str:
        return f"<IssueAttachment id={self.id} file={self.file_name!r} type={self.attachment_type}>"
