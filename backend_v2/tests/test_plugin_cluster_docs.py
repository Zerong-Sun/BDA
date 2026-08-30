from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROFILE_PATH = REPO / "qm-scripts/plugins/registry.json"
CATALOG_PATH = REPO / "qm-scripts/library/catalog.json"
EXPECTED_PLUGIN_KEYS = {
    "AlphaFold 3",
    "AlphaFold2",
    "APBS+PDB2PQR",
    "BindCraft",
    "Boltz",
    "Chai-1",
    "DiffAb",
    "Foldseek",
    "Mask RGN",
    "proteinhunter_boltz",
    "ProteinMPNN",
    "RFdiffusion",
    "RFdiffusion3",
    "Rosetta",
    "superfold",
    "US-align",
}


def _generator():
    path = REPO / "qm-scripts/plugins/generate_docs.py"
    spec = importlib.util.spec_from_file_location("generate_plugin_cluster_docs", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_plugin_has_a_versioned_cluster_profile_and_generated_runbook() -> None:
    payload = json.loads(PROFILE_PATH.read_text())
    profiles = payload["plugins"]

    assert {profile["plugin_key"] for profile in profiles} == EXPECTED_PLUGIN_KEYS
    assert len({profile["slug"] for profile in profiles}) == len(profiles)
    for profile in profiles:
        assert profile["versions"]
        assert isinstance(profile["submission_authorized"], bool)
        if profile["state"] in {"disabled", "mixed"}:
            assert profile["submission_authorized"] is False
        assert profile["runtime"]
        assert "slot" in profile["resources"] or "submission" in profile["resources"]
        assert len(profile["rules"]) >= 3
        runbook = REPO / "qm-scripts/plugins" / profile["slug"] / "README.md"
        assert runbook.exists(), profile["plugin_key"]
        text = runbook.read_text()
        assert profile["plugin_key"] in text
        assert "How to write and review the job" in text
        assert "Recorded cluster observations" in text
        assert "Direct submission authorized" in text


def test_every_dated_observation_has_existing_evidence_and_never_implies_current_proof() -> None:
    profiles = json.loads(PROFILE_PATH.read_text())["plugins"]
    allowed_scopes = {"historical_observation", "installation_observation", "failed_observation"}

    for profile in profiles:
        for observation in profile["observations"]:
            date.fromisoformat(observation["observed_on"])
            if observation.get("completed_on"):
                date.fromisoformat(observation["completed_on"])
            assert observation["result"]
            assert observation["summary"]
            assert observation["proof_scope"] in allowed_scopes
            assert observation["sources"]
            for source in observation["sources"]:
                assert (REPO / source).exists(), (profile["plugin_key"], source)


def test_qm_job_profiles_reference_catalogued_models_and_real_examples() -> None:
    profiles = json.loads(PROFILE_PATH.read_text())["plugins"]
    models = json.loads(CATALOG_PATH.read_text())["models"]

    for profile in profiles:
        if profile["renderer"] != "qm_job":
            assert profile["qm_job_model"] is None
            assert profile["example"] is None
            continue
        assert profile["qm_job_model"] in models
        if profile["example"]:
            assert (REPO / profile["example"]).exists()


def test_generated_plugin_docs_are_current() -> None:
    generator = _generator()
    expected = generator.expected_files(generator.load_registry())

    assert expected
    assert all(path.exists() and path.read_text() == content for path, content in expected.items())
