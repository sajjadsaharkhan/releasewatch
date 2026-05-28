"""Celery tasks — post-upload attachment validation and thumbnail generation.

After a client confirms an upload (POST /issues/{id}/attachments/confirm),
this task is enqueued to:

1. Detect the MIME type from S3 (for display purposes).
2. Generate a thumbnail for image attachments using Pillow.
3. Update ``file_size_bytes`` from the S3 HEAD response.

All file types are now allowed — MIME type detection is for display only,
not rejection.
"""

import asyncio
import io
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Pillow thumbnail target dimensions
THUMBNAIL_SIZE = (400, 400)
THUMBNAIL_SUFFIX = "_thumb.jpg"


@celery_app.task(
    bind=True,
    name="app.tasks.attachments.validate_attachment",
    max_retries=2,
    default_retry_delay=15,
    queue="attachments",
)
def validate_attachment(
    self,
    attachment_id: str,
    s3_key: str,
) -> dict:
    """Validate an uploaded attachment and generate a thumbnail if it's an image.

    Parameters
    ----------
    attachment_id:
        UUID string of the ``IssueAttachment`` row to validate.
    s3_key:
        S3 object key of the uploaded file.

    Returns
    -------
    dict
        ``{valid: bool, thumbnail_key: str|None, file_size_bytes: int|None}``

    Note
    ----
    All file types are now allowed. MIME type detection is for display purposes
    and thumbnail generation, not for rejection.
    """
    from app.core.s3 import s3_service

    try:
        # Pass None for allowed_mime_types to accept all types
        result = asyncio.run(_validate(attachment_id, s3_key, s3_service, allowed_mime_types=None))
        return result
    except Exception as exc:
        logger.exception("validate_attachment failed for %s: %s", attachment_id, exc)
        raise self.retry(exc=exc)


async def _validate(
    attachment_id: str,
    s3_key: str,
    s3_service,
    allowed_mime_types,
) -> dict:
    """Async implementation of validate_attachment."""
    import boto3
    import botocore

    from app.config import settings

    boto_client = boto3.client(
        "s3",
        aws_access_key_id=settings.S3_ACCESS_KEY or None,
        aws_secret_access_key=settings.S3_SECRET_KEY or None,
        region_name=settings.S3_REGION,
    )

    # ── 1. HEAD request — get size and server-declared Content-Type ────────────
    try:
        head = boto_client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
    except botocore.exceptions.ClientError as exc:
        logger.warning("S3 HEAD failed for %s: %s", s3_key, exc)
        return {"valid": False, "thumbnail_key": None, "file_size_bytes": None}

    file_size = head.get("ContentLength")
    content_type = head.get("ContentType", "")

    # Strip charset etc. from content type
    declared_mime = content_type.split(";")[0].strip()

    # Only reject if allowed_mime_types is explicitly set and MIME doesn't match
    # (For attachments, allowed_mime_types is None, so all types are accepted)
    if allowed_mime_types is not None and declared_mime not in allowed_mime_types:
        logger.warning(
            "Attachment %s rejected — MIME type %r not allowed", attachment_id, declared_mime
        )
        # Clean up S3 and DB
        await _delete_attachment(attachment_id, s3_key, s3_service)
        return {"valid": False, "thumbnail_key": None, "file_size_bytes": None}

    # ── 2. Generate thumbnail for images ──────────────────────────────────────
    thumbnail_key: str | None = None
    if declared_mime.startswith("image/"):
        thumbnail_key = await _generate_thumbnail(
            boto_client, settings.S3_BUCKET_NAME, s3_key, file_size
        )

    # ── 3. Update DB row ──────────────────────────────────────────────────────
    await _update_attachment_record(attachment_id, file_size, declared_mime)

    return {
        "valid": True,
        "thumbnail_key": thumbnail_key,
        "file_size_bytes": file_size,
    }


async def _generate_thumbnail(
    boto_client,
    bucket: str,
    s3_key: str,
    file_size: int | None,
) -> str | None:
    """Download the image, generate a thumbnail, and upload it back to S3."""
    try:
        from PIL import Image, UnidentifiedImageError

        max_source_bytes = 20 * 1024 * 1024  # 20 MB guard
        if file_size and file_size > max_source_bytes:
            logger.info("Skipping thumbnail for large file (%d bytes): %s", file_size, s3_key)
            return None

        response = boto_client.get_object(Bucket=bucket, Key=s3_key)
        raw = response["Body"].read()

        img = Image.open(io.BytesIO(raw))
        img.thumbnail(THUMBNAIL_SIZE)

        thumb_buffer = io.BytesIO()
        img.convert("RGB").save(thumb_buffer, format="JPEG", quality=85, optimize=True)
        thumb_buffer.seek(0)

        thumb_key = s3_key + THUMBNAIL_SUFFIX
        boto_client.put_object(
            Bucket=bucket,
            Key=thumb_key,
            Body=thumb_buffer,
            ContentType="image/jpeg",
        )
        logger.info("Thumbnail generated: %s", thumb_key)
        return thumb_key

    except Exception as exc:
        logger.warning("Thumbnail generation failed for %s: %s", s3_key, exc)
        return None


async def _delete_attachment(attachment_id: str, s3_key: str, s3_service) -> None:
    """Remove both the S3 object and the DB row for an invalid attachment."""
    # S3 cleanup
    try:
        s3_service.delete_file(s3_key)
    except Exception as exc:
        logger.error("Failed to delete S3 object %s: %s", s3_key, exc)

    # DB cleanup — open a fresh session since we're inside a Celery task
    try:
        from sqlalchemy import delete
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from app.config import settings
        from app.db.models.issue_attachment import IssueAttachment

        engine = create_async_engine(settings.database_url)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await session.execute(
                delete(IssueAttachment).where(
                    IssueAttachment.id == int(attachment_id)
                )
            )
            await session.commit()
        await engine.dispose()
    except Exception as exc:
        logger.error("Failed to delete attachment record %s: %s", attachment_id, exc)


async def _update_attachment_record(
    attachment_id: str,
    file_size_bytes: int | None,
    mime_type: str,
) -> None:
    """Update file_size_bytes and mime_type on the IssueAttachment row."""
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from sqlalchemy import update
        from app.config import settings
        from app.db.models.issue_attachment import IssueAttachment

        engine = create_async_engine(settings.database_url)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await session.execute(
                update(IssueAttachment)
                .where(IssueAttachment.id == int(attachment_id))
                .values(file_size_bytes=file_size_bytes, mime_type=mime_type)
            )
            await session.commit()
        await engine.dispose()
    except Exception as exc:
        logger.error("Failed to update attachment record %s: %s", attachment_id, exc)
