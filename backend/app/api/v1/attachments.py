"""Attachment endpoints — nested under issues.

POST /issues/{id}/attachments/presign   — generate pre-signed upload URL
POST /issues/{id}/attachments/confirm   — confirm upload and create DB record
GET  /issues/{id}/attachments           — list attachments with download URLs
DELETE /issues/{id}/attachments/{aid}   — delete an attachment
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
    PresignRequest,
    PresignResponse,
)

router = APIRouter()


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
            project_slug=project.slug,
            release_version=release.version,
            issue_number=issue.issue_number,
            filename=payload.filename,
            mime_type=payload.mime_type,
            max_size_mb=payload.max_size_mb,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    from app.config import settings

    return PresignResponse(
        upload_url=result["upload_url"],
        fields=result["fields"],
        s3_key=result["s3_key"],
        attachment_id=result["attachment_id"],
        expires_in_seconds=settings.S3_PRESIGN_EXPIRY,
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
    response.download_url = s3_service.generate_presigned_download(attachment.s3_key)
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
    """Return all attachments for an issue, each with a fresh pre-signed download URL."""
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
        resp.download_url = s3_service.generate_presigned_download(att.s3_key)
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
