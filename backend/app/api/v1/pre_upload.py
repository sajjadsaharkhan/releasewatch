"""Standalone attachment pre-upload endpoints — no issue ID required.

Used when uploading files before an issue exists (new issue creation flow).
Files are stored at a flat S3 path: attachments/issues/{uuid}/{filename}

POST /api/v1/attachments/presign              — generate presigned upload URL
POST /api/v1/attachments/multipart/start      — start multipart upload (large files)
POST /api/v1/attachments/multipart/part       — get presigned URL for a part
POST /api/v1/attachments/multipart/complete   — complete multipart upload (S3 only, no DB record)
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.config import settings
from app.core.auth import get_current_user
from app.core.s3 import s3_service
from app.db.models.issue_attachment import AttachmentType
from app.db.models.user import User
from app.schemas.attachment import (
    MultipartPartRequest,
    MultipartPartResponse,
    MultipartPresignRequest,
    MultipartPresignResponse,
    PresignRequest,
    PresignResponse,
)


class MultipartCompleteForPendingRequest(BaseModel):
    """Payload for completing a multipart upload without creating a DB record."""
    upload_id: str
    s3_key: str
    parts: list[dict] = Field(..., description="List of {part_number: int, etag: str}")
    filename: str = Field(max_length=512)
    mime_type: str = Field(max_length=128)
    file_size_bytes: int
    attachment_type: AttachmentType = AttachmentType.other


class PendingAttachmentResult(BaseModel):
    """Returned after a successful pre-upload — no DB record exists yet."""
    s3_key: str
    filename: str
    mime_type: str
    file_size_bytes: int
    attachment_type: AttachmentType
    is_large_file: bool

router = APIRouter()

CHUNK_SIZE_BYTES = 5 * 1024 * 1024


@router.post(
    "/presign",
    response_model=PresignResponse,
    summary="Generate pre-signed S3 upload URL (no issue required)",
)
async def presign_upload(
    payload: PresignRequest,
    current_user: User = Depends(get_current_user),
) -> PresignResponse:
    """Generate a presigned S3 POST URL for direct browser-to-S3 uploads.

    Files land at attachments/issues/{uuid}/{filename}. No database record is
    created here — the frontend collects the returned s3_key and sends it with
    the IssueCreate payload so the backend can link attachments atomically.
    """
    try:
        result = s3_service.generate_presigned_upload(
            file_type="attachment",
            filename=payload.filename,
            mime_type=payload.mime_type,
            max_size_mb=payload.max_size_mb,
            # No project_slug/release_version/issue_number → flat path
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    is_large_file = payload.max_size_mb > settings.S3_LARGE_FILE_THRESHOLD_MB

    return PresignResponse(
        upload_url=result["upload_url"],
        fields=result["fields"],
        s3_key=result["s3_key"],
        attachment_id=result["file_id"],
        public_url=result["public_url"],
        expires_in_seconds=settings.S3_PRESIGN_EXPIRY,
        is_large_file=is_large_file,
    )


@router.post(
    "/multipart/start",
    response_model=MultipartPresignResponse,
    summary="Start multipart upload for large files (no issue required)",
)
async def start_multipart_upload(
    payload: MultipartPresignRequest,
    current_user: User = Depends(get_current_user),
) -> MultipartPresignResponse:
    """Initialize a multipart upload for files larger than 100MB."""
    try:
        result = s3_service.create_multipart_upload(
            file_type="attachment",
            filename=payload.filename,
            mime_type=payload.mime_type,
            # No project/release/issue context → flat path
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return MultipartPresignResponse(
        upload_id=result["upload_id"],
        s3_key=result["s3_key"],
        file_id=result["file_id"],
        chunk_size_bytes=CHUNK_SIZE_BYTES,
    )


@router.post(
    "/multipart/part",
    response_model=MultipartPartResponse,
    summary="Get presigned URL for a multipart part (no issue required)",
)
async def get_part_upload_url(
    payload: MultipartPartRequest,
    current_user: User = Depends(get_current_user),
) -> MultipartPartResponse:
    """Generate a presigned URL for uploading a single part of a multipart upload."""
    part_url = s3_service._client.generate_presigned_url(
        "upload_part",
        Params={
            "Bucket": s3_service.bucket,
            "Key": payload.s3_key,
            "UploadId": payload.upload_id,
            "PartNumber": payload.part_number,
        },
        ExpiresIn=settings.S3_PRESIGN_EXPIRY,
    )

    return MultipartPartResponse(upload_url=part_url, part_url=part_url)


@router.post(
    "/multipart/complete",
    response_model=PendingAttachmentResult,
    summary="Complete multipart upload (S3 only, no DB record created)",
)
async def complete_multipart_upload(
    payload: MultipartCompleteForPendingRequest,
    current_user: User = Depends(get_current_user),
) -> PendingAttachmentResult:
    """Finalize the S3 multipart upload and return metadata for later use.

    No IssueAttachment DB record is created here. The returned metadata should
    be sent as part of the pending_attachments list when creating the issue.
    """
    try:
        s3_service.complete_multipart_upload(
            s3_key=payload.s3_key,
            upload_id=payload.upload_id,
            parts=payload.parts,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to complete multipart upload: {str(exc)}",
        )

    threshold = settings.S3_LARGE_FILE_THRESHOLD_MB * 1024 * 1024
    is_large = payload.file_size_bytes > threshold

    return PendingAttachmentResult(
        s3_key=payload.s3_key,
        filename=payload.filename,
        mime_type=payload.mime_type,
        file_size_bytes=payload.file_size_bytes,
        attachment_type=payload.attachment_type,
        is_large_file=is_large,
    )
