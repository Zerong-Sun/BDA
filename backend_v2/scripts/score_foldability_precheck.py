"""Full readout: three families (r2b) plus neoculin, under the frozen criterion.

For a heterodimer the whole complex is superposed as ONE rigid body. That is the question
item 50 asks - whether the contract reproduces the 2D04 C/D heterodimer - and it is not
answered by folding each chain well. Per-chain RMSDs are reported alongside, because they
separate the two failure modes: chains folded wrong, versus chains folded right and docked
wrong. Only the complex number is compared to the bar.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from Bio.Align import PairwiseAligner
from Bio.PDB import PDBParser
from Bio.PDB.Polypeptide import protein_letters_3to1

PARSER = PDBParser(QUIET=True)
ALIGNER = PairwiseAligner(mode="global", open_gap_score=-11, extend_gap_score=-1)
ALIGNER.match_score, ALIGNER.mismatch_score = 2, -1


def ca_trace(path: Path, chain_id):
    model = next(iter(PARSER.get_structure("s", str(path))))
    out = []
    for chain in model:
        if chain_id is not None and chain.id != chain_id:
            continue
        for res in chain:
            if res.id[0] != " " or "CA" not in res:
                continue
            letter = protein_letters_3to1.get(res.get_resname().upper())
            if letter:
                out.append((letter, res["CA"].coord))
    return out


def pairs(ref, pred):
    aln = ALIGNER.align("".join(r[0] for r in ref), "".join(p[0] for p in pred))[0]
    got: list[tuple[int, int]] = []
    for (rs, re_), (ps, pe) in zip(*aln.aligned, strict=True):
        got.extend(zip(range(rs, re_), range(ps, pe), strict=True))
    return got


def kabsch(p, q):
    """RMSD after optimal superposition. Returns (rmsd, rotation, ref_mean, pred_mean)."""
    pm, qm = p.mean(axis=0), q.mean(axis=0)
    p0, q0 = p - pm, q - qm
    v, _, wt = np.linalg.svd(p0.T @ q0)
    d = np.sign(np.linalg.det(v @ wt))
    rot = v @ np.diag([1.0, 1.0, d]) @ wt
    diff = p0 @ rot - q0
    return float(np.sqrt((diff * diff).sum() / len(p))), rot, pm, qm


def verdict(worst):
    return "pass" if worst <= 2.0 else ("topology_only" if worst <= 5.0 else "fail")


def confidence(pred_path: Path):
    c = pred_path.parent / f"confidence_{pred_path.stem}.json"
    if not c.exists():
        return {}
    d = json.loads(c.read_text())
    return {k: round(d[k], 4) for k in ("complex_plddt", "ptm", "iptm") if k in d}


def run(cfg):
    """cfg: reference path + list of (ref_chain, pred_chain) segments in order."""
    segs = cfg["segments"]
    ref_seg = [ca_trace(Path(cfg["reference"]), rc) for rc, _ in segs]
    samples = []
    for i, pred_path in enumerate(sorted(Path(cfg["pred_dir"]).glob("*_model_*.pdb"))):
        a_all, b_all, per_chain = [], [], []
        for (rc, pc), ref in zip(segs, ref_seg, strict=True):
            pred = ca_trace(pred_path, pc)
            pr = pairs(ref, pred)
            a = np.array([ref[x][1] for x, _ in pr], float)
            b = np.array([pred[y][1] for _, y in pr], float)
            a_all.append(a)
            b_all.append(b)
            per_chain.append(
                {"ref_chain": rc, "pred_chain": pc, "matched_ca": len(pr),
                 "ca_rmsd_angstrom": round(kabsch(a, b)[0], 3)}
            )
        a, b = np.vstack(a_all), np.vstack(b_all)
        samples.append(
            {"sample": i, "ca_rmsd_angstrom": round(kabsch(a, b)[0], 3),
             "matched_ca": len(a), "per_chain": per_chain, **confidence(pred_path)}
        )
    worst = max(s["ca_rmsd_angstrom"] for s in samples)
    return {"reference": cfg["reference"],
            "reference_chains": [rc for rc, _ in segs],
            "models": len(samples), "per_sample": samples,
            "worst_ca_rmsd_angstrom": worst,
            "best_ca_rmsd_angstrom": min(s["ca_rmsd_angstrom"] for s in samples),
            "verdict": verdict(worst)}


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text())
    print(json.dumps({k: run(v) for k, v in spec.items()}, indent=1))
