import hashlib
import uuid

import pytest
from backend_v2.app.compute.parsers import ParseContext, get_parser


@pytest.mark.parametrize("case", ["matched", "wrong_hash", "missing_score", "duplicate_structure", "duplicate_score"])
def test_interface_scores_require_unique_checksum_matched_coordinates(case):
    body = b"ATOM sample coordinates\n"
    checksum = hashlib.sha256(body).hexdigest()
    data = {
        "model": body,
        "scores": (
            "stage,scored_structure_sha256,dG_separated,total_score\n"
            f"primary,{checksum},-999,-999\n"
            f"interface,{checksum if case != 'wrong_hash' else '0' * 64},{'nan' if case == 'missing_score' else -12},-50\n"
        ).encode(),
    }
    if case == "duplicate_score":
        data["scores"] += f"interface,{checksum},-22,-51\n".encode()
    outputs = [
        {"filename": "runs/a/model.pdb", "object_key": "model"},
        {"filename": "scores.csv", "object_key": "scores"},
    ]
    if case == "duplicate_structure":
        outputs.append({"filename": "runs/b/model.pdb", "object_key": "model"})
    result = get_parser("rosetta_interface")(
        ParseContext(
            uuid.uuid4(), uuid.uuid4(), 1, outputs, {"interface": "A_B", "score_weights": "ref2015"}, data.__getitem__
        )
    )
    if case == "matched":
        assert result.candidates[0].scores["dG_separated"] == -12
        assert result.candidates[0].structure_output_index == 0
        assert result.candidates[0].metrics[0].condition == "A_B:ref2015"
    else:
        assert result.candidates == []
        assert result.warnings
