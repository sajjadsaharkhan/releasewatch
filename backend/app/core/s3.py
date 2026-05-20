"""AWS S3 integration — pre-signed URLs, upload validation, and deletion.

Key format used for all uploads::

    {project_slug}/{release_version}/{issue_number}/{uuid4}/{original_filename}

This keeps objects namespaced and browsable in the S3 console.
"""

import uuid
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import settings

# ── Allowed MIME types ────────────────────────────────────────────────────────
ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        # Images / screenshots
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/svg+xml",
        # Videos / recordings
        "video/mp4",
        "video/webm",
        "video/quicktime",
        # Logs / text
        "text/plain",
        "text/csv",
        "application/json",
        "application/xml",
        # Archives
        "application/zip",
        "application/x-tar",
        "application/gzip",
    }
)


class S3Service:
    """Thin wrapper around boto3 that generates pre-signed S3 URLs.

    A single instance should be created at module level and reused for the
    lifetime of the process (boto3 handles connection pooling internally).
    """

    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_ACCESS_KEY or None,
            aws_secret_access_key=settings.S3_SECRET_KEY or None,
            region_name=settings.S3_REGION,
        )
        self.bucket = settings.S3_BUCKET_NAME

    # ── Key construction ──────────────────────────────────────────────────────

    @staticmethod
    def build_key(
        project_slug: str,
        release_version: str,
        issue_number: int,
        filename: str,
    ) -> str:
        """Return a unique S3 object key for the given context.

        Format::

            {project_slug}/{release_version}/{issue_number}/{uuid4}/{filename}
        """
        unique_prefix = uuid.uuid4().hex
        safe_filename = filename.replace(" ", "_")
        return f"{project_slug}/{release_version}/{issue_number}/{unique_prefix}/{safe_filename}"

    # ── Pre-signed upload ─────────────────────────────────────────────────────

    def generate_presigned_upload(
        self,
        project_slug: str,
        release_version: str,
        issue_number: int,
        filename: str,
        mime_type: str,
        max_size_mb: int = 50,
    ) -> dict[str, Any]:
        """Generate a pre-signed POST URL for direct client-side uploads.

        Parameters
        ----------
        project_slug, release_version, issue_number:
            Used to construct the S3 key path.
        filename:
            Original filename supplied by the client.
        mime_type:
            Expected MIME type; validated against ``ALLOWED_MIME_TYPES``.
        max_size_mb:
            Maximum upload size enforced via a Content-Length-Range condition.

        Returns
        -------
        dict
            ``{upload_url, fields, s3_key, attachment_id}`` — pass
            ``upload_url`` + ``fields`` to the browser's ``FormData``.

        Raises
        ------
        ValueError
            If ``mime_type`` is not in ``ALLOWED_MIME_TYPES``.
        """
        if mime_type not in ALLOWED_MIME_TYPES:
            raise ValueError(f"MIME type {mime_type!r} is not allowed for upload.")

        s3_key = self.build_key(project_slug, release_version, issue_number, filename)
        attachment_id = str(uuid.uuid4())

        response = self._client.generate_presigned_post(
            Bucket=self.bucket,
            Key=s3_key,
            Fields={"Content-Type": mime_type},
            Conditions=[
                {"Content-Type": mime_type},
                ["content-length-range", 1, max_size_mb * 1024 * 1024],
            ],
            ExpiresIn=settings.S3_PRESIGN_EXPIRY,
        )

        return {
            "upload_url": response["url"],
            "fields": response["fields"],
            "s3_key": s3_key,
            "attachment_id": attachment_id,
        }

    # ── Pre-signed download ───────────────────────────────────────────────────

    def generate_presigned_download(
        self,
        s3_key: str,
        expiry_seconds: int | None = None,
    ) -> str:
        """Return a pre-signed GET URL for downloading an S3 object.

        Parameters
        ----------
        s3_key:
            The full S3 object key.
        expiry_seconds:
            URL validity window in seconds.  Defaults to ``settings.S3_PRESIGN_EXPIRY``.

        Returns
        -------
        str
            A temporary, signed URL that allows unauthenticated download.
        """
        expiry = expiry_seconds if expiry_seconds is not None else settings.S3_PRESIGN_EXPIRY
        url: str = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": s3_key},
            ExpiresIn=expiry,
        )
        return url

    # ── Deletion ──────────────────────────────────────────────────────────────

    def delete_file(self, s3_key: str) -> None:
        """Permanently delete an S3 object.

        Parameters
        ----------
        s3_key:
            The full S3 object key to delete.

        Raises
        ------
        ClientError
            Re-raised from boto3 on unexpected S3 errors (e.g. access denied).
        """
        try:
            self._client.delete_object(Bucket=self.bucket, Key=s3_key)
        except ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            if error_code == "NoSuchKey":
                return  # Idempotent — already gone
            raise

    # ── Object existence check ────────────────────────────────────────────────

    def object_exists(self, s3_key: str) -> bool:
        """Return ``True`` if the given S3 key exists in the bucket."""
        try:
            self._client.head_object(Bucket=self.bucket, Key=s3_key)
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                return False
            raise


# Module-level singleton
s3_service = S3Service()
