from pathlib import Path

from backend_v2.scripts.check_domain_boundaries import construction_problems, constructions, violations


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    for name, body in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return tmp_path


def test_current_tree_has_no_cross_domain_repository_imports() -> None:
    assert violations() == []


def test_flags_every_spelling_of_a_foreign_repository_import(tmp_path: Path) -> None:
    app = _tree(
        tmp_path,
        {
            "research/a.py": "from ..candidates.repository import CandidateRepository\n",
            "research/b.py": "from ..candidates import repository\n",
            "research/c.py": "from backend_v2.app.candidates.repository import CandidateRepository\n",
            "research/d.py": "import backend_v2.app.candidates.repository\n",
            "research/e.py": "def late():\n    from ..candidates.repository import CandidateRepository\n",
        },
    )

    found = violations(app)

    assert [line.split(":")[0] for line in found] == [f"research/{name}.py" for name in "abcde"]
    assert all("research imports candidates.repository" in line for line in found)


def test_allows_own_repository_and_foreign_services(tmp_path: Path) -> None:
    app = _tree(
        tmp_path,
        {
            "research/service.py": "from .repository import ResearchRepository\n",
            "research/__init__.py": "from .repository import ResearchRepository\n",
            "research/api.py": "from ..candidates.service import save_research_candidate\nfrom ..candidates import service\n",
            "main.py": "from .compute.repository import ComputeRepository\n",
        },
    )

    assert violations(app) == []


def test_current_tree_constructs_no_foreign_models() -> None:
    assert construction_problems() == []


def test_flags_a_new_foreign_model_construction_in_any_spelling(tmp_path: Path) -> None:
    app = _tree(
        tmp_path,
        {
            "research/a.py": "from ..artifacts.models import Artifact\nArtifact(id=1)\n",
            "research/b.py": "from ..artifacts import models\nmodels.ArtifactLineageEdge()\n",
            "research/c.py": "def late():\n    from backend_v2.app.artifacts.models import Artifact as A\n    return A()\n",
            "research/d.py": "from .models import ResearchBrief\nfrom ..core.models import update_versioned\nResearchBrief()\nupdate_versioned(1)\n",
        },
    )

    assert constructions(app) == [
        ("research/a.py", 2, "artifacts.Artifact"),
        ("research/b.py", 2, "artifacts.ArtifactLineageEdge"),
        ("research/c.py", 3, "artifacts.Artifact"),
    ]
