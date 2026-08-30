from __future__ import annotations

import hashlib
import json
from collections.abc import Generator
from types import SimpleNamespace

import pytest
from backend_v2.app.artifacts.storage import ObjectStorage
from minio.error import S3Error


class Response:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.closed = False
        self.released = False

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]

    def stream(self, _size: int):
        yield self.body[:2]
        yield self.body[2:]

    def close(self) -> None:
        self.closed = True

    def release_conn(self) -> None:
        self.released = True


class Client:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.bucket_present = False
        self.calls: list[tuple] = []
        self.bucket_exists_calls = 0

    def bucket_exists(self, bucket: str) -> bool:
        self.bucket_exists_calls += 1
        return self.bucket_present

    def make_bucket(self, bucket: str) -> None:
        self.bucket_present = True
        self.calls.append(("make_bucket", bucket))

    def presigned_put_object(self, bucket: str, key: str, **kwargs) -> str:
        return f"put://{bucket}/{key}"

    def presigned_get_object(self, bucket: str, key: str, **kwargs) -> str:
        return f"get://{bucket}/{key}"

    def get_object(self, bucket: str, key: str) -> Response:
        return Response(self.objects[key])

    def put_object(self, bucket: str, key: str, stream, length: int, *, content_type: str) -> None:
        self.objects[key] = stream.read(length)
        self.calls.append(("put", key, content_type))

    def stat_object(self, bucket: str, key: str):
        if key not in self.objects:
            raise S3Error(None, "NoSuchKey", "missing", key, None, None)
        return SimpleNamespace(size=len(self.objects[key]))

    def copy_object(self, bucket: str, key: str, source) -> None:
        self.objects[key] = self.objects[source.object_name]
        self.calls.append(("copy", source.object_name, key))

    def remove_object(self, bucket: str, key: str) -> None:
        self.objects.pop(key, None)

    def list_objects(self, bucket: str, *, recursive: bool):
        return [SimpleNamespace(object_name=key) for key in self.objects]

    def fput_object(self, bucket: str, key: str, path: str, *, content_type: str) -> None:
        self.calls.append(("fput", key, path, content_type))


@pytest.fixture(autouse=True)
def _forget_known_buckets() -> Generator[None]:
    """Each test gets a fresh fake client, so the process-level bucket cache must not
    carry a previous test's answer into it."""
    ObjectStorage.reset_bucket_cache()
    yield
    ObjectStorage.reset_bucket_cache()


@pytest.fixture
def storage() -> ObjectStorage:
    instance = object.__new__(ObjectStorage)
    instance.bucket = "artifacts"
    instance.client = Client()
    instance.presign_client = instance.client
    return instance


def test_bucket_existence_is_checked_once_per_process(storage) -> None:
    storage.ensure_bucket()
    storage.put_bytes("a.bin", b"a", "application/octet-stream")
    storage.put_bytes("b.bin", b"b", "application/octet-stream")
    storage.put_json("c.json", {})

    assert [call for call in storage.client.calls if call[0] == "make_bucket"] == [("make_bucket", "artifacts")]
    assert storage.client.bucket_exists_calls == 1


def test_object_storage_read_write_and_urls(storage, monkeypatch) -> None:
    monkeypatch.setattr(
        "backend_v2.app.artifacts.storage.get_settings",
        lambda: SimpleNamespace(upload_url_ttl_seconds=300),
    )
    storage.ensure_bucket()
    assert storage.client.bucket_present
    assert storage.upload_url("stage/x") == "put://artifacts/stage/x"
    assert storage.download_url("objects/x") == "get://artifacts/objects/x"

    storage.put_json("manifest.json", {"b": 2, "a": 1})
    assert storage.read_json("manifest.json") == {"a": 1, "b": 2}
    storage.put_bytes("data.bin", b"payload", "application/octet-stream")
    assert storage.read_bytes("data.bin") == b"payload"
    assert storage.inspect_and_hash("data.bin") == (7, hashlib.sha256(b"payload").hexdigest())
    assert [item.object_name for item in storage.list_objects()] == ["manifest.json", "data.bin"]
    storage.remove("data.bin")
    assert "data.bin" not in storage.client.objects


def test_object_storage_separates_internal_io_and_public_presign_endpoints(monkeypatch) -> None:
    clients: list[Client] = []

    def client_factory(endpoint: str, **options) -> Client:
        client = Client()
        client.endpoint = endpoint
        client.options = options
        clients.append(client)
        return client

    monkeypatch.setattr("backend_v2.app.artifacts.storage.Minio", client_factory)
    monkeypatch.setattr(
        "backend_v2.app.artifacts.storage.get_settings",
        lambda: SimpleNamespace(
            minio_bucket="artifacts",
            minio_endpoint="minio-v2:9000",
            minio_public_endpoint="localhost:9002",
            minio_access_key="test",
            minio_secret_key="test-secret",
            minio_secure=False,
            minio_region="us-east-1",
            upload_url_ttl_seconds=300,
        ),
    )

    storage = ObjectStorage()

    assert storage.client.endpoint == "minio-v2:9000"
    assert storage.presign_client.endpoint == "localhost:9002"
    assert storage.presign_client.options["region"] == "us-east-1"
    assert storage.upload_url("stage/x") == "put://artifacts/stage/x"


def test_object_storage_validation_and_file_dedup(storage, monkeypatch) -> None:
    storage.client.objects["array.json"] = json.dumps([1, 2]).encode()
    with pytest.raises(ValueError, match="manifest_root"):
        storage.read_json("array.json")
    storage.client.objects["large.bin"] = b"12345"
    with pytest.raises(ValueError, match="object_too_large"):
        storage.read_bytes("large.bin", max_bytes=3)

    monkeypatch.setattr(storage, "exists", lambda _key: False)
    storage.put_file("script.py", "/tmp/script.py", "text/x-python")
    assert any(call[0] == "fput" for call in storage.client.calls)
    monkeypatch.setattr(storage, "exists", lambda _key: True)
    before = len(storage.client.calls)
    storage.put_file("script.py", "/tmp/script.py", "text/x-python")
    assert len(storage.client.calls) == before


def test_object_storage_copy_is_non_destructive_and_idempotent(storage) -> None:
    storage.client.objects["source.cif"] = b"structure"

    storage.copy("source.cif", "copied.cif")
    storage.copy("source.cif", "copied.cif")

    assert storage.client.objects["source.cif"] == b"structure"
    assert storage.client.objects["copied.cif"] == b"structure"
    assert [call for call in storage.client.calls if call[0] == "copy"] == [
        ("copy", "source.cif", "copied.cif")
    ]
