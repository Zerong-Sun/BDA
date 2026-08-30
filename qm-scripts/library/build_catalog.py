#!/usr/bin/env python3
"""Build the QM model parameter catalog from pinned upstream source checkouts."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from pathlib import Path
from typing import Any

import yaml


UPSTREAMS = {
    "rfdiffusion": {
        "repo": "https://github.com/RosettaCommons/RFdiffusion",
        "commit": "2d0c003df46b9db41d119321f15403dec3716cd9",
        "entrypoint": "scripts/run_inference.py",
        "style": "hydra",
    },
    "proteinmpnn": {
        "repo": "https://github.com/dauparas/ProteinMPNN",
        "commit": "8907e6671bfbfc92303b5f79c4b5e6ce47cdef57",
        "entrypoint": "protein_mpnn_run.py",
        "style": "argparse",
    },
    "alphafold2": {
        "repo": "https://github.com/google-deepmind/alphafold",
        "commit": "c77e5d2a8961d1a353632c462914ff0a32a950f6",
        "entrypoint": "run_alphafold.py",
        "style": "absl",
    },
    "alphafold3": {
        "repo": "https://github.com/google-deepmind/alphafold3",
        "commit": "b2f3d45fbfcacc5183bd5345d15df93571b8437f",
        "entrypoint": "run_alphafold.py",
        "style": "absl",
    },
    "boltz": {
        "repo": "https://github.com/jwohlwend/boltz",
        "commit": "b1ebfc46ecf57f5414e0d1a6f9027bbb122c53bc",
        "entrypoint": "src/boltz/main.py",
        "style": "click",
    },
    "chai1": {
        "repo": "https://github.com/chaidiscovery/chai-lab",
        "commit": "c544fb183e865c4950909444db860a9d50604f66",
        "entrypoint": "chai_lab/chai1.py",
        "style": "python_call",
    },
    "bindcraft": {
        "repo": "https://github.com/martinpacesa/BindCraft",
        "commit": "b971db42ba6e091afab63ccb30ae02215150a990",
        "entrypoint": "bindcraft.py",
        "style": "json_bundle",
    },
    "rosetta": {
        "repo": "https://github.com/RosettaCommons/rosetta",
        "commit": "bbb6a2d27c70be05b2fb2409f3920b5894967d60",
        "entrypoint": "rosetta_scripts/relax/InterfaceAnalyzer/cartesian_ddg",
        "style": "rosetta_flags",
    },
    "maskrgn": {
        "repo": "local://models/maskrgnn_clean",
        "commit": "workspace",
        "entrypoint": "models/maskrgnn_clean/inference.py",
        "style": "hydra",
    },
}


def literal(node: ast.AST | None) -> Any:
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None


def parameter(
    key: str,
    default: Any,
    *,
    kind: str = "string",
    help_text: str = "",
    required: bool = False,
    boolean_style: str | None = None,
    group: str = "parameters",
) -> dict[str, Any]:
    item = {
        "key": key,
        "default": default,
        "type": kind,
        "help": help_text,
        "required": required,
        "group": group,
    }
    if boolean_style:
        item["boolean_style"] = boolean_style
    return item


def flatten_yaml(value: Any, prefix: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "defaults":
                continue
            full = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(flatten_yaml(child, full))
        return rows
    kind = "any" if value is None else "boolean" if isinstance(value, bool) else "integer" if isinstance(value, int) else "number" if isinstance(value, float) else "json" if isinstance(value, list) else "string"
    rows.append(parameter(prefix, value, kind=kind))
    return rows


def argparse_parameters(path: Path) -> list[dict[str, Any]]:
    tree = ast.parse(path.read_text())
    rows = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "add_argument" or not node.args:
            continue
        options = [literal(arg) for arg in node.args]
        options = [x for x in options if isinstance(x, str) and x.startswith("-")]
        if not options:
            continue
        key = max(options, key=len).lstrip("-").replace("-", "_")
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        action = literal(kwargs.get("action"))
        default = literal(kwargs.get("default"))
        if action == "store_true":
            default = False if default is None else default
        type_name = literal(kwargs.get("type"))
        kind = {"int": "integer", "float": "number"}.get(type_name, "boolean" if action == "store_true" else "string")
        rows.append(parameter(
            key,
            default,
            kind=kind,
            help_text=literal(kwargs.get("help")) or "",
            required=bool(literal(kwargs.get("required"))),
            boolean_style="flag" if action == "store_true" else None,
        ))
    return sorted({row["key"]: row for row in rows}.values(), key=lambda row: row["key"])


def absl_parameters(path: Path) -> list[dict[str, Any]]:
    tree = ast.parse(path.read_text())
    rows = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if not node.func.attr.startswith("DEFINE_") or not node.args:
            continue
        key = literal(node.args[0])
        if not isinstance(key, str):
            continue
        default = literal(node.args[1]) if len(node.args) > 1 else None
        help_text = ""
        for candidate in reversed(node.args[2:]):
            value = literal(candidate)
            if isinstance(value, str):
                help_text = value
                break
        suffix = node.func.attr.removeprefix("DEFINE_")
        kind = {
            "bool": "boolean", "boolean": "boolean", "integer": "integer",
            "float": "number", "list": "list", "multi_string": "list",
        }.get(suffix, "string")
        rows.append(parameter(key, default, kind=kind, help_text=help_text or "", boolean_style="value" if kind == "boolean" else None))
    by_key = {row["key"]: row for row in rows}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "mark_flags_as_required" or not node.args:
            continue
        for key in literal(node.args[0]) or []:
            if key in by_key:
                by_key[key]["required"] = True
    return sorted(by_key.values(), key=lambda row: row["key"])


def click_parameters(path: Path) -> list[dict[str, Any]]:
    tree = ast.parse(path.read_text())
    rows = [parameter("input_path", None, required=True, help_text="YAML input file or directory.")]
    predict = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "predict")
    for decorator in predict.decorator_list:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute) or decorator.func.attr != "option":
            continue
        option = literal(decorator.args[0]) if decorator.args else None
        if not isinstance(option, str):
            continue
        kwargs = {kw.arg: kw.value for kw in decorator.keywords if kw.arg}
        key = option.lstrip("-").replace("-", "_")
        default = literal(kwargs.get("default"))
        is_flag = bool(literal(kwargs.get("is_flag")))
        type_node = kwargs.get("type")
        type_name = literal(type_node)
        kind = {"int": "integer", "float": "number", "bool": "boolean"}.get(type_name, "boolean" if is_flag else "string")
        rows.append(parameter(
            key, default if default is not None else (False if is_flag else None),
            kind=kind, help_text=literal(kwargs.get("help")) or "",
            boolean_style="flag" if is_flag else None,
        ))
    return sorted(rows, key=lambda row: row["key"])


def function_parameters(path: Path, function_name: str) -> list[dict[str, Any]]:
    tree = ast.parse(path.read_text())
    fn = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == function_name)
    positional = list(fn.args.args)
    defaults = [None] * (len(positional) - len(fn.args.defaults)) + list(fn.args.defaults)
    pairs = list(zip(positional, defaults))
    pairs.extend(zip(fn.args.kwonlyargs, fn.args.kw_defaults))
    rows = []
    for arg, default_node in pairs:
        default = literal(default_node)
        annotation = ast.unparse(arg.annotation) if arg.annotation else ""
        kind = "boolean" if "bool" in annotation else "integer" if "int" in annotation else "string"
        rows.append(parameter(arg.arg, default, kind=kind, required=default_node is None))
    return rows


def bindcraft_parameters(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    defaults = {
        "target": json.loads((root / "settings_target/PDL1.json").read_text()),
        "advanced": json.loads((root / "settings_advanced/default_4stage_multimer.json").read_text()),
        "filters": json.loads((root / "settings_filters/default_filters.json").read_text()),
    }
    rows = []
    for group in ("target", "advanced"):
        for key, value in defaults[group].items():
            kind = "boolean" if isinstance(value, bool) else "integer" if isinstance(value, int) else "number" if isinstance(value, float) else "json" if isinstance(value, (list, dict)) else "string"
            rows.append(parameter(key, value, kind=kind, group=group))
    for key, value in defaults["filters"].items():
        rows.append(parameter(key, value, kind="json", group="filters"))
    return rows, defaults


def rosetta_parameters() -> list[dict[str, Any]]:
    rows = [
        ("application", "rosetta_scripts", "string"), ("s", None, "string"),
        ("parser:protocol", None, "string"), ("parser:script_vars", None, "string"),
        ("nstruct", 1, "integer"), ("score:weights", "ref2015", "string"),
        ("interface", "A_B", "string"), ("resfile", None, "string"),
        ("constraints:cst_fa_file", None, "string"), ("out:path:all", "output", "string"),
        ("out:file:scorefile", "score.sc", "string"), ("out:suffix", None, "string"),
        ("ex1", False, "boolean"), ("ex2", False, "boolean"), ("beta", False, "boolean"),
        ("overwrite", False, "boolean"), ("renumber_pdb", False, "boolean"),
        ("per_chain_renumbering", False, "boolean"), ("ignore_unrecognized_res", False, "boolean"),
        ("constant_seed", False, "boolean"), ("jran", None, "integer"),
        ("relax:constrain_relax_to_start_coords", False, "boolean"),
        ("relax:ramp_constraints", False, "boolean"), ("relax:script", None, "string"),
        ("relax:default_repeats", None, "integer"), ("packing:repack_only", False, "boolean"),
        ("pack_input", False, "boolean"), ("use_input_sc", False, "boolean"),
        ("mute", None, "string"), ("unmute", None, "string"),
        ("database", None, "string"), ("in:file:extra_res_fa", None, "string"),
        ("ddg:iterations", None, "integer"), ("ddg:dump_pdbs", False, "boolean"),
        ("ddg:cartesian", False, "boolean"), ("fa_max_dis", None, "number"),
    ]
    return [
        parameter(key, default, kind=kind, required=key == "s", boolean_style="flag" if kind == "boolean" else None)
        for key, default, kind in rows
    ]


def clone_pinned(name: str, destination: Path) -> Path:
    meta = UPSTREAMS[name]
    path = destination / name
    if not path.exists():
        subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", meta["repo"], str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "fetch", "--depth", "1", "origin", meta["commit"]], check=True)
    subprocess.run(["git", "-C", str(path), "checkout", "--detach", meta["commit"]], check=True)
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout-root", type=Path, help="Directory containing named upstream checkouts.")
    parser.add_argument("--clone-root", type=Path, help="Clone/fetch pinned upstream revisions here.")
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("catalog.json"))
    args = parser.parse_args()
    if not args.checkout_root and not args.clone_root:
        parser.error("one of --checkout-root or --clone-root is required")

    roots = {}
    aliases = {
        "rfdiffusion": "rfd", "proteinmpnn": "mpnn", "alphafold2": "af",
        "alphafold3": "af3", "boltz": "boltz", "chai1": "chai", "bindcraft": "bindcraft",
    }
    for name in aliases:
        roots[name] = clone_pinned(name, args.clone_root) if args.clone_root else args.checkout_root / aliases[name]

    rfd_config = yaml.safe_load((roots["rfdiffusion"] / "config/inference/base.yaml").read_text())
    bindcraft_rows, bindcraft_defaults = bindcraft_parameters(roots["bindcraft"])
    repository_root = Path(__file__).resolve().parents[2]
    mask_root = repository_root / "models/maskrgnn_clean/conf"
    mask_config = yaml.safe_load((mask_root / "inference.yaml").read_text())
    mask_model = yaml.safe_load((mask_root / "model/egnn.yaml").read_text())
    mask_data = yaml.safe_load((mask_root / "data/cath.yaml").read_text())
    mask_config.pop("defaults", None)
    mask_config["model"] = mask_model
    mask_config["data"] = mask_data
    models = {
        "rfdiffusion": flatten_yaml(rfd_config),
        "proteinmpnn": argparse_parameters(roots["proteinmpnn"] / "protein_mpnn_run.py"),
        "alphafold2": absl_parameters(roots["alphafold2"] / "run_alphafold.py"),
        "alphafold3": absl_parameters(roots["alphafold3"] / "run_alphafold.py"),
        "boltz": click_parameters(roots["boltz"] / "src/boltz/main.py"),
        "chai1": function_parameters(roots["chai1"] / "chai_lab/chai1.py", "run_inference"),
        "bindcraft": bindcraft_rows,
        "rosetta": rosetta_parameters(),
        "maskrgn": flatten_yaml(mask_config),
    }
    payload = {
        "schema_version": 1,
        "generated_from": UPSTREAMS,
        "models": {
            name: {
                **UPSTREAMS[name],
                "parameters": rows,
                "parameter_count": len(rows),
                **({"default_json": bindcraft_defaults} if name == "bindcraft" else {}),
            }
            for name, rows in models.items()
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {args.output}")
    for name, item in payload["models"].items():
        print(f"{name}: {item['parameter_count']} parameters")


if __name__ == "__main__":
    main()
