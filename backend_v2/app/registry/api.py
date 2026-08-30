from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from ..artifacts.repository import ArtifactRepository
from ..core.database import get_session
from ..core.etag import etag, parse_if_match
from ..core.pagination import decode_cursor, encode_cursor
from ..core.problem import DomainError
from ..identity.deps import current_user, require_roles
from ..identity.models import User
from ..platform.operations import enqueue_operation
from .models import (
    ComputeNode,
    LLMProvider,
    MethodPlugin,
    ModelPlugin,
    ParameterCatalog,
    RegistryServer,
    ScriptAsset,
)
from .repository import RegistryRepository
from .schemas import (
    ComputeNodeCreate,
    ComputeNodePage,
    ComputeNodeResponse,
    LLMProviderCreate,
    LLMProviderPage,
    LLMProviderResponse,
    MethodPluginCreate,
    MethodPluginPage,
    MethodPluginResponse,
    ModelPluginCreate,
    ModelPluginPage,
    ModelPluginResponse,
    ParameterCatalogPage,
    ParameterCatalogResponse,
    PluginSnapshot,
    RegistryDeactivateResponse,
    RegistryOperationAccepted,
    RegistryResourceUpdate,
    RegistryServerCreate,
    RegistryServerPage,
    RegistryServerResponse,
    ScriptAssetCreate,
    ScriptAssetPage,
    ScriptAssetResponse,
)
from .service import (
    create_resource,
    disable_resource,
    update_resource,
)
from .service import (
    create_script_asset as create_script_asset_service,
)

router = APIRouter(prefix="/registry", tags=["registry"])


def _rows(session: Session, model: Any, cursor: str | None, limit: int) -> tuple[list[Any], str | None]:
    after = decode_cursor(cursor)
    rows = RegistryRepository(session).rows(model, after, limit)
    page = rows[:limit]
    return page, encode_cursor(page[-1].id) if len(rows) > limit and page else None


def _resource(session: Session, model: Any, resource_id: uuid.UUID, code: str) -> Any:
    row = RegistryRepository(session).resource(model, resource_id)
    if row is None:
        raise DomainError(code, "Registry resource was not found", status_code=404)
    return row


def _update(row: Any, payload: RegistryResourceUpdate, if_match: str | None) -> Any:
    return update_resource(row, payload, parse_if_match(if_match))


def _disable(row: Any, if_match: str | None) -> RegistryDeactivateResponse:
    return disable_resource(row, parse_if_match(if_match))


@router.get("/servers", response_model=RegistryServerPage)
def list_servers(
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> RegistryServerPage:
    rows, next_cursor = _rows(session, RegistryServer, cursor, limit)
    return RegistryServerPage(
        items=[RegistryServerResponse.model_validate(row) for row in rows], next_cursor=next_cursor
    )


@router.post(
    "/servers",
    response_model=RegistryServerResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "registry.server.create"},
)
def create_server(
    payload: RegistryServerCreate, session: Session = Depends(get_session), user: User = Depends(require_roles("admin"))
) -> RegistryServerResponse:
    row = create_resource(session, "server", payload.model_dump())
    return RegistryServerResponse.model_validate(row)


@router.get("/servers/{server_id}", response_model=RegistryServerResponse)
def get_server(
    server_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> RegistryServerResponse:
    row = _resource(session, RegistryServer, server_id, "registry_server_not_found")
    response.headers["ETag"] = etag(row.version)
    return RegistryServerResponse.model_validate(row)


@router.patch(
    "/servers/{server_id}",
    response_model=RegistryServerResponse,
    openapi_extra={"x-permission": "registry.server.update"},
)
def patch_server(
    server_id: uuid.UUID,
    payload: RegistryResourceUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> RegistryServerResponse:
    row = _update(_resource(session, RegistryServer, server_id, "registry_server_not_found"), payload, if_match)
    response.headers["ETag"] = etag(row.version)
    return RegistryServerResponse.model_validate(row)


@router.delete(
    "/servers/{server_id}",
    response_model=RegistryDeactivateResponse,
    openapi_extra={"x-permission": "registry.server.disable"},
)
def disable_server(
    server_id: uuid.UUID,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> RegistryDeactivateResponse:
    return _disable(_resource(session, RegistryServer, server_id, "registry_server_not_found"), if_match)


@router.get("/compute-nodes", response_model=ComputeNodePage)
def list_compute_nodes(
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ComputeNodePage:
    rows, next_cursor = _rows(session, ComputeNode, cursor, limit)
    return ComputeNodePage(items=[ComputeNodeResponse.model_validate(row) for row in rows], next_cursor=next_cursor)


@router.post(
    "/compute-nodes",
    response_model=ComputeNodeResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "registry.compute_node.create"},
)
def create_compute_node(
    payload: ComputeNodeCreate, session: Session = Depends(get_session), user: User = Depends(require_roles("admin"))
) -> ComputeNodeResponse:
    row = create_resource(session, "compute_node", payload.model_dump())
    return ComputeNodeResponse.model_validate(row)


@router.get("/compute-nodes/{node_id}", response_model=ComputeNodeResponse)
def get_compute_node(
    node_id: uuid.UUID, response: Response, session: Session = Depends(get_session), user: User = Depends(current_user)
) -> ComputeNodeResponse:
    row = _resource(session, ComputeNode, node_id, "compute_node_not_found")
    response.headers["ETag"] = etag(row.version)
    return ComputeNodeResponse.model_validate(row)


@router.patch(
    "/compute-nodes/{node_id}",
    response_model=ComputeNodeResponse,
    openapi_extra={"x-permission": "registry.compute_node.update"},
)
def patch_compute_node(
    node_id: uuid.UUID,
    payload: RegistryResourceUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> ComputeNodeResponse:
    row = _update(_resource(session, ComputeNode, node_id, "compute_node_not_found"), payload, if_match)
    response.headers["ETag"] = etag(row.version)
    return ComputeNodeResponse.model_validate(row)


@router.delete(
    "/compute-nodes/{node_id}",
    response_model=RegistryDeactivateResponse,
    openapi_extra={"x-permission": "registry.compute_node.disable"},
)
def disable_compute_node(
    node_id: uuid.UUID,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> RegistryDeactivateResponse:
    return _disable(_resource(session, ComputeNode, node_id, "compute_node_not_found"), if_match)


@router.get("/model-plugins", response_model=ModelPluginPage)
def list_model_plugins(
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ModelPluginPage:
    rows, next_cursor = _rows(session, ModelPlugin, cursor, limit)
    return ModelPluginPage(items=[ModelPluginResponse.model_validate(row) for row in rows], next_cursor=next_cursor)


@router.post(
    "/model-plugins",
    response_model=ModelPluginResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "registry.model_plugin.create"},
)
def create_model_plugin(
    payload: ModelPluginCreate, session: Session = Depends(get_session), user: User = Depends(require_roles("admin"))
) -> ModelPluginResponse:
    row = create_resource(session, "model_plugin", payload.model_dump())
    return ModelPluginResponse.model_validate(row)


@router.get("/model-plugins/{plugin_id}", response_model=ModelPluginResponse)
def get_model_plugin(
    plugin_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ModelPluginResponse:
    row = _resource(session, ModelPlugin, plugin_id, "plugin_not_found")
    response.headers["ETag"] = etag(row.version)
    return ModelPluginResponse.model_validate(row)


@router.patch(
    "/model-plugins/{plugin_id}",
    response_model=ModelPluginResponse,
    openapi_extra={"x-permission": "registry.model_plugin.update"},
)
def patch_model_plugin(
    plugin_id: uuid.UUID,
    payload: RegistryResourceUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> ModelPluginResponse:
    row = _update(_resource(session, ModelPlugin, plugin_id, "plugin_not_found"), payload, if_match)
    response.headers["ETag"] = etag(row.version)
    return ModelPluginResponse.model_validate(row)


@router.delete(
    "/model-plugins/{plugin_id}",
    response_model=RegistryDeactivateResponse,
    openapi_extra={"x-permission": "registry.model_plugin.disable"},
)
def disable_model_plugin(
    plugin_id: uuid.UUID,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> RegistryDeactivateResponse:
    return _disable(_resource(session, ModelPlugin, plugin_id, "plugin_not_found"), if_match)


@router.get("/method-plugins", response_model=MethodPluginPage)
def list_method_plugins(
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> MethodPluginPage:
    rows, next_cursor = _rows(session, MethodPlugin, cursor, limit)
    return MethodPluginPage(items=[MethodPluginResponse.model_validate(row) for row in rows], next_cursor=next_cursor)


@router.post(
    "/method-plugins",
    response_model=MethodPluginResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "registry.method_plugin.create"},
)
def create_method_plugin(
    payload: MethodPluginCreate, session: Session = Depends(get_session), user: User = Depends(require_roles("admin"))
) -> MethodPluginResponse:
    row = create_resource(session, "method_plugin", payload.model_dump())
    return MethodPluginResponse.model_validate(row)


@router.get("/method-plugins/{plugin_id}", response_model=MethodPluginResponse)
def get_method_plugin(
    plugin_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> MethodPluginResponse:
    row = _resource(session, MethodPlugin, plugin_id, "method_plugin_not_found")
    response.headers["ETag"] = etag(row.version)
    return MethodPluginResponse.model_validate(row)


@router.patch(
    "/method-plugins/{plugin_id}",
    response_model=MethodPluginResponse,
    openapi_extra={"x-permission": "registry.method_plugin.update"},
)
def patch_method_plugin(
    plugin_id: uuid.UUID,
    payload: RegistryResourceUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> MethodPluginResponse:
    row = _update(_resource(session, MethodPlugin, plugin_id, "method_plugin_not_found"), payload, if_match)
    response.headers["ETag"] = etag(row.version)
    return MethodPluginResponse.model_validate(row)


@router.delete(
    "/method-plugins/{plugin_id}",
    response_model=RegistryDeactivateResponse,
    openapi_extra={"x-permission": "registry.method_plugin.disable"},
)
def disable_method_plugin(
    plugin_id: uuid.UUID,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> RegistryDeactivateResponse:
    return _disable(_resource(session, MethodPlugin, plugin_id, "method_plugin_not_found"), if_match)


@router.get("/llm-providers", response_model=LLMProviderPage)
def list_llm_providers(
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> LLMProviderPage:
    rows, next_cursor = _rows(session, LLMProvider, cursor, limit)
    return LLMProviderPage(items=[LLMProviderResponse.model_validate(row) for row in rows], next_cursor=next_cursor)


@router.post(
    "/llm-providers",
    response_model=LLMProviderResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "registry.llm_provider.create"},
)
def create_llm_provider(
    payload: LLMProviderCreate, session: Session = Depends(get_session), user: User = Depends(require_roles("admin"))
) -> LLMProviderResponse:
    row = create_resource(session, "llm_provider", payload.model_dump())
    return LLMProviderResponse.model_validate(row)


@router.get("/llm-providers/{provider_id}", response_model=LLMProviderResponse)
def get_llm_provider(
    provider_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> LLMProviderResponse:
    row = _resource(session, LLMProvider, provider_id, "llm_provider_not_found")
    response.headers["ETag"] = etag(row.version)
    return LLMProviderResponse.model_validate(row)


@router.patch(
    "/llm-providers/{provider_id}",
    response_model=LLMProviderResponse,
    openapi_extra={"x-permission": "registry.llm_provider.update"},
)
def patch_llm_provider(
    provider_id: uuid.UUID,
    payload: RegistryResourceUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> LLMProviderResponse:
    row = _update(_resource(session, LLMProvider, provider_id, "llm_provider_not_found"), payload, if_match)
    response.headers["ETag"] = etag(row.version)
    return LLMProviderResponse.model_validate(row)


@router.delete(
    "/llm-providers/{provider_id}",
    response_model=RegistryDeactivateResponse,
    openapi_extra={"x-permission": "registry.llm_provider.disable"},
)
def disable_llm_provider(
    provider_id: uuid.UUID,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> RegistryDeactivateResponse:
    return _disable(_resource(session, LLMProvider, provider_id, "llm_provider_not_found"), if_match)


@router.get("/model-plugins/{plugin_id}/snapshot", response_model=PluginSnapshot)
def get_plugin_snapshot(
    plugin_id: uuid.UUID, session: Session = Depends(get_session), user: User = Depends(current_user)
) -> PluginSnapshot:
    from ..core.problem import DomainError

    row = RegistryRepository(session).plugin(plugin_id)
    if row is None:
        raise DomainError("plugin_not_found", "Model plugin was not found", status_code=404)
    return PluginSnapshot.model_validate(row, from_attributes=True)


@router.get("/parameter-catalog", response_model=ParameterCatalogPage)
def list_parameter_catalog(
    plugin_id: uuid.UUID | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ParameterCatalogPage:
    after = decode_cursor(cursor)
    rows = RegistryRepository(session).parameter_catalog(plugin_id, after, limit)
    page = rows[:limit]
    next_cursor = encode_cursor(page[-1].id) if len(rows) > limit and page else None
    return ParameterCatalogPage(
        items=[ParameterCatalogResponse.model_validate(row) for row in page], next_cursor=next_cursor
    )


@router.get("/parameter-catalog/{catalog_id}", response_model=ParameterCatalogResponse)
def get_parameter_catalog_entry(
    catalog_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ParameterCatalogResponse:
    row = _resource(session, ParameterCatalog, catalog_id, "parameter_catalog_entry_not_found")
    response.headers["ETag"] = etag(row.version)
    return ParameterCatalogResponse.model_validate(row)


@router.get("/script-assets", response_model=ScriptAssetPage)
def list_script_assets(
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ScriptAssetPage:
    rows, next_cursor = _rows(session, ScriptAsset, cursor, limit)
    return ScriptAssetPage(items=[ScriptAssetResponse.model_validate(row) for row in rows], next_cursor=next_cursor)


@router.get("/script-assets/{asset_id}", response_model=ScriptAssetResponse)
def get_script_asset(
    asset_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ScriptAssetResponse:
    row = _resource(session, ScriptAsset, asset_id, "script_asset_not_found")
    response.headers["ETag"] = etag(row.version)
    return ScriptAssetResponse.model_validate(row)


@router.post(
    "/script-assets",
    response_model=ScriptAssetResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "registry.script_asset.create"},
)
def create_script_asset(
    payload: ScriptAssetCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> ScriptAssetResponse:
    artifact = ArtifactRepository(session).artifact(payload.artifact_id)
    if artifact is None or artifact.status != "available":
        raise DomainError("artifact_not_found", "Available script artifact was not found", status_code=404)
    row = create_script_asset_service(session, payload, artifact, user)
    return ScriptAssetResponse.model_validate(row, from_attributes=True)


def _operation(session: Session, topic: str, resource_id: uuid.UUID, user: User) -> RegistryOperationAccepted:
    operation = enqueue_operation(
        session,
        topic=topic,
        resource_type="registry_resource",
        resource_id=resource_id,
        user=user,
        payload={"resource_id": str(resource_id)},
    )
    return RegistryOperationAccepted(operation_id=operation.id, resource_id=resource_id)


@router.post(
    "/model-plugins/{plugin_id}/validations",
    response_model=RegistryOperationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "registry.validate"},
)
def validate_model_plugin(
    plugin_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> RegistryOperationAccepted:
    if RegistryRepository(session).plugin(plugin_id) is None:
        raise DomainError("plugin_not_found", "Model plugin was not found", status_code=404)
    return _operation(session, "registry.model_plugin.validate", plugin_id, user)


@router.post(
    "/compute-nodes/{node_id}/health-checks",
    response_model=RegistryOperationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "registry.validate"},
)
def check_compute_node(
    node_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> RegistryOperationAccepted:
    if RegistryRepository(session).resource(ComputeNode, node_id) is None:
        raise DomainError("compute_node_not_found", "Compute node was not found", status_code=404)
    return _operation(session, "registry.compute_node.health", node_id, user)


@router.post(
    "/servers/{server_id}/connection-tests",
    response_model=RegistryOperationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "registry.validate"},
)
def test_server_connection(
    server_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> RegistryOperationAccepted:
    if RegistryRepository(session).resource(RegistryServer, server_id) is None:
        raise DomainError("registry_server_not_found", "Registry server was not found", status_code=404)
    return _operation(session, "registry.server.test", server_id, user)
