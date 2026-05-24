"""User profile schemas."""

from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.user import UserRole


class UserResponse(BaseModel):
    """User profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    username: str
    role: UserRole
    title: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    avatar_color: str
    telegram_handle: Optional[str] = None
    is_active: bool
    created_at: datetime


class ProfileUpdateRequest(BaseModel):
    """Payload for PUT /me/profile."""

    name: Optional[str] = Field(None, max_length=255)
    username: Optional[str] = Field(None, max_length=64)
    title: Optional[str] = Field(None, max_length=255)
    bio: Optional[str] = Field(None, max_length=2000)
    avatar_url: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)


class AvatarPresignRequest(BaseModel):
    """Payload for POST /me/avatar/presign to request presigned URL."""

    filename: str = Field(..., max_length=255)
    mime_type: str = Field(..., description="MIME type, e.g., image/jpeg")


class AvatarPresignResponse(BaseModel):
    """Response with presigned S3 URL for avatar upload."""

    upload_url: str
    fields: dict
    s3_key: str
    file_id: str
    public_url: Optional[str] = None
    expires_in_seconds: int


class AvatarConfirmRequest(BaseModel):
    """Payload for POST /me/avatar/confirm to finalize upload."""

    s3_key: str
    delete_old: bool = Field(True, description="Delete the old avatar from S3")


# Legacy schemas for backward compatibility
class AvatarUploadRequest(BaseModel):
    """Legacy payload for POST /me/avatar to request presigned URL.

    Deprecated: Use AvatarPresignRequest instead.
    """

    file_name: str = Field(..., max_length=255)
    content_type: str = Field(..., pattern=r"^image/")
    file_size_bytes: int = Field(..., gt=0, le=10_000_000)


class AvatarUploadResponse(BaseModel):
    """Legacy response with presigned S3 URL.

    Deprecated: Use AvatarPresignResponse instead.
    """

    upload_url: str
    s3_key: str
