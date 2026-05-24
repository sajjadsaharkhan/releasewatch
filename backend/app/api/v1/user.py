"""User profile and avatar endpoints.

POST /me/avatar/presign   — generate pre-signed S3 upload URL for avatar
POST /me/avatar/confirm   — confirm avatar upload and update profile
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
    AvatarConfirmRequest,
    AvatarPresignRequest,
    AvatarPresignResponse,
    ProfileUpdateRequest,
    UserResponse,
)

router = APIRouter()


@router.post(
    "/me/avatar/presign",
    response_model=AvatarPresignResponse,
    summary="Generate pre-signed S3 upload URL for avatar",
)
async def presign_avatar_upload(
    payload: AvatarPresignRequest,
    current_user: User = Depends(get_current_user),
) -> AvatarPresignResponse:
    """Generate a pre-signed S3 POST URL for avatar upload.

    The client must then POST the file directly to S3 and call ``/confirm``
    to register the avatar in the database.
    """
    try:
        result = s3_service.generate_presigned_upload(
            file_type="avatar",
            filename=payload.filename,
            mime_type=payload.mime_type,
            max_size_mb=5,  # Avatar images limited to 5MB
            user_id=str(current_user.id),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    from app.config import settings

    return AvatarPresignResponse(
        upload_url=result["upload_url"],
        fields=result["fields"],
        s3_key=result["s3_key"],
        file_id=result["file_id"],
        public_url=result["public_url"],
        expires_in_seconds=settings.S3_PRESIGN_EXPIRY,
    )


@router.post(
    "/me/avatar/confirm",
    response_model=UserResponse,
    summary="Confirm avatar upload and update profile",
)
async def confirm_avatar_upload(
    payload: AvatarConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Confirm avatar upload and update the user's avatar_url.

    Optionally deletes the old avatar from S3 if ``delete_old`` is True.
    """
    # Verify the object exists in S3
    if not s3_service.object_exists(payload.s3_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Avatar file not found in S3. Upload may have failed.",
        )

    # Delete old avatar if requested and one exists
    if payload.delete_old and current_user.avatar_url:
        # Extract S3 key from the old URL if it's our S3 URL
        old_url = current_user.avatar_url
        if old_url.startswith("http"):
            # Try to extract key from URL
            if "avatars/" in old_url:
                # Handle both presigned and public URLs
                parts = old_url.split("avatars/")
                if len(parts) > 1:
                    old_key = "avatars/" + parts[1].split("?")[0]  # Remove query params
                    try:
                        s3_service.delete_file(old_key)
                    except Exception:
                        pass  # Ignore deletion errors

    # Generate the permanent URL
    avatar_url = s3_service.get_download_url(payload.s3_key)

    # Update user profile
    current_user.avatar_url = avatar_url
    await db.commit()
    await db.refresh(current_user)

    return UserResponse.model_validate(current_user)


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
        # Check for duplicate username
        from sqlalchemy import select
        result = await db.execute(
            select(User).where(
                User.username == payload.username,
                User.id != current_user.id,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )
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
        # Delete from S3 if it's our URL
        old_url = current_user.avatar_url
        if "avatars/" in old_url:
            parts = old_url.split("avatars/")
            if len(parts) > 1:
                old_key = "avatars/" + parts[1].split("?")[0]
                try:
                    s3_service.delete_file(old_key)
                except Exception:
                    pass  # Ignore deletion errors

        current_user.avatar_url = None
        await db.commit()
        await db.refresh(current_user)
    return UserResponse.model_validate(current_user)
