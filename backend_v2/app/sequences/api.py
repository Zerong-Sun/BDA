"""Codon optimisation over HTTP.

Deliberately not a copilot tool. A tool call's result is recorded in
`copilot_messages.tool_calls`, so a construct returned there would be a second
plaintext copy of what the protein library keeps in exactly one place - the
same reason `analyse_sequence` takes ids and returns no residues. Here the DNA
goes to the authenticated person who asked for it, in the response body, and is
not stored.

`POST` for a computation that writes nothing is a compromise, and a knowing
one: the request carries a set of constraints too large for a query string,
and the platform already treats `workflow-runs/{id}/preview` and
`registry/validate` the same way. The cost is that the production read-only
gate (`BDA_V2_WRITES_ENABLED=false`) refuses it along with real writes.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..identity.deps import current_user
from ..identity.models import User
from ..projects.service import require_project
from .codon import hosts
from .schemas import CodonHostRead, CodonOptimiseRequest, CodonOptimiseResponse
from .service import optimise_codons

router = APIRouter(tags=["sequences"])


@router.get("/codon-hosts", response_model=list[CodonHostRead])
def list_codon_hosts(user: User = Depends(current_user)) -> list[CodonHostRead]:
    """Which hosts have a counted codon usage table, and how big the count was.

    Not project-scoped: the tables are reference data generated from public
    genomes by `scripts/build_codon_usage.py`, identical for every project.
    """
    return [CodonHostRead(**host) for host in hosts()]


@router.post(
    "/projects/{project_id}/codon-optimisations",
    response_model=CodonOptimiseResponse,
    openapi_extra={"x-permission": "sequence.optimise"},
)
def post_codon_optimisation(
    project_id: uuid.UUID,
    payload: CodonOptimiseRequest,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> CodonOptimiseResponse:
    """A construct for a candidate, target or registered protein.

    `current_user` rather than `require_command`: this creates nothing and
    records nothing. The permission declaration stays because the route is a
    POST and reaches project data, and every command route must name one.
    """
    require_project(session, project_id, user)
    result = optimise_codons(
        session,
        project_id,
        candidate_id=payload.candidate_id,
        target_id=payload.target_id,
        protein_id=payload.protein_id,
        host=payload.host,
        avoid_sites=payload.avoid_sites,
        prefix=payload.prefix,
        suffix=payload.suffix,
        add_stop=payload.add_stop,
        max_homopolymer=payload.max_homopolymer,
    )
    return CodonOptimiseResponse(**result)
