"""Id -> sequence -> analysis. The one impure step, and one privacy rule.

Same shape as `structures/service.py`: the kernels are pure, and this resolves
what the caller named into the text they operate on. Three sources, because a
sequence lives in three places in this platform and a person asking "is this
construct sensible" does not care which:

* a **candidate** carries its designed sequence in `properties["sequence"]`,
  written there by the ProteinMPNN and ProteinHunter parsers - the same key
  `wetlab.service` reads when promoting a design to the bench;
* a **target** carries the sequence being designed against;
* a **protein** is a registered construct in the project's library.

**The analysis is returned; the sequence is not.** `wetlab.models.Protein` says
its `sequence` column is the only plaintext copy and that the API exposes the
digest instead - `ProteinRead` omits the sequence deliberately. A tool that
resolved a protein id and handed the plaintext back to a model would undo that
in one line, so every result here carries `sequence_sha256` and never the
residues. The kernels already refuse to echo the sequence; this adds the part
the kernels cannot know, which is where the text came from.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..candidates.models import Candidate
from ..core.problem import DomainError
from ..targets.models import Target
from ..wetlab.models import Protein
from . import codon, kernels


def _digest(sequence: str) -> str:
    """The fingerprint the protein library uses, computed the same way.

    Over the *sanitised* sequence, so the same construct pasted with line
    breaks or a trailing stop codon has one identity.
    """
    return hashlib.sha256(kernels.sanitise(sequence).encode()).hexdigest()


def _one_source(**named: Any) -> tuple[str, Any]:
    given = {name: value for name, value in named.items() if value}
    if len(given) != 1:
        raise DomainError(
            "sequence_source_ambiguous",
            "Name exactly one of sequence, candidate_id, target_id or protein_id.",
            status_code=422,
        )
    return next(iter(given.items()))


def resolve(
    session: Session,
    project_id: uuid.UUID,
    *,
    sequence: str | None = None,
    candidate_id: uuid.UUID | None = None,
    target_id: uuid.UUID | None = None,
    protein_id: uuid.UUID | None = None,
) -> tuple[str, dict[str, Any]]:
    """The sequence and a description of where it came from.

    A row that exists but holds no sequence is its own error: "this candidate
    has no sequence recorded" is actionable, and a 404 would send the reader
    looking for a candidate that is in front of them.
    """
    kind, value = _one_source(
        sequence=sequence, candidate_id=candidate_id, target_id=target_id, protein_id=protein_id
    )

    if kind == "sequence":
        text = str(value)
        return text, {"kind": "sequence", "sequence_sha256": _digest(text)}

    if kind == "candidate_id":
        candidate = session.scalar(
            select(Candidate).where(Candidate.id == value, Candidate.project_id == project_id)
        )
        if candidate is None:
            raise DomainError("candidate_not_found", "No such candidate in this project.", status_code=404)
        text = str((candidate.properties or {}).get("sequence") or "").strip()
        if not text:
            raise DomainError(
                "candidate_sequence_missing",
                f"Candidate {candidate.name!r} has no recorded sequence. A structure-only "
                "design has nothing for this analysis to read.",
                status_code=422,
            )
        return text, {
            "kind": "candidate",
            "id": str(candidate.id),
            "name": candidate.name,
            "sequence_sha256": _digest(text),
        }

    if kind == "target_id":
        target = session.scalar(
            select(Target).where(Target.id == value, Target.project_id == project_id)
        )
        if target is None:
            raise DomainError("target_not_found", "No such target in this project.", status_code=404)
        text = str(target.sequence or "").strip()
        if not text:
            raise DomainError(
                "target_sequence_missing",
                f"Target {target.name!r} has no sequence recorded.",
                status_code=422,
            )
        return text, {
            "kind": "target",
            "id": str(target.id),
            "name": target.name,
            "sequence_sha256": _digest(text),
        }

    protein = session.scalar(
        select(Protein).where(Protein.id == value, Protein.project_id == project_id)
    )
    if protein is None:
        raise DomainError("protein_not_found", "No such protein in this project.", status_code=404)
    return str(protein.sequence), {
        "kind": "protein",
        "id": str(protein.id),
        "name": protein.name,
        # The library's own digest, not a recomputed one: if they ever disagree
        # the row is what identifies the construct everywhere else.
        "sequence_sha256": protein.sequence_sha256,
    }


def optimise_codons(
    session: Session,
    project_id: uuid.UUID,
    *,
    candidate_id: uuid.UUID | None = None,
    target_id: uuid.UUID | None = None,
    protein_id: uuid.UUID | None = None,
    host: str,
    avoid_sites: dict[str, str] | None = None,
    prefix: str = "",
    suffix: str = "",
    add_stop: bool = True,
    max_homopolymer: int = codon.MAX_HOMOPOLYMER,
) -> dict[str, Any]:
    """A DNA construct for whichever protein was named, and how it was built.

    The one place in this domain that returns a sequence. It is DNA rather than
    the protein, and it goes to the authenticated person who asked over HTTP -
    not through a copilot tool, whose results are written into the transcript.
    Nothing is stored: the construct is a function of the record and the
    constraints, both of which are in the response.
    """
    try:
        text, source = resolve(
            session,
            project_id,
            candidate_id=candidate_id,
            target_id=target_id,
            protein_id=protein_id,
        )
        result = codon.optimise(
            text,
            host=host,
            avoid_sites=avoid_sites,
            prefix=prefix,
            suffix=suffix,
            add_stop=add_stop,
            max_homopolymer=max_homopolymer,
        )
    except codon.CodonError as error:
        raise DomainError("codon_request_invalid", str(error), status_code=422) from error
    except kernels.SequenceError as error:
        # Either the stored text is not a protein, or the construct failed its
        # own round-trip check. Both mean no construct is returned.
        raise DomainError("sequence_unreadable", str(error), status_code=422) from error
    return {"source": source, **result}


def analyse(
    session: Session,
    project_id: uuid.UUID,
    *,
    sequence: str | None = None,
    candidate_id: uuid.UUID | None = None,
    target_id: uuid.UUID | None = None,
    protein_id: uuid.UUID | None = None,
    window: int = kernels.PATCH_WINDOW,
    threshold: float = kernels.PATCH_THRESHOLD,
) -> dict[str, Any]:
    """Liabilities, patches and properties for whichever sequence was named."""
    try:
        text, source = resolve(
            session,
            project_id,
            sequence=sequence,
            candidate_id=candidate_id,
            target_id=target_id,
            protein_id=protein_id,
        )
        result = kernels.analyse(text, window=window, threshold=threshold)
    except kernels.SequenceError as error:
        # Resolution sanitises too, to compute the digest, so a stored row
        # holding unreadable text raises here rather than in the analysis. Both
        # are the same answer to the reader: this text is not a protein.
        raise DomainError("sequence_unreadable", str(error), status_code=422) from error
    return {"source": source, **result}
