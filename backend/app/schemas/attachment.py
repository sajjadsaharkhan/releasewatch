"""Attachment schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.issue_attachment import AttachmentType


class PresignRequest(BaseModel):
    """Payload for POST /issues/{id}/attachments/presign."""

    filename: str = Field(max_length=512)
    mime_type: str = Field(max_length=128)
    attachment_type: AttachmentType = AttachmentType.other
    max_size_mb: int = Field(50, ge=1, le=500)


class PresignResponse(BaseModel):
    """Pre-signed upload details returned to the client."""

    upload_url: str
    fields: dict
    s3_key: str
    attachment_id: str
    public_url: Optional[str] = None
    expires_in_seconds: int
    is_large_file: bool = Field(
        description="True if file exceeds S3_LARGE_FILE_THRESHOLD_MB and will be auto-deleted"
    )


class ConfirmRequest(BaseModel):
    """Payload for POST /issues/{id}/attachments/confirm — finalise an upload."""

    s3_key: str
    filename: str = Field(max_length=512)
    mime_type: str = Field(max_length=128)
    file_size_bytes: Optional[int] = None
    attachment_type: AttachmentType = AttachmentType.other


class AttachmentResponse(BaseModel):
    """Attachment metadata with a download URL."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    uploaded_by_id: Optional[int] = None
    file_name: str
    s3_key: str
    mime_type: str
    file_size_bytes: Optional[int] = None
    attachment_type: AttachmentType
    download_url: Optional[str] = None  # Populated on retrieval, not stored
    public_url: Optional[str] = None  # Permanent URL if configured
    is_large_file: Optional[bool] = None  # True if subject to auto-deletion
    retention_days: Optional[int] = None  # Days until auto-deletion for large files
    created_at: datetime


class MultipartPresignRequest(BaseModel):
    """Payload for POST /issues/{id}/attachments/multipart/start — start multipart upload."""

    filename: str = Field(max_length=512)
    mime_type: str = Field(max_length=128)
    attachment_type: AttachmentType = AttachmentType.other
    total_size_bytes: int = Field(gt=0)


class MultipartPresignResponse(BaseModel):
    """Response with multipart upload details."""

    upload_id: str
    s3_key: str
    file_id: str
    chunk_size_bytes: int = Field(
        description="Recommended chunk size for multipart upload"
    )


class MultipartPartRequest(BaseModel):
    """Payload for POST /issues/{id}/attachments/multipart/part — get part upload URL."""

    upload_id: str
    part_number: int = Field(ge=1, le=10000)
    s3_key: str


class MultipartPartResponse(BaseModel):
    """Response with pre-signed URL for uploading a part."""

    upload_url: str
    part_url: str


class MultipartCompleteRequest(BaseModel):
    """Payload for POST /issues/{id}/attachments/multipart/complete — finish multipart upload."""

    upload_id: str
    s3_key: str
    parts: list[dict] = Field(
        ...,
        description="List of {part_number: int, etag: str} for each uploaded part"
    )
    filename: str = Field(max_length=512)
    mime_type: str = Field(max_length=128)
    file_size_bytes: int
    attachment_type: AttachmentType = AttachmentType.other


class PendingAttachment(BaseModel):
    """Metadata for a file uploaded before an issue exists.

    Collected on the frontend after each pre-upload and sent as a list
    alongside the IssueCreate payload so the backend can link them atomically.
    """

    s3_key: str
    filename: str = Field(max_length=512)
    mime_type: str = Field(max_length=128)
    file_size_bytes: Optional[int] = None
    attachment_type: AttachmentType = AttachmentType.other
