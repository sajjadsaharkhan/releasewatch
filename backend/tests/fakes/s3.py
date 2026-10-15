"""The fake S3 (slice 16): an in-memory object store patched into ``s3_service``.

Covers what the app asks of S3 — put, get, presigned upload, presigned
download — so a test can seed an object with bytes and a MIME type, register
it through the attachment API, and read it back through a tool. Nothing
leaves the process. Tests that only need the presign call recorded keep their
own recorder (``tests/test_attachments.py``).
"""

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

BASE_URL = "https://fake-s3.test"


@dataclass
class StoredObject:
    data: bytes
    mime_type: str


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, StoredObject] = {}
        #: Every key whose bytes were read, in order — a read is the exception (A.6).
        self.reads: list[str] = []

    def install(self, monkeypatch, service) -> None:
        self._service = service
        for name in (
            "generate_presigned_upload", "upload_file", "get_object_bytes",
            "generate_presigned_download", "get_download_url", "object_exists",
            "get_file_info", "delete_file",
        ):
            monkeypatch.setattr(service, name, getattr(self, name))

    # ── Seeding ───────────────────────────────────────────────────────────────

    def put(self, s3_key: str, data: bytes, mime_type: str) -> None:
        self.objects[s3_key] = StoredObject(data=data, mime_type=mime_type)

    # ── The S3Service surface ─────────────────────────────────────────────────

    def generate_presigned_upload(
        self, file_type, filename: str, mime_type: str, max_size_mb: int = 50, **context: Any,
    ) -> dict[str, Any]:
        s3_key, file_id = self._service.build_key(file_type, filename=filename, **context)
        return {
            "upload_url": f"{BASE_URL}/upload",
            "fields": {"key": s3_key, "Content-Type": mime_type},
            "s3_key": s3_key,
            "file_id": file_id,
            "public_url": None,
        }

    def upload_file(
        self, file_data: bytes, file_type, filename: str, mime_type: str, **context: Any,
    ) -> dict[str, Any]:
        s3_key, file_id = self._service.build_key(file_type, filename=filename, **context)
        self.put(s3_key, file_data, mime_type)
        return {
            "s3_key": s3_key, "file_id": file_id, "public_url": None,
            "file_size_bytes": len(file_data),
        }

    def get_object_bytes(self, s3_key: str, max_bytes: int) -> bytes | None:
        obj = self.objects.get(s3_key)
        if obj is None or len(obj.data) > max_bytes:
            return None
        self.reads.append(s3_key)
        return obj.data

    def generate_presigned_download(self, s3_key: str, expiry_seconds: int | None = None) -> str:
        return f"{BASE_URL}/{quote(s3_key)}?X-Amz-Expires={expiry_seconds or 3600}"

    def get_download_url(self, s3_key: str, expiry_seconds: int | None = None) -> str:
        return self.generate_presigned_download(s3_key, expiry_seconds)

    def object_exists(self, s3_key: str) -> bool:
        return s3_key in self.objects

    def get_file_info(self, s3_key: str) -> dict[str, Any] | None:
        obj = self.objects.get(s3_key)
        if obj is None:
            return None
        return {"size_bytes": len(obj.data), "content_type": obj.mime_type}

    def delete_file(self, s3_key: str) -> None:
        self.objects.pop(s3_key, None)
