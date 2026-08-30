"""A problem+json body must always be encodable, whatever a validator raised.

Pydantic puts the original exception object into an error's ``ctx`` when a validator
raises ``ValueError``. Passing that through untouched made the response encoder blow up
*while building the 422*, so the caller saw a serialization crash instead of the
validation message. This affects every schema that validates with a plain
``raise ValueError`` - compute, workflows and timeline all do.
"""

from __future__ import annotations

import json

from backend_v2.app.core.problem import _json_safe


def test_exception_objects_become_readable_strings() -> None:
    error = ValueError("entry_type must be one of ['decision', 'plan']")
    safe = _json_safe({"ctx": {"error": error}, "type": "value_error"})
    assert safe["ctx"]["error"] == str(error)
    json.dumps(safe)  # would raise if anything unencodable survived


def test_nested_structures_are_walked() -> None:
    payload = [{"loc": ("body", "entry_type"), "ctx": {"error": TypeError("nope")}}]
    safe = _json_safe(payload)
    assert safe[0]["loc"] == ["body", "entry_type"]
    assert safe[0]["ctx"]["error"] == "nope"
    json.dumps(safe)


def test_plain_json_values_are_left_alone() -> None:
    """Sanitising must not quietly restringify data that was already fine."""
    payload = {"a": 1, "b": 1.5, "c": True, "d": None, "e": "text", "f": [1, 2]}
    assert _json_safe(payload) == payload


def test_non_string_keys_are_coerced() -> None:
    assert _json_safe({1: "x"}) == {"1": "x"}
    json.dumps(_json_safe({1: "x"}))
