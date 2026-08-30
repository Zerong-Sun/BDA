"""What actually differs between two runs.

A causal claim in this platform is always a comparison: this run against that one, with a
stated set of parameters changed. The cannabinoid binder project rested entirely on such
comparisons - 90 against 50, a replicate at identical settings, an arm differing only by a
contact constraint - and the only evidence that any of them was single-variable was a diff
its author ran by hand and pasted into a document.

Computing the diff here, from the stored node parameters, moves that from testimony to
observation: the platform states what changed because it looked, and an author who claims a
controlled comparison can be contradicted by the record.
"""

from __future__ import annotations

from typing import Any

# A run with no ancestor is the thing others are compared against; one whose parameters are
# indistinguishable from its ancestor is a repeat of the same experiment; anything else
# varies something and has to say what.
ARM_BASELINE = "baseline"
ARM_REPLICATE = "replicate"
ARM_VARIANT = "variant"


def diff_parameters(baseline: dict[str, dict], current: dict[str, dict]) -> dict[str, dict]:
    """Parameter differences between two runs, keyed by node key then parameter name.

    Both arguments map a node key to that node's parameters. Nodes present on only one side
    are reported whole, because adding or removing a step is as much a change as retuning
    one. Values are compared as stored; no normalisation is attempted, since a parameter
    that changed type has changed.
    """
    differences: dict[str, dict] = {}
    for node_key in sorted(set(baseline) | set(current)):
        before = baseline.get(node_key)
        after = current.get(node_key)
        if before is None:
            differences[node_key] = {"node": {"from": None, "to": "added"}}
            continue
        if after is None:
            differences[node_key] = {"node": {"from": "present", "to": None}}
            continue
        node_diff = {
            name: {"from": before.get(name), "to": after.get(name)}
            for name in sorted(set(before) | set(after))
            if before.get(name) != after.get(name)
        }
        if node_diff:
            differences[node_key] = node_diff
    return differences


def arm_label_for(derived_from: Any, differences: dict[str, dict]) -> str:
    if derived_from is None:
        return ARM_BASELINE
    return ARM_REPLICATE if not differences else ARM_VARIANT


def varied_parameter_names(differences: dict[str, dict]) -> list[str]:
    """Flat list of what changed, for reading at a glance."""
    return sorted({name for node_diff in differences.values() for name in node_diff})


def describe(differences: dict[str, dict]) -> str:
    """One line a scientist can read, e.g. 'percent_x' or '3 parameters across 2 nodes'."""
    names = varied_parameter_names(differences)
    if not names:
        return "no parameter differences"
    if len(names) == 1:
        return names[0]
    return f"{len(names)} parameters across {len(differences)} node(s)"
