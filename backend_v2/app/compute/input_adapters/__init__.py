"""Synthesise inputs a model needs but a workflow cannot bind directly.

Mirror image of ``compute.parsers``. A parser turns a model's native output into platform
records; an input adapter turns platform records into a model's native input.

The motivating case is AlphaFold 3, which takes its sequences inside a JSON job
specification rather than as a sequence file. Declared that way, an AF3 node could not be
wired downstream of anything - its only input port was an opaque parameter. An adapter
builds that JSON from bound sequence inputs, so AF3 joins the graph like any other node.

Adapters run on the worker during dispatch, before the manifest is written, so they work
for every compute backend and need nothing installed on the cluster.
"""

from __future__ import annotations

from .base import (
    AdapterContext,
    GeneratedInput,
    available_input_adapters,
    get_input_adapter,
    register_input_adapter,
)

# Importing the modules is what registers them.
from . import af3_fold_input  # noqa: E402, F401  isort:skip

__all__ = [
    "AdapterContext",
    "GeneratedInput",
    "available_input_adapters",
    "get_input_adapter",
    "register_input_adapter",
]
