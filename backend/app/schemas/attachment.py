"""Attachment schemas."""

from datetime import datetime
from typing import Optional
import uuid

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
    expires_in_seconds: int


class ConfirmRequest(BaseModel):
    """Payload for POST /issues/{id}/attachments/confirm — finalise an upload."""

    s3_key: str
    filename: str = Field(max_length=512)
    mime_type: str = Field(max_length=128)
    file_size_bytes: Optional[int] = None
    attachment_type: AttachmentType = AttachmentType.other


class AttachmentResponse(BaseModel):
    """Attachment metadata with an ephemeral download URL."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_id: uuid.UUID
    uploaded_by_id: Optional[uuid.UUID] = None
    file_name: str
    s3_key: str
    mime_type: str
    file_size_bytes: Optional[int] = None
    attachment_type: AttachmentType
    download_url: Optional[str] = None  # Populated on retrieval, not stored
    created_at: datetime
