"""BDA Rosetta runner: validated argv, per-input/seed directories and raw evidence.

Only Python standard library is required on the compute node. This source and SPEC
are embedded in the immutable manifest. No Rosetta software is bundled.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import xml.etree.ElementTree as ET

if "SPEC" not in globals():
    SPEC = json.loads(Path(__file__).with_name("options.json").read_text())


class ConfigurationError(ValueError):
    pass


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def normalize(raw):
    if not isinstance(raw, dict):
        raise ConfigurationError("Configuration must be a JSON object")
    props = SPEC["schema"]["properties"]
    unknown = set(raw) - set(props)
    if unknown:
        raise ConfigurationError("Unknown parameters: " + ", ".join(sorted(unknown)))
    p = {k: v["default"] for k, v in props.items()}
    p.update(raw)
    for k, v in p.items():
        s = props[k]
        valid = {
            "string": isinstance(v, str),
            "boolean": isinstance(v, bool),
            "integer": isinstance(v, int) and not isinstance(v, bool),
            "number": isinstance(v, (int, float)) and not isinstance(v, bool),
        }[s["type"]]
        if not valid or (isinstance(v, float) and not math.isfinite(v)):
            raise ConfigurationError(k + ": wrong type or nonfinite value")
        if "enum" in s and v not in s["enum"]:
            raise ConfigurationError(k + ": unsupported value")
        if "minimum" in s and v < s["minimum"] or "maximum" in s and v > s["maximum"]:
            raise ConfigurationError(k + ": outside supported range")
        if "pattern" in s and not re.fullmatch(s["pattern"], v):
            raise ConfigurationError(k + ": invalid format")
        if isinstance(v, str) and ("\x00" in v or "\n" in v or "\r" in v):
            raise ConfigurationError(k + ": control characters are not allowed")
    mode = p["application"]
    for k in raw:
        modes = props[k].get("x-bda-modes", [])
        if modes and mode not in modes and raw[k] != props[k]["default"]:
            raise ConfigurationError(k + ": not applicable to " + mode)
    for modes, field in [
        (["InterfaceAnalyzer", "relax_interface"], "interface"),
        (["docking_protocol"], "dock_partners"),
        (["cartesian_ddg"], "ddg_mut_file"),
        (["rosetta_scripts"], "parser_protocol"),
    ]:
        if mode in modes and not p[field]:
            raise ConfigurationError(field + ": required for " + mode)
    if (
        mode == "cartesian_ddg"
        or mode in ["relax", "relax_interface"]
        and p["relax_cartesian"]
    ) and not p["score_weights"].endswith("_cart"):
        raise ConfigurationError(
            "Cartesian protocols require a supported *_cart score_weights"
        )
    if (
        mode == "docking_protocol"
        and p["dock_search"] == "global"
        and p["dock_local_refine"]
    ):
        raise ConfigurationError("global search and local-refine-only are incompatible")
    if (
        mode in ["relax", "relax_interface"]
        and p["ramp_constraints"]
        and not p["constrain_start"]
    ):
        raise ConfigurationError("ramp_constraints requires constrain_start")
    if mode in ["InterfaceAnalyzer", "relax_interface"]:
        if bool(p["receptor_axis"]) != bool(p["binder_axis"]):
            raise ConfigurationError(
                "Provide both receptor_axis and binder_axis, or neither"
            )
        if not p["geometry_contacts"] and any(
            p[k] for k in ["receptor_axis", "binder_axis", "geometry_reference_file"]
        ):
            raise ConfigurationError(
                "Geometry anchors/reference require geometry_contacts"
            )
    return {
        k: v
        for k, v in p.items()
        if not props[k].get("x-bda-modes") or mode in props[k]["x-bda-modes"]
    }


def from_environment():
    out = {}
    for k, s in SPEC["schema"]["properties"].items():
        if k not in os.environ:
            continue
        v = os.environ[k]
        if s["type"] == "boolean":
            if v not in ["1", "", "true", "false", "True", "False", "0"]:
                raise ConfigurationError(k + ": invalid boolean")
            out[k] = v in ["1", "true", "True"]
        elif s["type"] == "integer":
            out[k] = int(v)
        elif s["type"] == "number":
            out[k] = float(v)
        else:
            out[k] = v
    return out


def auxiliary(root, name):
    if not name:
        return None
    path = (root / "aux" / name).resolve()
    if (
        Path(name).is_absolute()
        or not path.is_relative_to((root / "aux").resolve())
        or not path.is_file()
    ):
        raise ConfigurationError("Auxiliary file must exist under input/aux: " + name)
    return path


def pdb_info(path):
    chains = set()
    residues = []
    seen = set()
    models = 0
    for line in path.read_text().splitlines():
        if line.startswith("MODEL "):
            models += 1
        if line.startswith(("ATOM  ", "HETATM")):
            if len(line) < 54:
                raise ConfigurationError("Truncated PDB atom record: " + str(path))
            chain = line[21]
            chains.add(chain)
            key = (chain, line[22:27], line[17:20])
            if key not in seen:
                seen.add(key)
                residues.append(
                    {
                        "chain": chain,
                        "pdb_number": line[22:27].strip(),
                        "resname": line[17:20],
                    }
                )
    if not chains or models > 1:
        raise ConfigurationError("Require a nonempty, single-model PDB: " + str(path))
    return {"chains": sorted(chains), "residues": residues}


def check_partners(partners, chains):
    left, right = partners.split("_")
    if len(set(left + right)) != len(left + right):
        raise ConfigurationError(
            "Partner groups must be disjoint with no repeated chain IDs"
        )
    if set(left + right) != set(chains):
        raise ConfigurationError(
            "Partner groups must cover exactly all input PDB chains; observed "
            + repr(chains)
        )


def check_mutations(path, info):
    rows = [x.split() for x in path.read_text().splitlines() if x.strip()]
    if not rows or len(rows[0]) != 2 or rows[0][0] != "total":
        raise ConfigurationError("mut_file must start with total N")
    amino = dict(
        zip(
            [
                "ALA",
                "CYS",
                "ASP",
                "GLU",
                "PHE",
                "GLY",
                "HIS",
                "ILE",
                "LYS",
                "LEU",
                "MET",
                "ASN",
                "PRO",
                "GLN",
                "ARG",
                "SER",
                "THR",
                "VAL",
                "TRP",
                "TYR",
            ],
            "ACDEFGHIKLMNPQRSTVWY",
        )
    )
    # Pose indexing is ambiguous with ligands/water/missing residues; do not guess.
    if any(r["resname"] not in amino for r in info["residues"]):
        raise ConfigurationError(
            "cartesian_ddg requires a canonical protein-only PDB with verified pose indexing"
        )
    count = 0
    groups = 0
    tags = []
    i = 1
    try:
        while i < len(rows):
            size = int(rows[i][0])
            if len(rows[i]) != 1 or size < 1:
                raise ValueError()
            i += 1
            group_positions = set()
            tag_parts = []
            for _ in range(size):
                wt, position, mutant = rows[i]
                n = int(position)
                if (
                    n < 1
                    or n > len(info["residues"])
                    or n in group_positions
                    or mutant not in amino.values()
                    or mutant == wt
                    or amino[info["residues"][n - 1]["resname"]] != wt
                ):
                    raise ValueError()
                group_positions.add(n)
                tag_parts.append(
                    str(n) + next(k for k, v in amino.items() if v == mutant)
                )
                i += 1
                count += 1
            groups += 1
            tags.append("MUT_" + "_".join(tag_parts))
        if count != int(rows[0][1]) or groups == 0:
            raise ValueError()
    except (ValueError, IndexError):
        raise ConfigurationError(
            "mut_file counts, WT identity or pose indices do not match input"
        ) from None
    return {
        "groups": groups,
        "mutations": count,
        "expected_mutant_tags": tags,
        "indexing": "canonical protein-only PDB residue order, 1-based",
    }


def variables(value):
    pairs = shlex.split(value)
    names = set()
    for pair in pairs:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.+", pair):
            raise ConfigurationError("XML variables require name=value tokens")
        name = pair.split("=", 1)[0]
        if name in names:
            raise ConfigurationError("Duplicate XML variable: " + name)
        names.add(name)
    return pairs, names


def argv_common(p, aux, seed):
    args = [
        "-score:weights",
        p["score_weights"],
        "-run:constant_seed",
        "true",
        "-run:jran",
        str(seed),
        "-ex1",
        str(p["ex1"]).lower(),
        "-ex2",
        str(p["ex2"]).lower(),
        "-use_input_sc",
        str(p["use_input_sc"]).lower(),
        "-ignore_unrecognized_res",
        str(p["ignore_unrecognized_res"]).lower(),
    ]
    for field, flag in [
        ("extra_res_fa", "-in:file:extra_res_fa"),
        ("extra_res_cen", "-in:file:extra_res_cen"),
    ]:
        if aux.get(field):
            args += [flag, str(aux[field])]
    if "fa_max_dis" in p:
        args += ["-fa_max_dis", str(p["fa_max_dis"])]
    return args


def command(root, binary, inp, out, args, scorefile, nstruct=None):
    argv = [
        str(root / "bin" / (binary + ".default.linuxgccrelease")),
        "-in:file:s",
        str(inp),
        "-out:path:all",
        str(out),
        "-out:file:scorefile",
        str(out / scorefile),
    ]
    if nstruct is not None:
        argv += ["-nstruct", str(nstruct)]
    return argv + args


def plan(raw, input_dir, output_dir, runtime_root):
    p = normalize(raw)
    mode = p["application"]
    inp, out, runtime = (
        Path(input_dir).resolve(),
        Path(output_dir).resolve(),
        Path(runtime_root).resolve(),
    )
    if out == inp or out.is_relative_to(inp) or inp.is_relative_to(out):
        raise ConfigurationError("Input and output directories must be separate")
    if out.exists() and any(out.iterdir()):
        raise ConfigurationError(
            "Use a fresh empty output directory; existing results are never overwritten"
        )
    inputs = sorted((inp / "s").rglob("*"))
    inputs = [
        x
        for x in inputs
        if x.is_file() and x.suffix.lower() in [".pdb", ".cif", ".mmcif"]
    ]
    if not inputs:
        raise ConfigurationError("No input structures on port s")
    if any(x.suffix.lower() != ".pdb" for x in inputs):
        raise ConfigurationError(
            "This audited release requires PDB input with explicit chain mapping; convert mmCIF before staging, preserving auth/label mapping"
        )
    if p["seed"] + len(inputs) * p["replicates"] > 2147483647:
        raise ConfigurationError("Seed range exceeds signed 32-bit integer")
    fields = [
        "extra_res_fa",
        "extra_res_cen",
        "constraints_file",
        "movemap_file",
        "relax_script",
        "native_file",
        "ddg_mut_file",
        "parser_protocol",
        "geometry_reference_file",
    ]
    aux = {k: auxiliary(inp, p.get(k, "")) for k in fields}
    xml_report = None
    if mode == "rosetta_scripts":
        value = aux["parser_protocol"].read_text()
        if (
            "<!DOCTYPE" in value
            or "<!ENTITY" in value
            or "xi:include" in value
            or "XInclude" in value
        ):
            raise ConfigurationError(
                "Use a self-contained XML without external entities/includes"
            )
        pairs, names = variables(p["parser_script_vars"])
        needed = set(re.findall(r"%%([A-Za-z_][A-Za-z0-9_]*)%%", value))
        if needed != names:
            raise ConfigurationError(
                "XML placeholders and supplied variables must match exactly"
            )
        try:
            # Placeholder XML remains well formed because placeholders are string values.
            tree = ET.fromstring(value)
        except ET.ParseError as e:
            raise ConfigurationError("Invalid XML: " + str(e)) from None
        if tree.tag != "ROSETTASCRIPTS":
            raise ConfigurationError("Expected ROSETTASCRIPTS root")
        xml_report = [
            {"tag": node.tag, "attributes": dict(node.attrib)} for node in tree.iter()
        ]
    entries = []
    for i, path in enumerate(inputs):
        if not path.resolve().is_relative_to((inp / "s").resolve()):
            raise ConfigurationError("Structure symlink escapes input port")
        info = pdb_info(path)
        if mode in ["InterfaceAnalyzer", "relax_interface", "docking_protocol"]:
            check_partners(p.get("interface", p.get("dock_partners")), info["chains"])
        if mode in ["InterfaceAnalyzer", "relax_interface"] and p["geometry_contacts"]:
            if p["receptor_axis"]:
                interface_geometry(path, p)
            if aux.get("geometry_reference_file"):
                ref_info = pdb_info(aux["geometry_reference_file"])
                check_partners(p["interface"], ref_info["chains"])
                interface_geometry(aux["geometry_reference_file"], p)
        mutation = (
            check_mutations(aux["ddg_mut_file"], info)
            if mode == "cartesian_ddg"
            else None
        )
        for rep in range(p["replicates"]):
            seed = p["seed"] + i * p["replicates"] + rep
            work = (
                out
                / "runs"
                / f"{i:04d}_{digest(path)[:10]}"
                / f"replicate_{rep + 1:03d}"
            )
            common = argv_common(p, aux, seed)
            extra = []
            if aux.get("constraints_file"):
                extra += [
                    "-constraints:cst_fa_file",
                    str(aux["constraints_file"]),
                    "-constraints:cst_fa_weight",
                    str(p["constraint_weight"]),
                ]
            binary = mode
            if mode in ["relax", "relax_interface"]:
                binary = "relax"
                extra += [
                    "-relax:default_repeats",
                    str(p["relax_repeats"]),
                    "-relax:cartesian",
                    str(p["relax_cartesian"]).lower(),
                    "-relax:constrain_relax_to_start_coords",
                    str(p["constrain_start"]).lower(),
                    "-relax:ramp_constraints",
                    str(p["ramp_constraints"]).lower(),
                ]
                for k, flag in [
                    ("movemap_file", "-in:file:movemap"),
                    ("relax_script", "-relax:script"),
                ]:
                    if aux[k]:
                        extra += [flag, str(aux[k])]
            elif mode == "InterfaceAnalyzer":
                extra += interface_args(p)
            elif mode == "docking_protocol":
                extra += [
                    "-in:file:fullatom",
                    "true",
                    "-docking:partners",
                    p["dock_partners"],
                ]
                if p["dock_search"] == "global":
                    extra += [
                        "-docking:randomize1",
                        "true",
                        "-docking:randomize2",
                        "true",
                    ]
                else:
                    extra += [
                        "-docking:dock_pert",
                        str(p["dock_translation"]),
                        str(p["dock_rotation"]),
                    ]
                extra += [
                    "-docking:docking_local_refine",
                    str(p["dock_local_refine"]).lower(),
                ]
                if aux["native_file"]:
                    extra += ["-in:file:native", str(aux["native_file"])]
            elif mode == "cartesian_ddg":
                extra += [
                    "-ddg:mut_file",
                    str(aux["ddg_mut_file"]),
                    "-ddg:iterations",
                    str(p["ddg_iterations"]),
                    "-ddg:cartesian",
                    "true",
                    "-ddg:legacy",
                    "false",
                    "-ddg:bbnbrs",
                    str(p["ddg_bb_neighbors"]),
                    "-ddg:dump_pdbs",
                    str(p["ddg_dump_pdbs"]).lower(),
                ]
            elif mode == "rosetta_scripts":
                extra += ["-parser:protocol", str(aux["parser_protocol"])]
                if pairs:
                    extra += ["-parser:script_vars", *pairs]
            stage = work / ("relax" if mode == "relax_interface" else "primary")
            argv = command(
                runtime,
                binary,
                path,
                stage,
                common + extra,
                p["out_scorefile"],
                p.get("nstruct"),
            )
            entries.append(
                {
                    "input": str(path),
                    "input_sha256": digest(path),
                    "chains": info["chains"],
                    "replicate": rep + 1,
                    "seed": seed,
                    "work_dir": str(work),
                    "stage_dir": str(stage),
                    "argv": argv,
                    "mutations": mutation,
                }
            )
    return {
        "schema_version": 1,
        "plugin_version": SPEC["plugin_version"],
        "status": "generated_not_executed",
        "parameters": p,
        "mode_description": SPEC["modes"][mode],
        "runtime_root": str(runtime),
        "output_dir": str(out),
        "auxiliary_files": {
            k: {"path": str(v), "sha256": digest(v)} for k, v in aux.items() if v
        },
        "xml_attribute_inventory": xml_report,
        "entries": entries,
        "deferred_stage": "InterfaceAnalyzer on every saved relaxed PDB, each with nstruct=1; actual argv recorded before execution"
        if mode == "relax_interface"
        else None,
        "units": {
            "Rosetta_energy": "REU; not physical kcal/mol or measured Kd",
            "dSASA_int": "angstrom^2",
        },
        "scientific_validation": "not_established; software output completeness is not binding/activation validation",
    }


def interface_args(p):
    a = [
        "-interface",
        p["interface"],
        "-pack_input",
        str(p["pack_input"]).lower(),
        "-pack_separated",
        str(p["pack_separated"]).lower(),
        "-compute_packstat",
        str(p["compute_packstat"]).lower(),
        "-tracer_data_print",
        "false",
        "-add_regular_scores_to_scorefile",
        "true",
    ]
    if p["compute_packstat"]:
        a += ["-packstat:oversample", str(p["packstat_oversample"])]
    return a


def score_rows(path):
    header = None
    rows = []
    for line in path.read_text().splitlines():
        tokens = line.split()
        if not tokens or tokens[0] != "SCORE:":
            continue
        tokens = tokens[1:]
        if "description" in tokens and not rows:
            header = tokens
            continue
        if header and tokens == header:
            continue
        if header and len(tokens) == len(header):
            row = dict(zip(header, tokens))
            try:
                converted = {}
                numeric_required = {
                    "score",
                    "total_score",
                    "dG_separated",
                    "dSASA_int",
                    "packstat",
                }
                for k, v in row.items():
                    if k == "description":
                        converted[k] = v
                        continue
                    try:
                        number = float(v)
                    except ValueError:
                        if k in numeric_required:
                            raise
                        converted[k] = v  # XML string extra-scores remain raw text.
                    else:
                        if not math.isfinite(number):
                            raise ValueError()
                        converted[k] = number
            except ValueError:
                raise ConfigurationError(
                    "Invalid/nonfinite SCORE row: " + str(path)
                ) from None
            rows.append(converted)
    return rows


def interface_geometry(path, p):
    """Heavy-atom contacts in the exact scored input; oriented angles need explicit CA anchors."""
    left, right = p["interface"].split("_")
    groups = [[], []]
    ca = {}
    for line in path.read_text().splitlines():
        if not line.startswith(("ATOM  ", "HETATM")) or line[16] not in (" ", "A"):
            continue
        atom = line[12:16].strip()
        element = line[76:78].strip() if len(line) >= 78 else ""
        if (element or atom.lstrip("0123456789")[:1]).upper() in ("H", "D"):
            continue
        chain, residue = line[21], line[22:27].strip()
        xyz = tuple(float(line[a:b]) for a, b in [(30, 38), (38, 46), (46, 54)])
        if not all(math.isfinite(x) for x in xyz):
            raise ConfigurationError("Nonfinite PDB coordinate")
        record = {
            "chain": chain,
            "residue": residue,
            "resname": line[17:20].strip(),
            "atom": atom,
            "xyz": xyz,
        }
        if chain in left:
            groups[0].append(record)
        elif chain in right:
            groups[1].append(record)
        if atom == "CA":
            ca[chain + ":" + residue] = xyz
    if not all(groups):
        raise ConfigurationError("Empty heavy-atom partner group")
    cutoff = p["contact_cutoff"]
    grid = {}
    for atom in groups[1]:
        key = tuple(math.floor(x / cutoff) for x in atom["xyz"])
        grid.setdefault(key, []).append(atom)
    contacts = []
    residue_min = {}
    for a in groups[0]:
        key = tuple(math.floor(x / cutoff) for x in a["xyz"])
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for b in grid.get((key[0] + dx, key[1] + dy, key[2] + dz), []):
                        distance = math.dist(a["xyz"], b["xyz"])
                        if distance <= cutoff:
                            contact = {
                                **{
                                    "receptor_" + k: a[k]
                                    for k in ["chain", "residue", "resname", "atom"]
                                },
                                **{
                                    "binder_" + k: b[k]
                                    for k in ["chain", "residue", "resname", "atom"]
                                },
                                "distance_angstrom": distance,
                            }
                            contacts.append(contact)
                            rkey = (a["chain"], a["residue"], b["chain"], b["residue"])
                            if (
                                rkey not in residue_min
                                or distance < residue_min[rkey]["distance_angstrom"]
                            ):
                                residue_min[rkey] = contact
    centroids = [
        tuple(sum(a["xyz"][i] for a in group) / len(group) for i in range(3))
        for group in groups
    ]
    angle = None
    if p["receptor_axis"] and p["binder_axis"]:
        axes = []
        for field, permitted in [("receptor_axis", left), ("binder_axis", right)]:
            ids = p[field].split(",")
            if len(ids) != 2 or any(
                x not in ca or x.split(":")[0] not in permitted for x in ids
            ):
                raise ConfigurationError(
                    field + ": both CA anchors must exist in the corresponding partner"
                )
            vec = tuple(b - a for a, b in zip(ca[ids[0]], ca[ids[1]]))
            norm = math.sqrt(sum(x * x for x in vec))
            if norm < 1e-8:
                raise ConfigurationError("Angle axis has zero length")
            axes.append(tuple(x / norm for x in vec))
        angle = math.degrees(
            math.acos(max(-1, min(1, sum(a * b for a, b in zip(*axes)))))
        )
    return {
        "coordinate_file": str(path),
        "coordinate_sha256": digest(path),
        "interface": p["interface"],
        "contact_cutoff_angstrom": cutoff,
        "heavy_atom_counts": [len(g) for g in groups],
        "centroid_distance_angstrom": math.dist(*centroids),
        "contact_atom_pair_count": len(contacts),
        "minimum_distance_within_cutoff_angstrom": min(
            (r["distance_angstrom"] for r in contacts), default=None
        ),
        "receptor_axis": p["receptor_axis"],
        "binder_axis": p["binder_axis"],
        "anchored_angle_degrees": angle,
        "angle_status": "computed_from_explicit_CA_axes"
        if angle is not None
        else "not_computed; CA anchors not supplied",
        "geometry_scope": "saved input coordinates; excludes unexported IA internal packing copies",
        "atom_contacts": contacts,
        "residue_pair_minima": list(residue_min.values()),
    }


def write_geometry(path, target, p, job):
    report = interface_geometry(path, p)
    ref = job["auxiliary_files"].get("geometry_reference_file")
    if ref:
        reference = interface_geometry(Path(ref["path"]), p)
        report["reference"] = reference
        report["reference_evidence_status"] = (
            "user-supplied; not assumed to be an experimentally solved complex"
        )
        report["centroid_distance_delta_angstrom"] = (
            report["centroid_distance_angstrom"]
            - reference["centroid_distance_angstrom"]
        )
        report["anchored_angle_delta_degrees"] = (
            (report["anchored_angle_degrees"] - reference["anchored_angle_degrees"])
            if report["anchored_angle_degrees"] is not None
            else None
        )
    save_json(target / "interface-geometry.json", report)
    if report["atom_contacts"]:
        with (target / "atom-contacts.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(report["atom_contacts"][0]))
            writer.writeheader()
            writer.writerows(report["atom_contacts"])


def save_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )


def run_process(argv, directory, evidence):
    directory.mkdir(parents=True, exist_ok=False)
    binary = Path(argv[0])
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ConfigurationError("Rosetta executable not available: " + str(binary))
    evidence["executables"][str(binary)] = digest(binary)
    with (directory / "rosetta.log").open("w") as log:
        result = subprocess.run(
            argv, cwd=directory, stdout=log, stderr=subprocess.STDOUT, check=False
        )
    if result.returncode:
        raise ConfigurationError(
            f"Rosetta exit {result.returncode}: {directory}/rosetta.log"
        )


def execute(job):
    out = Path(job["output_dir"])
    p = job["parameters"]
    mode = p["application"]
    evidence = {
        "status": "running",
        "jobs": [],
        "executables": {},
        "energy_unit": "REU",
        "runtime_root": job["runtime_root"],
        "metric_status": {
            "packstat": "requested"
            if p.get("compute_packstat")
            else "not_requested; any raw zero is not an evaluated packing score"
        },
    }
    rows = []
    save_json(out / "execution.json", evidence)
    try:
        for entry in job["entries"]:
            stage = Path(entry["stage_dir"])
            item = {**entry, "status": "running"}
            evidence["jobs"].append(item)
            save_json(out / "execution.json", evidence)
            run_process(entry["argv"], stage, evidence)
            if mode == "cartesian_ddg":
                ddgs = list(stage.glob("*.ddg"))
                if not ddgs or any(not f.read_text().strip() for f in ddgs):
                    raise ConfigurationError(
                        "cartesian_ddg produced no nonempty .ddg output"
                    )
                records = []
                for f in ddgs:
                    for line in f.read_text().splitlines():
                        match = re.match(
                            r"^COMPLEX:\s+Round(\d+):\s+(WT_?|MUT_[A-Za-z0-9_]+):\s+(\S+)",
                            line,
                        )
                        if match:
                            energy = float(match[3])
                            if not math.isfinite(energy):
                                raise ConfigurationError(
                                    "Nonfinite Cartesian DDG energy"
                                )
                            records.append(
                                {
                                    "round": int(match[1]),
                                    "tag": match[2],
                                    "score": energy,
                                    "source": str(f),
                                }
                            )
                tags = {r["tag"] for r in records}
                if not tags.intersection({"WT", "WT_"}) or not set(
                    entry["mutations"]["expected_mutant_tags"]
                ).issubset(tags):
                    raise ConfigurationError(
                        "Incomplete modern Cartesian DDG WT/mutant records"
                    )
                save_json(
                    stage / "ddg-records.json",
                    {
                        "records": records,
                        "unit": "REU",
                        "requested_iterations": p["ddg_iterations"],
                        "note": "WT and each mutant present. Early termination/iteration counts require protocol review.",
                    },
                )
                item["ddg_files"] = [str(f) for f in ddgs]
                item["scientific_completeness"] = (
                    "WT_and_each_mutant_present; not a validated physical stability measurement"
                )
            else:
                scored = (
                    score_rows(stage / p["out_scorefile"])
                    if (stage / p["out_scorefile"]).is_file()
                    else []
                )
                if len(scored) < p["nstruct"]:
                    raise ConfigurationError("Fewer SCORE rows than requested nstruct")
                pdbs = sorted(stage.glob("*.pdb"))
                need_struct = (
                    mode in ["relax", "relax_interface", "docking_protocol"]
                    or mode == "rosetta_scripts"
                    and p["xml_expected_output"] == "structure"
                )
                if need_struct and len(pdbs) < p["nstruct"]:
                    raise ConfigurationError("Fewer output PDBs than requested nstruct")
                for row in scored:
                    rows.append(
                        {
                            "input_sha256": entry["input_sha256"],
                            "replicate": entry["replicate"],
                            "seed": entry["seed"],
                            "stage": "primary",
                            "source_scorefile": str(stage / p["out_scorefile"]),
                            **row,
                        }
                    )
                if mode == "relax_interface":
                    item["interface_commands"] = []
                    for j, pdb in enumerate(pdbs):
                        target = Path(entry["work_dir"]) / "interface" / f"{j:05d}"
                        aux = {
                            k: Path(v["path"])
                            for k, v in job["auxiliary_files"].items()
                            if k == "extra_res_fa"
                        }
                        argv = command(
                            Path(job["runtime_root"]),
                            "InterfaceAnalyzer",
                            pdb,
                            target,
                            argv_common(p, aux, entry["seed"]) + interface_args(p),
                            p["out_scorefile"],
                            1,
                        )
                        item["interface_commands"].append(
                            {"argv": argv, "input_sha256": digest(pdb)}
                        )
                        save_json(out / "execution.json", evidence)
                        run_process(argv, target, evidence)
                        ir = (
                            score_rows(target / p["out_scorefile"])
                            if (target / p["out_scorefile"]).is_file()
                            else []
                        )
                        if not ir or any("dG_separated" not in r for r in ir):
                            raise ConfigurationError(
                                "Missing dG_separated interface rows"
                            )
                        if p["geometry_contacts"]:
                            write_geometry(pdb, target, p, job)
                        for row in ir:
                            rows.append(
                                {
                                    "input_sha256": entry["input_sha256"],
                                    "replicate": entry["replicate"],
                                    "seed": entry["seed"],
                                    "stage": "interface",
                                    "source_scorefile": str(
                                        target / p["out_scorefile"]
                                    ),
                                    "scored_structure": str(pdb),
                                    "scored_structure_sha256": digest(pdb),
                                    **row,
                                }
                            )
                elif mode == "InterfaceAnalyzer" and any(
                    "dG_separated" not in r for r in scored
                ):
                    raise ConfigurationError("Missing dG_separated interface metric")
            if mode == "InterfaceAnalyzer" and p["geometry_contacts"]:
                write_geometry(Path(entry["input"]), stage, p, job)
            item["status"] = "outputs_checked"
            save_json(out / "execution.json", evidence)
        if rows:
            columns = sorted(set().union(*(r.keys() for r in rows)))
            with (out / "scores.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
        save_json(
            out / "scores.json",
            {
                "rows": rows,
                "note": "All numeric score columns preserved; no inferred Kd or physical binding ΔG.",
            },
        )
        evidence["status"] = "execution_complete_raw_outputs_checked"
    except Exception as exc:
        evidence["status"] = "failed"
        evidence["error"] = str(exc)
        save_json(out / "execution.json", evidence)
        raise
    save_json(out / "execution.json", evidence)
    artifacts = [
        {"path": str(f.relative_to(out)), "size": f.stat().st_size, "sha256": digest(f)}
        for f in sorted(out.rglob("*"))
        if f.is_file() and f.name != "checksums.json"
    ]
    save_json(out / "checksums.json", artifacts)
    return evidence


def materialize(job):
    out = Path(job["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    save_json(out / "run-plan.json", job)
    props = SPEC["schema"]["properties"]
    lines = [
        "# 本次 Rosetta 参数说明",
        "",
        "状态：仅配置生成；是否执行以 execution.json 为准。",
        "",
        job["mode_description"],
        "",
    ]
    for k, v in job["parameters"].items():
        s = props[k]
        lines += [
            f"## {k} — {s['title']}",
            f"值：`{json.dumps(v, ensure_ascii=False)}`；单位：{s['x-bda-unit']}；映射：`{s['x-bda-flag']}`",
            "",
            s["description"],
            "",
            f"依据：{s['x-bda-source']}",
            "",
        ]
    if job["xml_attribute_inventory"] is not None:
        lines += [
            "## 自定义 XML 属性清单",
            "属性的科学语义由所上传协议和对应 Rosetta XSD 定义；此清单不表示已验证全部 XML 功能。",
            "",
            "```json",
            json.dumps(job["xml_attribute_inventory"], ensure_ascii=False, indent=2),
            "```",
        ]
    (out / "parameter-explanations.md").write_text("\n".join(lines) + "\n")
    (out / "commands.sh").write_text(
        "#!/usr/bin/env bash\n# Review only: working directories and output checks are managed by runner.py.\n"
        + "\n".join(shlex.join(e["argv"]) for e in job["entries"])
        + "\n"
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["describe", "generate", "run"])
    ap.add_argument("--config", type=Path)
    ap.add_argument("--input-dir", default=os.environ.get("BDA_INPUT_DIR"))
    ap.add_argument("--output-dir", default=os.environ.get("BDA_OUTPUT_DIR"))
    ap.add_argument("--runtime-root", default=os.environ.get("BDA_PLUGIN_ROOT"))
    args = ap.parse_args(argv)
    if args.action == "describe":
        print(json.dumps(SPEC, ensure_ascii=False, indent=2))
        return 0
    if not all([args.input_dir, args.output_dir, args.runtime_root]):
        ap.error("input-dir, output-dir and runtime-root are required")
    try:
        raw = json.loads(args.config.read_text()) if args.config else from_environment()
        job = plan(raw, args.input_dir, args.output_dir, args.runtime_root)
        materialize(job)
        if args.action == "run":
            execute(job)
        print(
            json.dumps(
                {
                    "status": "executed_raw_outputs_checked"
                    if args.action == "run"
                    else "generated_not_executed",
                    "output_dir": job["output_dir"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    except (ValueError, OSError) as e:
        print("Rosetta plugin: " + str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
