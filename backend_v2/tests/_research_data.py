"""Locate the research data store, and gate the tests that need it.

A number of private-environment tests read receptor structures, job configs and
deliverable bundles that are **not in public Git**. They are optional research
fixtures resolved through the external data boundary.

Those tests were silently broken in CI long before the split: the paths were
gitignored, so a clone never had them, and the failures were masked by the
lint step failing first. Gating them explicitly is what makes the suite honest
— a green run now means "everything runnable passed", not "the failures were
hidden".

Availability decides, not an opt-in flag: on a machine that has the store the
tests run and protect you; on CI or a fresh clone they skip. Set
`BDA_V2_REQUIRE_RESEARCH_FIXTURES=1` to turn a missing store into a failure
instead of a skip, for a machine that is supposed to have it.

    from backend_v2.tests._research_data import research_data, research_path

    pytestmark = research_data  # whole module
    SCRIPT = research_path("deliverables/foo/scripts/bar.py")
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from backend_v2.scripts._data_root import data_path, data_root

__all__ = ["research_data", "research_data_available", "research_path"]


def research_data_available() -> bool:
    """True when the research data store is present on this machine."""
    if os.environ.get("BDA_V2_REQUIRE_RESEARCH_FIXTURES") == "1":
        return True
    return data_root().is_dir()


def research_path(legacy_relative: str) -> Path:
    """A path inside the research store, addressed by its pre-split name."""
    return data_path(legacy_relative)


research_data = pytest.mark.skipif(
    not research_data_available(),
    reason=(
        "Requires the research data store (research-projects/, deliverables/), "
        "which is not part of a public clone. Set BDA_DATA_ROOT to an authorized "
        "store, or BDA_V2_REQUIRE_RESEARCH_FIXTURES=1 to fail instead of skip."
    ),
)
