"""Attachment endpoints — nested under issues.

POST /issues/{id}/attachments/presign           — generate pre-signed S3 upload URL
POST /issues/{id}/attachments/confirm           — confirm upload and create DB record
POST /issues/{id}/attachments/multipart/start   — start multipart upload (large files)
POST /issues/{id}/attachments/multipart/part    — get part upload URL
POST /issues/{id}/attachments/multipart/complete — complete multipart upload
GET  /issues/{id}/attachments                   — list attachments with download URLs
DELETE /issues/{id}/attachments/{aid}           — delete an attachment
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.s3 import s3_service
from app.db.models.issue import Issue
from app.db.models.issue_attachment import IssueAttachment
from app.db.models.project import Project
from app.db.models.release import Release
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.attachment import (
    AttachmentResponse,
    ConfirmRequest,
    MultipartCompleteRequest,
    MultipartPartRequest,
    MultipartPartResponse,
    MultipartPresignRequest,
    MultipartPresignResponse,
    PresignRequest,
    PresignResponse,
)
from app.config import settings

router = APIRouter()

# Recommended chunk size for multipart uploads (5MB)
CHUNK_SIZE_BYTES = 5 * 1024 * 1024


@router.post(
    "/{issue_id}/attachments/presign",
    response_model=PresignResponse,
    summary="Generate pre-signed S3 upload URL",
)
async def presign_upload(
    issue_id: uuid.UUID,
    payload: PresignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PresignResponse:
    """Generate a pre-signed S3 POST URL for direct browser-to-S3 uploads.

    The client must then POST the file directly to S3 and call ``/confirm``
    to register the attachment in the database.
    """
    issue = await _get_issue_or_404(db, issue_id)
    release = await _get_release(db, issue.release_id)
    project = await _get_project(db, issue.project_id)

    try:
        result = s3_service.generate_presigned_upload(
            file_type="attachment",
            filename=payload.filename,
            mime_type=payload.mime_type,
            max_size_mb=payload.max_size_mb,
            project_slug=project.slug,
            release_version=release.version,
            issue_number=issue.issue_number,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Determine if this is a large file based on the max size
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
    "/{issue_id}/attachments/confirm",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Confirm upload and register attachment",
)
async def confirm_upload(
    issue_id: uuid.UUID,
    payload: ConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttachmentResponse:
    """Create an ``IssueAttachment`` record after the client has uploaded to S3.

    Also enqueues the ``validate_attachment`` Celery task for MIME re-check
    and thumbnail generation.
    """
    await _get_issue_or_404(db, issue_id)

    attachment = IssueAttachment(
        issue_id=issue_id,
        uploaded_by_id=current_user.id,
        file_name=payload.filename,
        s3_key=payload.s3_key,
        mime_type=payload.mime_type,
        file_size_bytes=payload.file_size_bytes,
        attachment_type=payload.attachment_type,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)

    # Enqueue background validation
    from app.tasks.attachments import validate_attachment

    validate_attachment.apply_async(
        kwargs={"attachment_id": str(attachment.id), "s3_key": payload.s3_key},
        queue="attachments",
    )

    response = AttachmentResponse.model_validate(attachment)

    # Determine URL type based on settings
    if settings.S3_USE_PRESIGNED:
        response.download_url = s3_service.generate_presigned_download(attachment.s3_key)
    else:
        response.public_url = s3_service.get_download_url(attachment.s3_key)

    # Set large file metadata
    if attachment.file_size_bytes:
        threshold = settings.S3_LARGE_FILE_THRESHOLD_MB * 1024 * 1024
        is_large = attachment.file_size_bytes > threshold
        response.is_large_file = is_large
        if is_large:
            response.retention_days = settings.S3_LARGE_FILE_RETENTION_DAYS

    return response


@router.post(
    "/{issue_id}/attachments/multipart/start",
    response_model=MultipartPresignResponse,
    summary="Start multipart upload for large files",
)
async def start_multipart_upload(
    issue_id: uuid.UUID,
    payload: MultipartPresignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MultipartPresignResponse:
    """Initialize a multipart upload for files larger than 100MB.

    Returns an upload_id and recommended chunk size. The client should then
    call ``/multipart/part`` for each chunk, and finally ``/multipart/complete``.
    """
    issue = await _get_issue_or_404(db, issue_id)
    release = await _get_release(db, issue.release_id)
    project = await _get_project(db, issue.project_id)

    try:
        result = s3_service.create_multipart_upload(
            file_type="attachment",
            filename=payload.filename,
            mime_type=payload.mime_type,
            project_slug=project.slug,
            release_version=release.version,
            issue_number=issue.issue_number,
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
    "/{issue_id}/attachments/multipart/part",
    response_model=MultipartPartResponse,
    summary="Get upload URL for a part",
)
async def get_part_upload_url(
    issue_id: uuid.UUID,
    payload: MultipartPartRequest,
    current_user: User = Depends(get_current_user),
) -> MultipartPartResponse:
    """Generate a pre-signed URL for uploading a single part of a multipart upload.

    Note: Issue validation is skipped for part uploads to allow concurrent chunk uploads.
    The upload_id and s3_key from the multipart start response are sufficient for security.
    """
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

    return MultipartPartResponse(
        upload_url=part_url,
        part_url=part_url,
    )


@router.post(
    "/{issue_id}/attachments/multipart/complete",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Complete multipart upload",
)
async def complete_multipart_upload(
    issue_id: uuid.UUID,
    payload: MultipartCompleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttachmentResponse:
    """Complete a multipart upload and create the database record."""
    await _get_issue_or_404(db, issue_id)

    try:
        result = s3_service.complete_multipart_upload(
            s3_key=payload.s3_key,
            upload_id=payload.upload_id,
            parts=payload.parts,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to complete multipart upload: {str(exc)}",
        )

    attachment = IssueAttachment(
        issue_id=issue_id,
        uploaded_by_id=current_user.id,
        file_name=payload.filename,
        s3_key=payload.s3_key,
        mime_type=payload.mime_type,
        file_size_bytes=payload.file_size_bytes,
        attachment_type=payload.attachment_type,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)

    response = AttachmentResponse.model_validate(attachment)

    # Determine URL type based on settings
    if settings.S3_USE_PRESIGNED:
        response.download_url = s3_service.generate_presigned_download(attachment.s3_key)
    else:
        response.public_url = s3_service.get_download_url(attachment.s3_key)

    # Set large file metadata (multipart uploads are always large)
    response.is_large_file = True
    response.retention_days = settings.S3_LARGE_FILE_RETENTION_DAYS

    return response


@router.get(
    "/{issue_id}/attachments",
    response_model=List[AttachmentResponse],
    summary="List issue attachments",
)
async def list_attachments(
    issue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AttachmentResponse]:
    """Return all attachments for an issue, each with a download URL."""
    await _get_issue_or_404(db, issue_id)
    result = await db.execute(
        select(IssueAttachment)
        .where(IssueAttachment.issue_id == issue_id)
        .order_by(IssueAttachment.created_at.desc())
    )
    attachments = result.scalars().all()

    responses = []
    for att in attachments:
        resp = AttachmentResponse.model_validate(att)

        # Determine URL type based on settings
        if settings.S3_USE_PRESIGNED:
            resp.download_url = s3_service.generate_presigned_download(att.s3_key)
        else:
            resp.public_url = s3_service.get_download_url(att.s3_key)

        # Set large file metadata
        if att.file_size_bytes:
            threshold = settings.S3_LARGE_FILE_THRESHOLD_MB * 1024 * 1024
            is_large = att.file_size_bytes > threshold
            resp.is_large_file = is_large
            if is_large:
                resp.retention_days = settings.S3_LARGE_FILE_RETENTION_DAYS

        responses.append(resp)
    return responses


@router.delete(
    "/{issue_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an attachment",
)
async def delete_attachment(
    issue_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete an attachment from S3 and the database.

    Only the uploader or an admin may delete an attachment.
    """
    result = await db.execute(
        select(IssueAttachment).where(
            IssueAttachment.id == attachment_id,
            IssueAttachment.issue_id == issue_id,
        )
    )
    attachment = result.scalar_one_or_none()
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    is_uploader = attachment.uploaded_by_id == current_user.id
    is_admin = current_user.role == UserRole.admin
    if not (is_uploader or is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    s3_service.delete_file(attachment.s3_key)
    await db.delete(attachment)
    await db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_issue_or_404(db: AsyncSession, issue_id: uuid.UUID) -> Issue:
    result = await db.execute(select(Issue).where(Issue.id == issue_id))
    issue = result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    return issue


async def _get_release(db: AsyncSession, release_id: uuid.UUID) -> Release:
    result = await db.execute(select(Release).where(Release.id == release_id))
    return result.scalar_one()


async def _get_project(db: AsyncSession, project_id: uuid.UUID) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    return result.scalar_one()
