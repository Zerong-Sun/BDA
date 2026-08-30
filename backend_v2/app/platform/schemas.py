import uuid

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str = "bda-v2"
    checks: dict[str, str] | None = None


class LegacyIdResolution(BaseModel):
    entity_type: str
    legacy_id: str
    id: uuid.UUID
