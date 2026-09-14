"""The triage tool: applying a route's own thresholds, and refusing to invent any.

The arithmetic and the database join are tested elsewhere. What this covers is
the tool's judgement about when it has no business answering:

* a route that declares no acceptance tiers - returning an empty verdict there
  would read as a clean pass, which is the worst possible answer;
* an unknown route id;
* a batch large enough that the result stops being something a person reads.

It also pins the tool to the capability that owns result interpretation, since
a read tool landing in the wrong capability is granted to the wrong operator.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.candidates.models import Candidate, CandidateMetric
from backend_v2.app.copilot import tools as _tools  # noqa: F401  (registers the catalogue)
from backend_v2.app.copilot.registry import REGISTRY, ToolContext
from backend_v2.app.core.models import Base
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_counter = itertools.count()
POOLED = "de-novo-binder-pooled"


@pytest.fixture
def session() -> Iterator[Session]:
    engine = enforce_foreign_keys(
        create_engine(
            "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    )
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as opened:
        yield opened
    drop_all(engine, Base.metadata)


def _project(session: Session) -> tuple[Project, User]:
    n = next(_counter)
    user = User(username=f"tt-{n}", display_name="T", role="researcher", enabled=True)
    organization = Organization(name=f"TT Org {n}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"tt-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    return project, user


def _candidate(session: Session, project: Project, metrics: dict[str, float]) -> Candidate:
    candidate = Candidate(
        project_id=project.id, candidate_key=f"k-{next(_counter)}", name="Design 1"
    )
    session.add(candidate)
    session.flush()
    for key, value in metrics.items():
        session.add(
            CandidateMetric(
                candidate_id=candidate.id, metric_key=key, value=value,
                method="alphafold3", assessor="independent_model", evidence_kind="predicted",
            )
        )
    session.flush()
    return candidate


def _run(session: Session, project: Project, **args: object) -> object:
    context = ToolContext(project_id=project.id, session=session)
    return REGISTRY.execute("triage_candidates", context, args, granted={"result-interpretation"})


def test_the_tool_belongs_to_the_capability_that_owns_interpretation() -> None:
    spec = next(item for item in REGISTRY.all() if item.id == "triage_candidates")

    assert spec.capability == "result-interpretation"
    assert spec.execution_mode == "read"


def test_a_route_declaring_no_tiers_is_refused_rather_than_passed(session: Session) -> None:
    """Structure acquisition constrains an ensemble, not a binder's quality."""
    project, _user = _project(session)
    candidate = _candidate(session, project, {"plddt": 90.0})

    with pytest.raises(Exception, match="no_acceptance_tiers"):
        _run(session, project, route_id="structure-acquisition", candidate_ids=[str(candidate.id)])


def test_an_unknown_route_is_refused(session: Session) -> None:
    project, _user = _project(session)
    candidate = _candidate(session, project, {"plddt": 90.0})

    with pytest.raises(Exception, match="route_not_found"):
        _run(session, project, route_id="no-such-route", candidate_ids=[str(candidate.id)])


def test_a_batch_too_large_to_read_is_refused(session: Session) -> None:
    """Refused by the declared schema, before the handler is entered.

    `maxItems` on the parameter is what stops it, which is the better place:
    the model is told its arguments were wrong rather than receiving a
    domain-shaped error for something that never reached the domain. The
    handler keeps its own cap for callers that invoke it directly, so the rule
    survives if the schema is ever loosened.
    """
    project, _user = _project(session)

    with pytest.raises(Exception, match="do not match the declared schema"):
        _run(session, project, route_id=POOLED, candidate_ids=[str(uuid.uuid4()) for _ in range(26)])


def test_the_route_thresholds_are_the_ones_applied(session: Session) -> None:
    project, _user = _project(session)
    candidate = _candidate(session, project, {"pae_interaction": 5.0, "plddt": 92.0})

    result = _run(session, project, route_id=POOLED, candidate_ids=[str(candidate.id)])

    assert isinstance(result, dict)
    assert result["route_id"] == POOLED
    assert result["tier_order"] == ["tier_b", "tier_a"]
    # The catalogue's own numbers, not a copy kept in the tool.
    assert result["tiers"]["tier_a"]["pae_interaction"] == "< 15"


def test_a_design_missing_a_measurement_is_reported_as_missing(session: Session) -> None:
    """Rosetta and RMSD are in the route's tiers and nothing has run them."""
    project, _user = _project(session)
    candidate = _candidate(session, project, {"pae_interaction": 5.0, "plddt": 92.0})

    result = _run(session, project, route_id=POOLED, candidate_ids=[str(candidate.id)])

    assert isinstance(result, dict)
    verdict = result["verdicts"][0]
    outcomes = {item["name"]: item["outcome"] for item in verdict["criteria"]}
    assert outcomes["pae_interaction"] == "pass"
    assert outcomes["rosetta_ddg_reu"] == "missing"
    assert verdict["tier"] is None
    assert verdict["failed"] == 0
    assert "not that the design failed" in result["reading_note"]
