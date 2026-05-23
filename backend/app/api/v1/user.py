"""User profile and avatar endpoints.

POST /me/avatar/presign   — generate pre-signed S3 upload URL for avatar
PUT  /me/profile          — update profile (name, title, bio, avatar_url, password)
DELETE /me/avatar         — remove avatar
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, get_password_hash
from app.core.s3 import s3_service
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.user import (
    AvatarUploadRequest,
    AvatarUploadResponse,
    ProfileUpdateRequest,
    UserResponse,
)

router = APIRouter()


@router.post(
    "/me/avatar/presign",
    response_model=AvatarUploadResponse,
    summary="Generate pre-signed S3 upload URL for avatar",
)
async def presign_avatar_upload(
    payload: AvatarUploadRequest,
    current_user: User = Depends(get_current_user),
) -> AvatarUploadResponse:
    """Generate a pre-signed S3 POST URL for avatar upload."""
    if not payload.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image files are allowed",
        )

    s3_key = f"avatars/{current_user.username}/{uuid.uuid4().hex}/{payload.file_name}"

    response = s3_service._client.generate_presigned_post(
        Bucket=s3_service.bucket,
        Key=s3_key,
        Fields={"Content-Type": payload.content_type},
        Conditions=[
            {"Content-Type": payload.content_type},
            ["content-length-range", 1, payload.file_size_bytes],
        ],
        ExpiresIn=3600,
    )

    return AvatarUploadResponse(
        upload_url=response["url"],
        s3_key=s3_key,
    )


@router.put(
    "/me/profile",
    response_model=UserResponse,
    summary="Update user profile",
)
async def update_profile(
    payload: ProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Update user profile fields."""
    if payload.name is not None:
        current_user.name = payload.name
    if payload.username is not None:
        current_user.username = payload.username
    if payload.title is not None:
        current_user.title = payload.title
    if payload.bio is not None:
        current_user.bio = payload.bio
    if payload.avatar_url is not None:
        current_user.avatar_url = payload.avatar_url
    if payload.password is not None:
        current_user.hashed_password = get_password_hash(payload.password)

    await db.commit()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.delete(
    "/me/avatar",
    response_model=UserResponse,
    summary="Remove avatar",
)
async def remove_avatar(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Remove user's avatar and revert to initials."""
    if current_user.avatar_url:
        current_user.avatar_url = None
        await db.commit()
        await db.refresh(current_user)
    return UserResponse.model_validate(current_user)