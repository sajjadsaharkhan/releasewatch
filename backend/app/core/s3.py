"""AWS S3 / MinIO integration — pre-signed URLs, upload validation, lifecycle policies.

Key formats used for uploads:
- Attachments:  attachments/{project_slug}/{release_version}/{issue_number}/{uuid4}/{filename}
- Profile avatars: avatars/{user_id}/{uuid4}/{filename}

This keeps objects namespaced and browsable in the S3 console.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import boto3
from botocore.exceptions import ClientError

from app.config import settings

# ── Allowed MIME types ────────────────────────────────────────────────────────
# Avatar-specific MIME types (avatars are still restricted to images for security)
AVATAR_MIME_TYPES: frozenset[str] = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
    }
)

# ── File type categories ───────────────────────────────────────────────────────
FileType = Literal["attachment", "avatar"]


class S3Service:
    """Thin wrapper around boto3 with S3/MinIO support.

    Features:
    - Pre-signed POST URLs for direct client uploads
    - Public URL generation for permanent access
    - S3 lifecycle policy configuration for auto-deletion
    - Support for custom endpoints (MinIO, etc.)

    A single instance should be created at module level and reused for the
    lifetime of the process (boto3 handles connection pooling internally).
    """

    def __init__(self) -> None:
        client_config: dict[str, Any] = {}
        if settings.S3_ENDPOINT_URL:
            client_config["endpoint_url"] = settings.S3_ENDPOINT_URL

        self._client = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_ACCESS_KEY or None,
            aws_secret_access_key=settings.S3_SECRET_KEY or None,
            region_name=settings.S3_REGION,
            **client_config,
        )
        self.bucket = settings.S3_BUCKET_NAME
        self._lifecycle_configured = False

    # ── Bucket initialization ───────────────────────────────────────────────────

    def ensure_bucket_exists(self) -> None:
        """Create the bucket if it doesn't exist."""
        # First, try to create the bucket (idempotent - will fail if already exists)
        try:
            if settings.S3_ENDPOINT_URL and settings.S3_REGION == "us-east-1":
                # MinIO typically doesn't need location constraint
                self._client.create_bucket(Bucket=self.bucket)
            elif settings.S3_ENDPOINT_URL:
                # MinIO with explicit region
                self._client.create_bucket(Bucket=self.bucket)
            else:
                # AWS S3 with region
                location = {"LocationConstraint": settings.S3_REGION} if settings.S3_REGION != "us-east-1" else {}
                self._client.create_bucket(
                    Bucket=self.bucket,
                    CreateBucketConfiguration=location
                )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            # BucketAlreadyExists, BucketAlreadyOwnedByYou are OK - means bucket exists
            if error_code not in ("BucketAlreadyExists", "BucketAlreadyOwnedByYou"):
                # For other errors (like 403), log but don't fail - bucket might exist
                import logging
                logging.warning(f"S3 bucket check returned {error_code}: {exc}")

    def ensure_lifecycle_policy(self) -> None:
        """Configure lifecycle policy for auto-deletion of large files."""
        if self._lifecycle_configured:
            return

        rule_id = "delete-large-files"
        pre_upload_rule_id = "cleanup-pre-uploads"
        retention_days = settings.S3_LARGE_FILE_RETENTION_DAYS

        try:
            existing = self._client.get_bucket_lifecycle_configuration(Bucket=self.bucket)
            existing_ids = {rule.get("ID") for rule in existing.get("Rules", [])}
            if rule_id in existing_ids and pre_upload_rule_id in existing_ids:
                self._lifecycle_configured = True
                return
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code != "NoSuchLifecycleConfiguration":
                import logging
                logging.warning(f"S3 lifecycle check returned {error_code}: {exc}")
                return

        # Create or update lifecycle rules
        lifecycle_config = {
            "Rules": [
                {
                    "ID": rule_id,
                    "Status": "Enabled",
                    "Filter": {
                        "And": {
                            "Prefix": "attachments/",
                            "Tag": {
                                "Key": "LargeFile",
                                "Value": "true"
                            }
                        }
                    },
                    "Expiration": {
                        "Days": retention_days
                    },
                    "NoncurrentVersionExpiration": {
                        "NoncurrentDays": retention_days
                    }
                },
                {
                    "ID": pre_upload_rule_id,
                    "Status": "Enabled",
                    "Filter": {"Prefix": "attachments/issues/"},
                    "Expiration": {"Days": 2},
                }
            ]
        }

        try:
            self._client.put_bucket_lifecycle_configuration(
                Bucket=self.bucket,
                LifecycleConfiguration=lifecycle_config
            )
            self._lifecycle_configured = True
        except ClientError as exc:
            # Log warning but don't fail - lifecycle is optional
            import logging
            logging.warning(f"S3 lifecycle configuration failed: {exc}")

    # ── Key construction ──────────────────────────────────────────────────────

    def build_key(
        self,
        file_type: FileType,
        **context: Any,
    ) -> tuple[str, str]:
        """Return a unique S3 object key and a unique ID prefix.

        Parameters
        ----------
        file_type:
            Either "attachment" or "avatar"
        **context:
            For attachments: project_slug, release_version, issue_number, filename
            For avatars: user_id, filename

        Returns
        -------
        tuple[str, str]
            (s3_key, unique_id) - The full S3 key and the unique ID for this upload
        """
        unique_id = uuid.uuid4().hex

        if file_type == "avatar":
            user_id = context.get("user_id", "unknown")
            filename = context.get("filename", "avatar.jpg")
            safe_filename = filename.replace(" ", "_")
            s3_key = f"avatars/{user_id}/{unique_id}/{safe_filename}"
        else:  # attachment
            filename = context.get("filename", "file.bin")
            safe_filename = filename.replace(" ", "_")
            if "project_slug" in context:
                project_slug = context["project_slug"]
                release_version = context.get("release_version", "unknown")
                issue_number = context.get("issue_number", "0")
                s3_key = f"attachments/{project_slug}/{release_version}/{issue_number}/{unique_id}/{safe_filename}"
            else:
                # Flat pre-upload path — no issue context yet (new issue creation)
                s3_key = f"attachments/issues/{unique_id}/{safe_filename}"

        return s3_key, unique_id

    # ── Tagging for lifecycle ───────────────────────────────────────────────────

    def _get_file_tags(self, file_size_bytes: int) -> dict[str, str]:
        """Return S3 object tags based on file size for lifecycle policies."""
        threshold = settings.S3_LARGE_FILE_THRESHOLD_MB * 1024 * 1024
        if file_size_bytes > threshold:
            return {"LargeFile": "true"}
        return {"LargeFile": "false"}

    # ── Pre-signed upload ─────────────────────────────────────────────────────

    def generate_presigned_upload(
        self,
        file_type: FileType,
        filename: str,
        mime_type: str,
        max_size_mb: int = 50,
        **context: Any,
    ) -> dict[str, Any]:
        """Generate a pre-signed POST URL for direct client-side uploads.

        Parameters
        ----------
        file_type:
            Either "attachment" or "avatar"
        filename:
            Original filename supplied by the client.
        mime_type:
            Expected MIME type; validated against allowed types for avatars.
        max_size_mb:
            Maximum upload size enforced via a Content-Length-Range condition.
        **context:
            Additional context for key construction (project_slug, user_id, etc.)

        Returns
        -------
        dict
            ``{upload_url, fields, s3_key, file_id, public_url}`` — pass
            ``upload_url`` + ``fields`` to the browser's ``FormData``.
        """
        # Only avatars have MIME type restrictions
        if file_type == "avatar" and mime_type not in AVATAR_MIME_TYPES:
            raise ValueError(f"MIME type {mime_type!r} is not allowed for avatar uploads.")

        s3_key, unique_id = self.build_key(file_type, filename=filename, **context)
        file_id = str(uuid.uuid4())

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

        public_url = None
        if not settings.S3_USE_PRESIGNED and settings.S3_PUBLIC_URL_BASE:
            public_url = f"{settings.S3_PUBLIC_URL_BASE.rstrip('/')}/{s3_key}"

        return {
            "upload_url": response["url"],
            "fields": response["fields"],
            "s3_key": s3_key,
            "file_id": file_id,
            "public_url": public_url,
        }

    # ── Direct upload (server-side) ────────────────────────────────────────────

    def upload_file(
        self,
        file_data: bytes,
        file_type: FileType,
        filename: str,
        mime_type: str,
        **context: Any,
    ) -> dict[str, Any]:
        """Upload a file directly to S3 (server-side upload).

        Parameters
        ----------
        file_data:
            Raw file bytes.
        file_type:
            Either "attachment" or "avatar"
        filename:
            Original filename.
        mime_type:
            File MIME type.
        **context:
            Additional context for key construction.

        Returns
        -------
        dict
            ``{s3_key, file_id, public_url, file_size_bytes}``
        """
        # Only avatars have MIME type restrictions
        if file_type == "avatar" and mime_type not in AVATAR_MIME_TYPES:
            raise ValueError(f"MIME type {mime_type!r} is not allowed for avatar uploads.")

        s3_key, unique_id = self.build_key(file_type, filename=filename, **context)
        file_id = str(uuid.uuid4())
        file_size = len(file_data)

        # Upload with tags for lifecycle policy
        tags = self._get_file_tags(file_size)
        self._client.put_object(
            Bucket=self.bucket,
            Key=s3_key,
            Body=file_data,
            ContentType=mime_type,
            Tagging="&".join(f"{k}={v}" for k, v in tags.items()),
        )

        public_url = None
        if not settings.S3_USE_PRESIGNED and settings.S3_PUBLIC_URL_BASE:
            public_url = f"{settings.S3_PUBLIC_URL_BASE.rstrip('/')}/{s3_key}"

        return {
            "s3_key": s3_key,
            "file_id": file_id,
            "public_url": public_url,
            "file_size_bytes": file_size,
        }

    # ── URL generation ─────────────────────────────────────────────────────────

    def get_download_url(
        self,
        s3_key: str,
        expiry_seconds: int | None = None,
    ) -> str:
        """Return a download URL for an S3 object.

        Returns a public URL if configured, otherwise generates a pre-signed URL.

        Parameters
        ----------
        s3_key:
            The full S3 object key.
        expiry_seconds:
            For pre-signed URLs only. Defaults to ``settings.S3_PRESIGN_EXPIRY``.

        Returns
        -------
        str
            A URL for downloading the object.
        """
        if not settings.S3_USE_PRESIGNED and settings.S3_PUBLIC_URL_BASE:
            # Return permanent public URL
            return f"{settings.S3_PUBLIC_URL_BASE.rstrip('/')}/{s3_key}"

        # Generate pre-signed URL
        expiry = expiry_seconds if expiry_seconds is not None else settings.S3_PRESIGN_EXPIRY
        url: str = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": s3_key},
            ExpiresIn=expiry,
        )
        return url

    def generate_presigned_download(
        self,
        s3_key: str,
        expiry_seconds: int | None = None,
    ) -> str:
        """Return a pre-signed GET URL for downloading an S3 object.

        This method always returns a pre-signed URL, even when public URLs are enabled.
        Use ``get_download_url`` for the default behavior.

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

    # ── File info ──────────────────────────────────────────────────────────────

    def get_file_info(self, s3_key: str) -> dict[str, Any] | None:
        """Return metadata about an S3 object.

        Parameters
        ----------
        s3_key:
            The full S3 object key.

        Returns
        -------
        dict | None
            Object metadata including size, content_type, last_modified, or None if not found.
        """
        try:
            response = self._client.head_object(Bucket=self.bucket, Key=s3_key)
            return {
                "size_bytes": response.get("ContentLength", 0),
                "content_type": response.get("ContentType", ""),
                "last_modified": response.get("LastModified", datetime.now(timezone.utc)),
                "etag": response.get("ETag", "").strip('"'),
            }
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                return None
            raise

    # ── Multipart upload tracking ───────────────────────────────────────────────

    def create_multipart_upload(
        self,
        file_type: FileType,
        filename: str,
        mime_type: str,
        **context: Any,
    ) -> dict[str, Any]:
        """Initialize a multipart upload for large files.

        Parameters
        ----------
        file_type:
            Either "attachment" or "avatar"
        filename:
            Original filename.
        mime_type:
            File MIME type.
        **context:
            Additional context for key construction.

        Returns
        -------
        dict
            ``{upload_id, s3_key, file_id}`` for tracking the upload.
        """
        # Only avatars have MIME type restrictions
        if file_type == "avatar" and mime_type not in AVATAR_MIME_TYPES:
            raise ValueError(f"MIME type {mime_type!r} is not allowed for avatar uploads.")

        s3_key, unique_id = self.build_key(file_type, filename=filename, **context)
        file_id = str(uuid.uuid4())

        response = self._client.create_multipart_upload(
            Bucket=self.bucket,
            Key=s3_key,
            ContentType=mime_type,
        )

        return {
            "upload_id": response["UploadId"],
            "s3_key": s3_key,
            "file_id": file_id,
        }

    def complete_multipart_upload(
        self,
        s3_key: str,
        upload_id: str,
        parts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Complete a multipart upload.

        Parameters
        ----------
        s3_key:
            The S3 object key.
        upload_id:
            The upload ID from create_multipart_upload.
        parts:
            List of parts in format ``[{PartNumber: int, ETag: str}, ...]``

        Returns
        -------
        dict
            ``{location, bucket, key, etag}``
        """
        response = self._client.complete_multipart_upload(
            Bucket=self.bucket,
            Key=s3_key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )

        # Tag the object for lifecycle policy
        file_info = self.get_file_info(s3_key)
        if file_info:
            tags = self._get_file_tags(file_info["size_bytes"])
            self._client.put_object_tagging(
                Bucket=self.bucket,
                Key=s3_key,
                Tagging={"TagSet": [{"Key": k, "Value": v} for k, v in tags.items()]}
            )

        public_url = None
        if not settings.S3_USE_PRESIGNED and settings.S3_PUBLIC_URL_BASE:
            public_url = f"{settings.S3_PUBLIC_URL_BASE.rstrip('/')}/{s3_key}"

        return {
            "location": response.get("Location", ""),
            "bucket": response.get("Bucket", ""),
            "key": response.get("Key", ""),
            "etag": response.get("ETag", "").strip('"'),
            "public_url": public_url,
        }

    def abort_multipart_upload(self, s3_key: str, upload_id: str) -> None:
        """Abort a multipart upload, cleaning up any uploaded parts."""
        self._client.abort_multipart_upload(
            Bucket=self.bucket,
            Key=s3_key,
            UploadId=upload_id,
        )


# Module-level singleton
s3_service = S3Service()
