"""A molecular scene as data, in MolViewSpec's `.mvsj` tree.

An operator that says "the interface I mean is B:124-136, and these three
residues carry it" has, until now, had only prose to say it in. The obvious fix
is to let the model drive the viewer; this module is the argument against that.

**A scene is a value, not a sequence of calls.** MolViewSpec is Mol*'s own
declarative format: a tree of `download → parse → structure → component →
representation` nodes with colours, labels and a camera. Emitting one means the
scene can be stored beside the claim it illustrates, diffed when it changes,
attached to a decision record, and rendered by any MolViewSpec viewer rather
than only by this application's build of Mol*. A sequence of plugin calls can
do none of those things.

**It shows; it does not conclude.** Every function here takes residues it is
given and colours them. Nothing in this module decides that a residue is
important - that decision belongs to whoever produced the list, with the
evidence that supports it, and `structures/kernels.py` states the same rule for
measurements.

The emitted subset is deliberately small - download, parse, structure,
component, representation, colour, label, focus - because a subset that renders
identically everywhere is worth more here than coverage of the format.
"""

from __future__ import annotations

from typing import Any

#: The format version this module writes. MolViewSpec states it in the file so
#: a reader can refuse a tree it does not understand rather than rendering half
#: of it.
MVS_VERSION = "1"

#: Colours are part of the claim being made, so they are named here rather than
#: chosen per call site: one colour for "what I am pointing at" and one for the
#: rest of the molecule. Two surfaces using different colours for a hotspot
#: would look like two different kinds of thing.
HIGHLIGHT_COLOUR = "#e97953"
STRUCTURE_COLOUR = "#9aa79a"

MAX_HIGHLIGHTS = 200


class SceneError(ValueError):
    """The scene cannot be described as asked."""


def _node(kind: str, params: dict[str, Any] | None = None, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    node: dict[str, Any] = {"kind": kind}
    if params:
        node["params"] = params
    if children:
        node["children"] = children
    return node


def _residue_selector(residue: dict[str, Any]) -> dict[str, Any]:
    """One residue, addressed the way a person reads a structure file.

    `auth_asym_id` / `auth_seq_id` rather than the label numbering: the chain
    and number a person sees in a viewer, cites in a paper and types into a
    design tool are the author's, and silently switching to the canonical
    numbering would move every residue in files where the two differ.
    """
    chain = str(residue.get("chain") or residue.get("chain_id") or "").strip()
    number = residue.get("seq", residue.get("residue_seq"))
    if not chain or number is None:
        raise SceneError("A highlighted residue needs a chain and a residue number.")
    try:
        return {"auth_asym_id": chain, "auth_seq_id": int(number)}
    except (TypeError, ValueError) as error:
        raise SceneError(f"{number!r} is not a residue number.") from error


def scene(
    *,
    url: str,
    fmt: str,
    highlights: list[dict[str, Any]] | None = None,
    title: str = "",
    label: str = "",
    focus_on_highlights: bool = True,
) -> dict[str, Any]:
    """A `.mvsj` state: the structure, with the given residues picked out.

    `highlights` may be empty, and then the scene is just the structure - which
    is the honest rendering of "I have not identified anything yet", and is why
    an empty list is not an error.
    """
    picked = list(highlights or [])
    if len(picked) > MAX_HIGHLIGHTS:
        # A "highlight" of two hundred residues is a mis-specified selection
        # rather than a point being made, and rendering it silently would turn
        # the whole chain orange and say nothing.
        raise SceneError(
            f"A scene highlights at most {MAX_HIGHLIGHTS} residues; {len(picked)} were given."
        )
    if fmt not in {"pdb", "mmcif", "bcif"}:
        raise SceneError(f"{fmt!r} is not a structure format this scene can describe.")

    polymer = _node(
        "component",
        {"selector": "polymer"},
        [
            _node("representation", {"type": "cartoon"}, [
                _node("color", {"color": STRUCTURE_COLOUR}),
            ]),
        ],
    )
    children = [polymer]

    if picked:
        selectors = [_residue_selector(residue) for residue in picked]
        highlighted = _node(
            "component",
            {"selector": selectors},
            [
                _node("representation", {"type": "ball_and_stick"}, [
                    _node("color", {"color": HIGHLIGHT_COLOUR}),
                ]),
            ],
        )
        if label:
            # One label for the set rather than one per residue: a dozen
            # overlapping labels is a picture of nothing.
            highlighted["children"].append(_node("label", {"text": label}))
        if focus_on_highlights:
            highlighted["children"].append(_node("focus", {}))
        children.append(highlighted)

    root = _node(
        "root",
        None,
        [
            _node(
                "download",
                {"url": url},
                [
                    _node(
                        "parse",
                        {"format": fmt},
                        [_node("structure", {"type": "model"}, children)],
                    )
                ],
            )
        ],
    )
    return {
        "metadata": {"version": MVS_VERSION, "title": title or "BDA structure view"},
        "root": root,
    }


def residues_from_contacts(contacts: dict[str, Any], *, chain: str) -> list[dict[str, Any]]:
    """The residues of one chain that a contact list names.

    Takes the output of `kernels.contacts` unchanged, so a scene illustrating an
    interface is built from the same measurement the operator reported rather
    than from a second list assembled by hand.
    """
    side = "residue_a" if contacts.get("chain_a") == chain else "residue_b"
    seen: dict[tuple[str, int], dict[str, Any]] = {}
    for pair in contacts.get("pairs", []):
        residue = pair.get(side) or {}
        chain_id = str(residue.get("chain") or residue.get("chain_id") or chain)
        number = residue.get("seq", residue.get("residue_seq"))
        if number is None:
            continue
        seen[(chain_id, int(number))] = {"chain": chain_id, "seq": int(number)}
    return list(seen.values())
