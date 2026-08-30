from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

NAMESPACE = uuid.UUID("be4bc69f-3e74-4e64-a661-86e3600de241")


def stable_id(table: str, legacy_id: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{table}:{legacy_id}")


def local_artifact_path(storage_uri: str, artifact_roots: list[Path]) -> Path | None:
    roots = [root.resolve() for root in artifact_roots]
    if storage_uri.startswith("artifact://"):
        relative = Path(storage_uri.removeprefix("artifact://"))
        for root in roots:
            candidates = [(root / relative).resolve()]
            if relative.parts and relative.parts[0] == root.name:
                candidates.append((root / Path(*relative.parts[1:])).resolve())
            for candidate in candidates:
                if candidate.is_relative_to(root) and candidate.is_file():
                    return candidate
        return None
    if storage_uri.startswith("file://"):
        candidate = Path(storage_uri.removeprefix("file://")).resolve()
        return candidate if candidate.is_file() and any(candidate.is_relative_to(root) for root in roots) else None
    return None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
