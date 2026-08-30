from __future__ import annotations

import hashlib
import io
import json
from datetime import timedelta
from typing import ClassVar

from minio import Minio
from minio.commonconfig import CopySource
from minio.error import S3Error

from ..core.config import get_settings

# S3 presigned URLs cannot outlive seven days.
MAX_PRESIGN_SECONDS = 7 * 24 * 3600


class ObjectStorage:
    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.minio_bucket
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        # Object I/O uses the private service endpoint. Browser-facing
        # presigned URLs must be signed for the public host because the host is
        # part of the S3 signature and cannot be rewritten afterwards.
        self.presign_client = Minio(
            settings.minio_public_endpoint or settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
            # Supplying the known region prevents the SDK from contacting the
            # browser-only public hostname during URL generation.
            region=settings.minio_region,
        )

    # Buckets are not deleted at runtime, so once a process has seen one exist it stays
    # true for that process. Without this, every write paid an extra round trip to ask a
    # question already answered - and ObjectStorage is constructed per call site, so an
    # instance-level cache would never hit.
    _known_buckets: ClassVar[set[str]] = set()

    @classmethod
    def reset_bucket_cache(cls) -> None:
        """Forget which buckets are known. For tests that swap the underlying client."""
        cls._known_buckets.clear()

    def ensure_bucket(self) -> None:
        if self.bucket in ObjectStorage._known_buckets:
            return
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
        ObjectStorage._known_buckets.add(self.bucket)

    def upload_url(self, object_key: str, *, ttl_seconds: int | None = None) -> str:
        expires = ttl_seconds if ttl_seconds is not None else get_settings().upload_url_ttl_seconds
        return self.presign_client.presigned_put_object(
            self.bucket,
            object_key,
            expires=timedelta(seconds=self._clamp(expires)),
        )

    def download_url(self, object_key: str, *, ttl_seconds: int | None = None) -> str:
        """Presigned GET URL.

        Defaults to a short browser-facing lifetime. Compute jobs pass an explicit
        ttl covering their queue wait plus runtime, because a job that pends for hours
        must still be able to fetch its inputs when it finally starts.
        """
        expires = ttl_seconds if ttl_seconds is not None else 900
        return self.presign_client.presigned_get_object(
            self.bucket, object_key, expires=timedelta(seconds=self._clamp(expires))
        )

    def _clamp(self, seconds: int) -> int:
        return max(60, min(int(seconds), MAX_PRESIGN_SECONDS))

    def read_json(self, object_key: str) -> dict:
        response = self.client.get_object(self.bucket, object_key)
        try:
            data = json.loads(response.read().decode("utf-8"))
        finally:
            response.close()
            response.release_conn()
        if not isinstance(data, dict):
            raise ValueError("manifest_root_must_be_object")
        return data

    def read_bytes(self, object_key: str, *, max_bytes: int | None = None) -> bytes:
        response = self.client.get_object(self.bucket, object_key)
        try:
            data = response.read((max_bytes + 1) if max_bytes is not None else -1)
        finally:
            response.close()
            response.release_conn()
        if max_bytes is not None and len(data) > max_bytes:
            raise ValueError("object_too_large")
        return data

    def stream(self, object_key: str, *, chunk_size: int = 1024 * 1024):
        """Yield an object in chunks.

        Scientific inputs can be far larger than memory, so anything that moves whole
        objects between systems streams rather than calling read_bytes.
        """
        response = self.client.get_object(self.bucket, object_key)
        try:
            yield from response.stream(chunk_size)
        finally:
            response.close()
            response.release_conn()

    def put_stream(self, object_key: str, body, length: int, content_type: str) -> None:
        self.ensure_bucket()
        self.client.put_object(self.bucket, object_key, body, length, content_type=content_type)

    def put_json(self, object_key: str, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.ensure_bucket()
        self.client.put_object(self.bucket, object_key, io.BytesIO(body), len(body), content_type="application/json")

    def put_bytes(self, object_key: str, body: bytes, content_type: str) -> None:
        self.ensure_bucket()
        self.client.put_object(self.bucket, object_key, io.BytesIO(body), len(body), content_type=content_type)

    def inspect_and_hash(self, object_key: str) -> tuple[int, str]:
        stat = self.client.stat_object(self.bucket, object_key)
        response = self.client.get_object(self.bucket, object_key)
        digest = hashlib.sha256()
        try:
            for chunk in response.stream(1024 * 1024):
                digest.update(chunk)
        finally:
            response.close()
            response.release_conn()
        if stat.size is None:
            raise RuntimeError("object_size_missing")
        return stat.size, digest.hexdigest()

    def promote(self, source_key: str, target_key: str) -> None:
        try:
            self.client.stat_object(self.bucket, target_key)
        except S3Error as exc:
            if exc.code not in {"NoSuchKey", "NoSuchObject"}:
                raise
            self.client.copy_object(self.bucket, target_key, CopySource(self.bucket, source_key))
        self.client.remove_object(self.bucket, source_key)

    def copy(self, source_key: str, target_key: str) -> None:
        self.ensure_bucket()
        try:
            self.client.stat_object(self.bucket, target_key)
        except S3Error as exc:
            if exc.code not in {"NoSuchKey", "NoSuchObject"}:
                raise
            self.client.copy_object(self.bucket, target_key, CopySource(self.bucket, source_key))

    def remove(self, object_key: str) -> None:
        self.client.remove_object(self.bucket, object_key)

    def exists(self, object_key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, object_key)
            return True
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject"}:
                return False
            raise

    def list_objects(self):
        return self.client.list_objects(self.bucket, recursive=True)

    def put_file(self, object_key: str, path: str, content_type: str = "application/octet-stream") -> None:
        self.ensure_bucket()
        if not self.exists(object_key):
            self.client.fput_object(self.bucket, object_key, path, content_type=content_type)
