"""Pluggable interpretation of a job's collected outputs.

Turning raw files into candidates and experiment results used to be hardcoded inside
``collect_job``: it read ``metadata.candidate`` / ``metadata.experiment_result`` from the
output manifest, which meant every model container had to emit BDA-shaped JSON itself.
That pushed platform knowledge into each plugin's wrapper.

A parser moves that translation into the platform. A plugin names one via
``ModelPlugin.output_parser``; when it names none, ``manifest_metadata`` preserves the
existing behaviour exactly, so plugins written before this interface keep working.

Adding support for a new model means writing one function and registering it::

    @register_parser("my_model")
    def parse(ctx: ParseContext) -> ParsedOutputs:
        ...
"""

from __future__ import annotations

from .base import (
    ParseContext,
    ParsedCandidate,
    ParsedExperimentResult,
    ParsedMetric,
    ParsedOutputs,
    available_parsers,
    get_parser,
    register_parser,
)

# Importing the modules is what registers them.
from . import (  # noqa: E402, F401  isort:skip
    alphafold2_superfold,
    manifest_metadata,
    proteinhunter,
    proteinmpnn,
)

__all__ = [
    "ParseContext",
    "ParsedCandidate",
    "ParsedExperimentResult",
    "ParsedMetric",
    "ParsedOutputs",
    "available_parsers",
    "get_parser",
    "register_parser",
]
