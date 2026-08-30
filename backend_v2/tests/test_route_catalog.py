from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from backend_v2.app.compute.scripts import _SAFE_PARAMETER_NAME
from backend_v2.app.copilot.route_catalog import (
    ROUTE_CATALOG,
    ParameterRecommendation,
    RouteStep,
    recommended_parameters,
    routes_for,
)

_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic/versions/0033_register_design_plugins.py"
)
_spec = importlib.util.spec_from_file_location("register_design_plugins", _MIGRATION)
assert _spec and _spec.loader
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
PLUGINS = _module.PLUGINS


def step(*recommendations: ParameterRecommendation) -> RouteStep:
    return RouteStep(plugin_key="RFdiffusion", purpose="generate", recommendations=recommendations)


ZERO_NOISE = ParameterRecommendation(names=("noise_scale_ca",), value=0, reason="")
STEPS = ParameterRecommendation(names=("diffuser_T", "timesteps", "T"), value=50, reason="")


def test_a_declared_parameter_is_applied() -> None:
    schema = {"type": "object", "properties": {"noise_scale_ca": {"type": "number"}}}

    parameters, dropped = recommended_parameters(step(ZERO_NOISE), schema)

    assert parameters == {"noise_scale_ca": 0}
    assert dropped == []


def test_an_undeclared_parameter_is_dropped_with_a_note() -> None:
    """A key the plugin never declared would become a preflight blocker, not a default."""
    schema = {"type": "object", "properties": {"something_else": {"type": "number"}}}

    parameters, dropped = recommended_parameters(step(ZERO_NOISE), schema)

    assert parameters == {}
    assert len(dropped) == 1 and "noise_scale_ca" in dropped[0]


def test_a_declared_parameter_that_rejects_the_value_is_dropped() -> None:
    schema = {"type": "object", "properties": {"noise_scale_ca": {"type": "string"}}}

    parameters, dropped = recommended_parameters(step(ZERO_NOISE), schema)

    assert parameters == {}
    assert dropped


def test_the_first_declared_alias_wins() -> None:
    schema = {
        "type": "object",
        "properties": {"timesteps": {"type": "integer"}, "T": {"type": "integer"}},
    }

    parameters, _ = recommended_parameters(step(STEPS), schema)

    assert parameters == {"timesteps": 50}


@pytest.mark.parametrize("schema", [{}, None, "not-a-schema", {"properties": "invalid"}])
def test_absent_or_malformed_schemas_apply_nothing(schema: object) -> None:
    parameters, dropped = recommended_parameters(step(ZERO_NOISE), schema)

    assert parameters == {}
    assert dropped


def test_a_malformed_property_subschema_is_not_guessed_past() -> None:
    schema = {"type": "object", "properties": {"noise_scale_ca": {"type": "not-a-real-type"}}}

    parameters, dropped = recommended_parameters(step(ZERO_NOISE), schema)

    assert parameters == {}
    assert dropped


def test_routes_without_a_structure_only_offer_acquisition() -> None:
    routes = routes_for(has_structure=False)

    assert [route.route_id for route in routes] == ["structure-acquisition"]


def test_routes_with_a_structure_offer_the_binder_arms_pooled_first() -> None:
    routes = routes_for(has_structure=True)

    assert [route.route_id for route in routes] == [
        "de-novo-binder-pooled",
        "de-novo-binder-focused",
    ]


def test_every_catalog_route_has_steps_and_a_unique_id() -> None:
    ids = [route.route_id for route in ROUTE_CATALOG]

    assert len(ids) == len(set(ids))
    assert all(route.steps for route in ROUTE_CATALOG)
    assert all(route.summary and route.label for route in ROUTE_CATALOG)


def test_every_recommended_name_survives_the_script_renderer() -> None:
    """compute/scripts.py exports only ``^[a-z][a-z0-9_]*$`` as shell variables.

    A name outside that set validates against the plugin schema, gets written onto the
    node, and is then silently dropped from the rendered command — the parameter looks
    applied everywhere except in what actually runs.
    """
    offenders = [
        name
        for route in ROUTE_CATALOG
        for step in route.steps
        for recommendation in step.recommendations
        for name in recommendation.names
        if not _SAFE_PARAMETER_NAME.fullmatch(name)
    ]

    assert offenders == []


def test_registered_plugins_declare_every_recommendation_the_catalog_makes() -> None:
    """The migration and the catalog have to agree, or the routes ship no defaults."""
    schemas = {plugin["plugin_key"]: plugin["parameter_schema"] for plugin in PLUGINS}

    missing = []
    for route in ROUTE_CATALOG:
        for route_step in route.steps:
            schema = schemas.get(route_step.plugin_key)
            if schema is None:
                missing.append(f"{route.route_id}: no registered plugin for {route_step.plugin_key}")
                continue
            parameters, dropped = recommended_parameters(route_step, schema)
            missing.extend(dropped)
            assert len(parameters) == len(route_step.recommendations)

    assert missing == []
