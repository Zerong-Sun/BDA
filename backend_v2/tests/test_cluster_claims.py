"""Exercise the gate even in public checkouts with no research generators."""


import pytest
from backend_v2.scripts import check_cluster_claims as gate


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPOSITORY_ROOT", tmp_path)
    return tmp_path / "generator.py"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ('#BSUB -n 8\n#BSUB -R "span[ptile=2]"', "ptile"),
        ('#BSUB -n 8\nrun --cpu 2', "threads"),
        ('#BSUB -n 8\nOMP_NUM_THREADS=2', "threads"),
        ('#BSUB -n 2\nrun_alphafold.py --jackhmmer_n_cpu=2', "concurrent"),
        ('#BSUB -n 8\nrun_alphafold.py --jackhmmer_n_cpu=$UNKNOWN', "concurrent"),
        ('#BSUB -n 1\n# No GPU requested\nrun', "never asserts"),
        ('#BSUB -n 1\nfor f in input/*.json; do run; done', "count"),
    ],
)
def test_rejects_unsafe_claims(source, body, message):
    assert any(message in error for error in gate.check_stage(source, "stage", body))


@pytest.mark.parametrize(
    "body",
    [
        '#BSUB -n 8\n#BSUB -R "span[ptile=8]"\nrun --cpu 8',
        '#BSUB -n 8\nN=2\nrun_alphafold.py --jackhmmer_n_cpu=$N',
        '#BSUB -n 2\nrun_alphafold.py --norun_data_pipeline --jackhmmer_n_cpu=2',
        '#BSUB -n 1\n# explanation of --cpu 8 is not a command',
        '#BSUB -n 1\n# No GPU\n[ -z "${CUDA_VISIBLE_DEVICES:-}" ] || exit 9',
        '#BSUB -n 1\nfor f in input/*.json; do run; done\ntest "$n" -eq 3 || exit 1',
        '#BSUB -n 1\nfor f in input/*.json; do run; done\n[ "$n" = 3 ] || exit 1',
        '#BSUB -n 8\nrun --cpu "$LSB_DJOB_NUMPROC"',
    ],
)
def test_accepts_supported_guards_and_resource_declarations(source, body):
    assert gate.check_stage(source, "stage", body) == []


def test_acknowledgement_only_waives_historical_af3_mismatch(source):
    body = '#BSUB -n 2\nrun_alphafold.py --jackhmmer_n_cpu=2'
    assert gate.check_stage(source, '"stage"', body, {"stage": "ran as 1234567"}) == []
    assert gate.check_stage(source, "stage", body, {"stage": "planned"})
    assert gate.check_stage(source, "stage", body + '\nrun --cpu 4', {"stage": "ran as 1234567"})


def test_literal_extraction_resolves_constants_without_importing_generator(source):
    source.write_text('N = 8\nraise RuntimeError("must not execute")\n'
                      'JOB = f\'\'\'#BSUB -J stage\n#BSUB -n {N}\nrun --cpu {N}\'\'\'\n')
    found = gate.literals_with_bsub(source)
    assert found == [("stage", "#BSUB -J stage\n#BSUB -n 8\nrun --cpu 8")]


def test_unknown_resources_are_reported_as_unverified(source, capsys):
    source.write_text('JOB = f\'\'\'#BSUB -J stage\n#BSUB -n {unknown}\n'
                      '#BSUB -R "span[ptile={unknown}]"\'\'\'\n')
    name, body = gate.literals_with_bsub(source)[0]
    gate.check_stage(source, name, body)
    assert "UNVERIFIED" in capsys.readouterr().out


def test_commented_gpu_guard_is_not_executable(source):
    body = '#BSUB -n 1\n# No GPU\n# CUDA_VISIBLE_DEVICES || exit 9\nrun'
    assert gate.check_stage(source, "stage", body)


def test_main_reports_empty_checkout_explicitly(source, monkeypatch, capsys):
    monkeypatch.setattr(gate, "SEARCH_ROOTS", (source.parent,))
    monkeypatch.setattr("sys.argv", ["check_cluster_claims.py"])
    assert gate.main() == 0
    assert "SKIP" in capsys.readouterr().out


def test_main_rejects_broken_generator(source, monkeypatch):
    source.write_text("def broken(:")
    monkeypatch.setattr(gate, "SEARCH_ROOTS", (source.parent,))
    monkeypatch.setattr("sys.argv", ["check_cluster_claims.py"])
    assert gate.main() == 1
