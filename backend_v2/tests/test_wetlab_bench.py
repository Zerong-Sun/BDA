"""Wet-lab bench: sequence redaction, the protein library, and the calculators.

The redaction tests are the important ones. Everything else here is arithmetic
that would fail loudly; a sequence leaking into a response would not.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.app.wetlab.kernels import calculators
from backend_v2.app.wetlab.schemas import ProteinCreate, ProteinRead, ProteinUpdate
from backend_v2.app.wetlab.service import (
    FINGERPRINT_CHARS,
    create_protein,
    import_fasta,
    parse_fasta,
    sequence_digest,
    to_read,
    update_protein,
)
from backend_v2.tests._sqlite import drop_all
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# A real construct fragment: contains W, Y and C so it has an A280 signal.
SEQUENCE = "MKWVTFISLLLLFSSAYSRGVFRRDTHKSEIAHRFKDLGEENFKALVLIAFAQYLQQCPF"


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    # SQLite ignores foreign keys unless asked; without this the project and
    # candidate references here would not be constrained at all.
    @event.listens_for(engine, "connect")
    def _enforce_foreign_keys(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as opened:
        yield opened
    drop_all(engine, Base.metadata)


_project_counter = itertools.count()


def _project(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    suffix = next(_project_counter)
    user = User(
        username=f"bench-user-{suffix}", display_name="Bench User", role="editor", enabled=True
    )
    organization = Organization(name=f"Bench Org {suffix}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id,
        owner_id=user.id,
        name=f"bench-{suffix}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    return project.id, user.id


# --- Sequence redaction ------------------------------------------------------


def test_read_model_cannot_carry_a_sequence() -> None:
    """The redaction is structural, not a habit at each call site.

    If someone adds `sequence` to ProteinRead, every endpoint starts returning
    plaintext at once, so the field's absence is asserted rather than assumed.
    """
    assert "sequence" not in ProteinRead.model_fields


def test_projection_replaces_the_sequence_with_a_fingerprint(session: Session) -> None:
    project_id, user_id = _project(session)
    protein = create_protein(
        session, project_id, user_id, ProteinCreate(name="hsa-frag", sequence=SEQUENCE)
    )
    read = to_read(protein)
    dumped = read.model_dump_json()

    assert SEQUENCE not in dumped
    assert read.fingerprint == sequence_digest(SEQUENCE)[:FINGERPRINT_CHARS]
    assert len(read.fingerprint) == FINGERPRINT_CHARS
    # The stored row still has the sequence - redaction is at the boundary, not
    # at rest, because the derived numbers have to be recomputable.
    assert protein.sequence == SEQUENCE


def test_fingerprints_separate_two_constructs(session: Session) -> None:
    project_id, user_id = _project(session)
    first = create_protein(session, project_id, user_id, ProteinCreate(name="a", sequence=SEQUENCE))
    second = create_protein(
        session, project_id, user_id, ProteinCreate(name="b", sequence=SEQUENCE + "GG")
    )
    assert to_read(first).fingerprint != to_read(second).fingerprint


# --- Library rules -----------------------------------------------------------


def test_non_standard_residues_are_rejected_not_stripped() -> None:
    """Silently dropping unknown characters would compute a mass for a construct
    nobody has; the usual cause is a pasted nucleotide sequence."""
    with pytest.raises(ValueError, match="non-standard"):
        ProteinCreate(name="bad", sequence="MKVX1ZB")


def test_whitespace_and_stop_codons_are_normalised() -> None:
    payload = ProteinCreate(name="ok", sequence=" mkv\nlaa*\t")
    assert payload.sequence == "MKVLAA"


def test_same_sequence_twice_in_a_project_is_a_conflict(session: Session) -> None:
    project_id, user_id = _project(session)
    create_protein(session, project_id, user_id, ProteinCreate(name="first", sequence=SEQUENCE))
    with pytest.raises(DomainError) as raised:
        create_protein(
            session, project_id, user_id, ProteinCreate(name="second copy", sequence=SEQUENCE)
        )
    assert raised.value.status_code == 409
    assert raised.value.error_code == "protein_duplicate_sequence"


def test_derived_values_are_computed_and_stored(session: Session) -> None:
    project_id, user_id = _project(session)
    protein = create_protein(
        session, project_id, user_id, ProteinCreate(name="hsa-frag", sequence=SEQUENCE)
    )
    assert protein.length == len(SEQUENCE)
    assert protein.molecular_weight == pytest.approx(calculators.calc_mw(SEQUENCE), rel=1e-6)
    # W and Y present, so there is an A280 signal to quantify against.
    assert protein.ext_coeff_reduced > 0


def test_update_cannot_change_the_sequence(session: Session) -> None:
    """Mass and every recorded concentration were derived from it, so an edit in
    place would silently invalidate past results."""
    project_id, user_id = _project(session)
    protein = create_protein(session, project_id, user_id, ProteinCreate(name="n", sequence=SEQUENCE))
    assert "sequence" not in ProteinUpdate.model_fields

    update_protein(session, protein, ProteinUpdate(name="renamed", tags=["binder"]))
    assert protein.sequence == SEQUENCE
    assert protein.name == "renamed"
    assert protein.tags == ["binder"]


# --- FASTA import ------------------------------------------------------------


def test_fasta_parses_multiple_records_and_crlf() -> None:
    parsed = parse_fasta(">one desc\r\nMKV\r\nLAA\r\n\r\n>two\r\nWYC\r\n")
    assert parsed == [("one desc", "MKVLAA"), ("two", "WYC")]


def test_import_reports_each_record_instead_of_failing_the_batch(session: Session) -> None:
    """One duplicate or one bad paste must not discard the good records."""
    project_id, user_id = _project(session)
    create_protein(session, project_id, user_id, ProteinCreate(name="existing", sequence=SEQUENCE))

    result = import_fasta(
        session,
        project_id,
        user_id,
        f">fresh\nMKVLAAGIVGWY\n>dupe\n{SEQUENCE}\n>garbage\nXXXZZZ111\n",
        tags=["batch"],
    )

    assert (result.created, result.duplicates, result.rejected) == (1, 1, 1)
    assert [item.status for item in result.items] == ["created", "duplicate", "rejected"]
    assert result.items[2].detail  # says why it was rejected


# --- Calculator kernels ------------------------------------------------------


def test_concentration_follows_beer_lambert() -> None:
    # A = e*c*l, so c = A/(e*l); at A280=1.0 with e=10000 that is 100 uM.
    result = calculators.calc_conc(a280=1.0, ext_coeff=10_000, mw=12_000, path_length=1.0)
    assert result["molar_conc_uM"] == pytest.approx(100.0)
    # 100 uM * 12000 Da / 1000 = 1200 ng/uL = 1.2 mg/mL
    assert result["mass_conc_mg_mL"] == pytest.approx(1.2)


def test_concentration_refuses_a_sequence_with_no_signal() -> None:
    with pytest.raises(ValueError):
        calculators.calc_conc(a280=1.0, ext_coeff=0, mw=12_000)


def test_unit_conversion_crossing_molar_and_mass_needs_a_mass() -> None:
    assert calculators.convert_concentration(1000, "nM", "uM") == pytest.approx(1.0)
    assert calculators.convert_concentration(1, "mg/mL", "uM", 12_000) == pytest.approx(83.333, rel=1e-4)
    with pytest.raises(ValueError, match="mw"):
        calculators.convert_concentration(1, "mg/mL", "uM")


def test_dilution_series_steps_down_by_the_declared_factor() -> None:
    steps = calculators.calc_dilution_series(
        stock_conc_uM=100, start_conc_uM=50, dilution_factor=2, n_steps=4,
        vol_per_well_uL=200, extra_dead_vol_uL=20,
    )
    assert [step.conc_uM for step in steps] == [50.0, 25.0, 12.5, 6.25]
    # Every step must hold enough to fill a well and seed the next dilution.
    assert all(step.total_vol_uL >= 200 for step in steps)
    assert all(
        step.stock_vol_uL + step.buffer_vol_uL == pytest.approx(step.total_vol_uL) for step in steps
    )


def test_dilution_rejects_a_start_above_the_stock() -> None:
    with pytest.raises(ValueError):
        calculators.calc_dilution_series(
            stock_conc_uM=10, start_conc_uM=50, dilution_factor=2, n_steps=3, vol_per_well_uL=200
        )


# --- The dry/wet join --------------------------------------------------------


def _candidate(session: Session, project_id: uuid.UUID, **properties: object):
    from backend_v2.app.candidates.models import Candidate

    candidate = Candidate(
        project_id=project_id,
        candidate_key="design-001",
        name="Design 001",
        properties=dict(properties),
    )
    session.add(candidate)
    session.flush()
    return candidate


def test_a_designed_candidate_becomes_a_construct_on_the_bench(session: Session) -> None:
    """The join the platform existed either side of but never across."""
    from backend_v2.app.wetlab.service import promote_candidate

    project_id, user_id = _project(session)
    candidate = _candidate(session, project_id, sequence=SEQUENCE, length=len(SEQUENCE))

    protein = promote_candidate(session, project_id, user_id, candidate.id)

    assert protein.candidate_id == candidate.id
    assert protein.sequence == SEQUENCE
    assert protein.molecular_weight and protein.molecular_weight > 0
    assert "from-design" in protein.tags


def test_promoting_twice_returns_the_same_construct(session: Session) -> None:
    """A repeated click is not an error worth blocking the bench on."""
    from backend_v2.app.wetlab.service import promote_candidate

    project_id, user_id = _project(session)
    candidate = _candidate(session, project_id, sequence=SEQUENCE)

    first = promote_candidate(session, project_id, user_id, candidate.id)
    second = promote_candidate(session, project_id, user_id, candidate.id)
    assert first.id == second.id


def test_promotion_backfills_the_design_link_on_an_existing_construct(session: Session) -> None:
    """A construct entered by hand before its design was linked keeps its identity."""
    from backend_v2.app.wetlab.service import promote_candidate

    project_id, user_id = _project(session)
    manual = create_protein(
        session, project_id, user_id, ProteinCreate(name="entered by hand", sequence=SEQUENCE)
    )
    assert manual.candidate_id is None

    candidate = _candidate(session, project_id, sequence=SEQUENCE)
    promoted = promote_candidate(session, project_id, user_id, candidate.id)

    assert promoted.id == manual.id
    assert promoted.candidate_id == candidate.id


def test_a_candidate_without_a_sequence_cannot_be_made(session: Session) -> None:
    """A fold-only result has nothing to express; an empty construct would be worse."""
    from backend_v2.app.wetlab.service import promote_candidate

    project_id, user_id = _project(session)
    candidate = _candidate(session, project_id, plddt=91.2)

    with pytest.raises(DomainError) as raised:
        promote_candidate(session, project_id, user_id, candidate.id)
    assert raised.value.error_code == "candidate_has_no_sequence"
    assert raised.value.status_code == 422


def test_a_candidate_from_another_project_cannot_be_promoted(session: Session) -> None:
    from backend_v2.app.wetlab.service import promote_candidate

    project_id, user_id = _project(session)
    other_project, _ = _project(session)
    foreign = _candidate(session, other_project, sequence=SEQUENCE)

    with pytest.raises(DomainError) as raised:
        promote_candidate(session, project_id, user_id, foreign.id)
    assert raised.value.status_code == 404
