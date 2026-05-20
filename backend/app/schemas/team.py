"""Team management schemas."""

from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.models.user import UserRole


class TeamMemberResponse(BaseModel):
    """Public profile of a team member."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    username: str
    email: str
    role: UserRole
    avatar_color: str
    telegram_handle: Optional[str] = None
    telegram_connected_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime


class InviteRequest(BaseModel):
    """Payload for POST /team/invite."""

    email: EmailStr
    name: str = Field(max_length=255)
    username: str = Field(max_length=64, pattern=r"^[a-z0-9_.-]+$")
    role: UserRole = UserRole.qa
    temporary_password: str = Field(min_length=12)
    avatar_color: Optional[str] = Field(None, max_length=7, description="Hex colour e.g. #6366f1")


class RoleUpdateRequest(BaseModel):
    """Payload for PATCH /team/{user_id}/role."""

    role: UserRole


# Alias used in route files
ChangeRoleRequest = RoleUpdateRequest


class DeactivateRequest(BaseModel):
    """Payload for PATCH /team/{user_id}/deactivate."""

    deactivate: bool = True
    reason: Optional[str] = None
