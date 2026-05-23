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


class AvatarUploadRequest(BaseModel):
    """Payload for POST /me/avatar to request presigned URL."""

    file_name: str = Field(..., max_length=255)
    content_type: str = Field(..., pattern=r"^image/")
    file_size_bytes: int = Field(..., gt=0, le=10_000_000)


class AvatarUploadResponse(BaseModel):
    """Response with presigned S3 URL."""

    upload_url: str
    s3_key: str
