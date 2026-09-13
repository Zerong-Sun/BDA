"""What a plugin declares, against what the queue will actually give it.

`steward` reviews resource declarations, and until this module existed its
charter named four numbers no tool could show it: the slot count, the per-host
span, the thread budget, and the GPU. That is the same defect the roster fixed
once in `archivist` - an operator instructed to do something the platform does
not expose - and it is the one these tests exist to keep fixed.

The rule that earns its place is the queue's own GPU request. `#BSUB` carrying
no `-gpu` does not mean no GPU; `2v100-32-e5` merges one into everything, and a
CPU-only stage submitted there holds a V100 exclusively while its script says it
asked for none.
"""

from __future__ import annotations

import pytest
from backend_v2.app.compute import declarations
from backend_v2.app.compute.diagnosis import GPU_FORCING_QUEUES


def _review(**overrides):
    payload = {
        "plugin_key": "probe",
        "plugin_version": "1",
        "resources": {},
        "backend": "lsf",
        "queue": "63",
    }
    payload.update(overrides)
    return declarations.review(**payload)


def _ids(result) -> set[str]:
    return {finding["id"] for finding in result["findings"]}


# --- The slot count ----------------------------------------------------------


def test_one_slot_needs_no_evidence() -> None:
    """The floor, not a claim."""
    result = _review(resources={"cpus": 1})

    assert _ids(result) == set()
    assert result["verdict"] == "sound"


def test_more_than_one_slot_without_evidence_is_a_violation() -> None:
    """A job holding cores it cannot use draws inspection mail, which this
    project treats as a violation rather than a notice."""
    result = _review(resources={"cpus": 8})

    assert "cpus_without_evidence" in _ids(result)
    assert result["verdict"] == "violation"


def test_evidence_settles_the_slot_count() -> None:
    result = _review(resources={"cpus": 4, "cpus_evidence": "AF3 runs 4 MSA searches at once"})

    assert "cpus_without_evidence" not in _ids(result)


def test_blank_evidence_does_not_count_as_evidence() -> None:
    result = _review(resources={"cpus": 4, "cpus_evidence": "   "})

    assert "cpus_without_evidence" in _ids(result)


def test_slots_and_per_host_span_come_from_one_number() -> None:
    """They must never disagree, so the reviewer states it rather than checks it."""
    result = _review(resources={"cpus": 4, "cpus_evidence": "measured"})

    assert result["effective"]["slots"] == result["effective"]["slots_per_host"] == 4
    assert "#BSUB -n 4" in result["directives"]
    assert '#BSUB -R "span[ptile=4]"' in result["directives"]


def test_a_missing_or_malformed_slot_count_reads_as_one() -> None:
    for resources in ({}, {"cpus": 0}, {"cpus": -3}, {"cpus": "eight"}):
        assert _review(resources=resources)["declared"]["cpus"] == 1


# --- The queue's own GPU request ---------------------------------------------


@pytest.mark.parametrize("queue", sorted(GPU_FORCING_QUEUES))
def test_a_gpu_forcing_queue_contradicts_a_cpu_only_declaration(queue: str) -> None:
    result = _review(resources={"cpus": 1}, queue=queue)

    assert "queue_forces_unrequested_gpu" in _ids(result)
    assert result["verdict"] == "violation"
    assert result["effective"]["gpu_attached"] is True
    assert result["effective"]["gpu_forced_by_queue"] is True


def test_a_cpu_queue_leaves_a_cpu_only_declaration_alone() -> None:
    result = _review(resources={"cpus": 1}, queue="63")

    assert _ids(result) == set()
    assert result["effective"]["gpu_attached"] is False


def test_declaring_the_gpu_on_a_forcing_queue_is_not_a_finding() -> None:
    """The declaration and the queue agree, which is the point."""
    result = _review(resources={"cpus": 1, "gpu": True}, queue="2v100-32-e5")

    assert _ids(result) == set()


def test_a_gpu_on_a_queue_not_known_to_provide_one_is_a_warning() -> None:
    """It surfaces as a job that runs slowly on CPU rather than as a failure,
    which is why it is worth saying and not worth blocking."""
    result = _review(resources={"cpus": 1, "gpu": True}, queue="63")

    assert _ids(result) == {"gpu_requested_on_unconfirmed_queue"}
    assert result["verdict"] == "review"


def test_a_second_gpu_needs_evidence_like_a_second_core() -> None:
    """Each device is held exclusively, so an unused one is idle for the run."""
    result = _review(resources={"gpu": True, "gpu_count": 2}, queue="2v100-32-e5")

    assert "multiple_gpus_without_evidence" in _ids(result)


def test_an_unnamed_queue_reports_no_queue_rather_than_assuming_a_safe_one() -> None:
    """Half the question, said as half the question.

    Assuming a CPU queue would let the finding that matters most here go
    unreported precisely when nobody has decided where the job goes.
    """
    result = _review(resources={"cpus": 1}, queue=None)

    assert result["queue"] is None
    assert result["effective"]["gpu_forced_by_queue"] is False
    assert "queue_forces_unrequested_gpu" not in _ids(result)


# --- Backends ----------------------------------------------------------------


def test_a_queue_named_for_a_backend_that_ignores_it_is_a_note() -> None:
    result = _review(backend="docker", queue="2v100-32-e5", resources={"cpus": 1})

    assert "queue_on_non_lsf_backend" in _ids(result)
    # A note, not a violation: nothing is over-requested, the name is just inert.
    assert result["verdict"] == "review"


def test_directives_are_only_rendered_for_the_backend_that_has_them() -> None:
    assert _review(backend="docker", queue=None, resources={"cpus": 1})["directives"] == []
    assert _review(resources={"cpus": 1})["directives"]


# --- Saying so when it is sound ----------------------------------------------


def test_a_sound_declaration_is_reported_as_sound() -> None:
    """A review that never approves stops being read, so "sound" is a stated
    verdict rather than an empty finding list the caller has to interpret."""
    result = _review(
        resources={"cpus": 4, "cpus_evidence": "jackhmmer saturates ~3.3 cores"},
        queue="63",
    )

    assert result["findings"] == []
    assert result["verdict"] == "sound"


def test_every_finding_carries_the_two_things_that_disagree() -> None:
    """`steward`'s charter requires reporting the pair, not the conclusion."""
    result = _review(resources={"cpus": 8}, queue="2v100-32-e5")

    assert result["findings"]
    for finding in result["findings"]:
        assert finding["title"] and finding["detail"]
        assert "declared" in finding and "effective" in finding
        assert finding["severity"] in {"violation", "warning", "note"}


def test_the_queue_rules_do_not_fire_on_a_backend_that_ignores_the_queue() -> None:
    """An accusation about a machine the job never reaches.

    The first version applied the GPU-forcing rule regardless of backend, so a
    Docker run naming an LSF queue was reported as holding a V100.
    """
    result = _review(backend="docker", queue="2v100-32-e5", resources={"cpus": 1})

    assert "queue_forces_unrequested_gpu" not in _ids(result)
    assert result["effective"]["gpu_attached"] is False


def test_a_declared_gpu_on_docker_raises_no_queue_warning() -> None:
    result = _review(backend="docker", queue="63", resources={"cpus": 1, "gpu": True})

    assert "gpu_requested_on_unconfirmed_queue" not in _ids(result)
    assert result["effective"]["gpu_attached"] is True
