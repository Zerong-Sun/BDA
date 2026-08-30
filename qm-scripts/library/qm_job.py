#!/usr/bin/env python3
"""Validate model parameters and render a reproducible LSF job bundle."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "catalog.json"
EXAMPLES_DIR = ROOT / "examples"


def fail(message: str, fix_path: Path | str, code: int = 2) -> None:
    print(f"[ERROR] {message}", file=sys.stderr)
    print(f"[BDA_FIX_PATH] {Path(fix_path).resolve()}", file=sys.stderr)
    raise SystemExit(code)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except FileNotFoundError:
        fail("file not found", path)
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}", path)
    if not isinstance(value, dict):
        fail("top-level JSON value must be an object", path)
    return value


def catalog() -> dict[str, Any]:
    return load_json(CATALOG_PATH)


def shell_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"))
    return str(value)


def validate_type(key: str, value: Any, expected: str, config_path: Path) -> None:
    good = {
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "list": isinstance(value, list),
        "json": isinstance(value, (dict, list, str)),
        "string": isinstance(value, (str, type(None))),
    }.get(expected, True)
    if not good:
        fail(f"parameter {key!r} must be {expected}, got {type(value).__name__}", config_path)


def validate(config_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    cfg = load_json(config_path)
    model_name = cfg.get("model")
    models = catalog().get("models", {})
    if model_name not in models:
        fail(f"unknown model {model_name!r}; choose one of: {', '.join(sorted(models))}", config_path)
    model = models[model_name]
    if model.get("available") is False:
        # The catalog still documents the model's interface, which is worth keeping, but
        # rendering a job for something with no cluster installation only produces a job
        # that fails an hour later in the queue.
        reason = model.get("unavailable_reason", "no reason recorded")
        fail(f"model {model_name!r} is not available: {reason}", config_path)
    specs = {item["key"]: item for item in model["parameters"]}
    params = cfg.get("parameters", {})
    if not isinstance(params, dict):
        fail("parameters must be an object", config_path)
    unknown = sorted(set(params) - set(specs))
    if unknown:
        fail(f"unknown parameters for {model_name}: {', '.join(unknown)}", config_path)
    for key, value in params.items():
        validate_type(key, value, specs[key].get("type", "string"), config_path)
    missing = [
        key for key, spec in specs.items()
        if spec.get("required") and (key not in params or params[key] in (None, ""))
    ]
    if missing:
        fail(f"missing required parameters: {', '.join(missing)}", config_path)
    scheduler = cfg.get("scheduler", {})
    if not isinstance(scheduler, dict):
        fail("scheduler must be an object", config_path)
    return cfg, model, specs


def merged_parameters(cfg: dict[str, Any], specs: dict[str, Any]) -> dict[str, Any]:
    if not cfg.get("include_defaults", False):
        return dict(cfg.get("parameters", {}))
    values = {key: spec.get("default") for key, spec in specs.items() if spec.get("default") is not None}
    values.update(cfg.get("parameters", {}))
    return values


def command_words(executable: str) -> list[str]:
    words = shlex.split(executable)
    if not words:
        raise ValueError("empty executable")
    return words


def render_cli(executable: str, params: dict[str, Any], specs: dict[str, Any], *, prefix: list[str] | None = None) -> str:
    words = [*command_words(executable), *(prefix or [])]
    for key, value in params.items():
        if value is None or value == "":
            continue
        spec = specs[key]
        option = "--" + key
        if spec.get("boolean_style") == "flag":
            if value:
                words.append(option)
            continue
        if spec.get("boolean_style") == "value":
            # Abseil boolean flags are unambiguous as --flag=true/false.  Rendering
            # ``--flag false`` can be parsed as a true flag followed by an orphan
            # positional argument, depending on the entrypoint's flag library.
            words.append(f"{option}={'true' if value else 'false'}")
            continue
        if isinstance(value, list):
            # argparse action='append' and Abseil multi_string flags both require one
            # option occurrence per item.  A JSON-encoded list is a single literal
            # path/value and is not equivalent (notably for AF3 --db_dir).
            for item in value:
                words.extend([option, shell_value(item)])
            continue
        words.extend([option, shell_value(value)])
    return " ".join(shlex.quote(word) for word in words)


def render_command(
    cfg: dict[str, Any],
    model: dict[str, Any],
    specs: dict[str, Any],
    bundle: Path,
) -> str:
    name = cfg["model"]
    params = merged_parameters(cfg, specs)
    style = model["style"]
    default_executable = {
        "rfdiffusion": f"python {model['entrypoint']}",
        "proteinmpnn": f"python {model['entrypoint']}",
        "alphafold2": f"python {model['entrypoint']}",
        "alphafold3": f"python {model['entrypoint']}",
        "boltz": "boltz",
        "chai1": "python",
        "bindcraft": f"python -u {model['entrypoint']}",
        "maskrgn": f"python {model['entrypoint']}",
    }.get(name, model["entrypoint"])
    executable = cfg.get("executable") or default_executable
    if style == "hydra":
        words = command_words(executable)
        for key, value in params.items():
            if value is not None and value != "":
                if isinstance(value, list) and all(isinstance(item, str) for item in value):
                    # Hydra list syntax is [a,b], not JSON. shell_value would emit
                    # ["A26-566/B23-570/C1-53"] and the inner quotes become part of the
                    # contig string. Every RFdiffusion command that has actually completed
                    # in this project used the unquoted form; the quoted one exists only in
                    # a rendered preview that was reviewed and never executed.
                    rendered = "[" + ",".join(value) + "]"
                else:
                    rendered = shell_value(value)
                words.append(f"{key}={rendered}")
        return " ".join(shlex.quote(word) for word in words)
    if style in {"argparse", "absl"}:
        return render_cli(executable, params, specs)
    if style == "click":
        input_path = params.pop("input_path")
        return render_cli(executable, params, specs, prefix=["predict", str(input_path)])
    if style == "rosetta_flags":
        application = params.pop("application", "rosetta_scripts")
        words = [executable if cfg.get("executable") else application]
        for key, value in params.items():
            if value is None or value == "":
                continue
            if specs[key].get("boolean_style") == "flag":
                if value:
                    words.append(f"-{key}")
            elif isinstance(value, list):
                # Rosetta multi-valued options (-docking:dock_pert 3 8) need one argv entry
                # per value. Joining them into a single quoted string makes Rosetta report
                # "No values of the appropriate type specified" and exit 255.
                words.append(f"-{key}")
                words.extend(shell_value(item) for item in value)
            else:
                words.extend([f"-{key}", shell_value(value)])
        return " ".join(shlex.quote(word) for word in words)
    if style == "python_call":
        wrapper = bundle / "run_chai.py"
        wrapper.write_text(
            "import json\nfrom pathlib import Path\nfrom chai_lab.chai1 import run_inference\n"
            "p=json.loads(Path('config.resolved.json').read_text())['parameters']\n"
            "for k in ('fasta_file','output_dir','msa_directory','constraint_path','template_hits_path'):\n"
            "    if p.get(k) is not None: p[k]=Path(p[k])\n"
            "run_inference(**p)\n"
        )
        return " ".join(shlex.quote(word) for word in [*command_words(executable), wrapper.name])
    if style == "json_bundle":
        defaults = model["default_json"]
        groups = {name: json.loads(json.dumps(value)) for name, value in defaults.items()}
        for key, value in params.items():
            groups[specs[key].get("group", "advanced")][key] = value
        for group, value in groups.items():
            (bundle / f"{group}.json").write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        return " ".join([
            *(shlex.quote(word) for word in command_words(executable)),
            "--settings", "target.json",
            "--filters", "filters.json",
            "--advanced", "advanced.json",
        ])
    fail(f"unsupported render style: {style}", CATALOG_PATH)
    return ""


def render(config_path: Path, output_dir: Path) -> Path:
    cfg, model, specs = validate(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    params = merged_parameters(cfg, specs)
    resolved = {**cfg, "parameters": params, "source_config": str(config_path.resolve()), "upstream": {
        "repo": model["repo"], "commit": model["commit"], "entrypoint": model["entrypoint"],
    }}
    (output_dir / "config.resolved.json").write_text(json.dumps(resolved, ensure_ascii=False, indent=2) + "\n")
    command = render_command(cfg, model, specs, output_dir)
    scheduler = cfg.get("scheduler", {})
    queue = scheduler.get("queue", "gpu-bme-liz")
    cpus = int(scheduler.get("cpus", 1))
    gpu_count = int(scheduler.get("gpus", 1))
    job_name = scheduler.get("job_name", f"qm-{cfg['model']}")
    setup = cfg.get("setup", ["module purge"])
    if not isinstance(setup, list):
        fail("setup must be a list of shell lines", config_path)
    fix_path = config_path.resolve()
    lines = [
        "#!/bin/bash",
        f"#BSUB -J {job_name}",
        f"#BSUB -q {queue}",
        f"#BSUB -n {cpus}",
        # ptile is slots PER HOST, so ptile=1 spreads -n slots across -n separate hosts.
        # Every model here is single-node, and a single-GPU job asking for four hosts
        # stays PEND on "Not enough hosts to meet the job's spanning requirement" rather
        # than failing. Pack all slots onto one host by default; allow an explicit
        # override for a genuinely multi-node model.
        f'#BSUB -R "span[ptile={int(scheduler.get("ptile", cpus))}]"',
        "#BSUB -o logs/%J.out",
        "#BSUB -e logs/%J.err",
    ]
    if gpu_count:
        lines.append(f'#BSUB -gpu "num={gpu_count}"')
    lines.extend([
        "",
        "set -Eeuo pipefail",
        "export BDA_FIX_PATH=\"$PWD/config.resolved.json\"",
        f"export BDA_SOURCE_CONFIG={shlex.quote(str(fix_path))}",
        f"export BDA_MODEL={shlex.quote(cfg['model'])}",
        "mkdir -p logs output",
        "on_error() {",
        "  code=$?",
        "  echo \"[ERROR] model=${BDA_MODEL} exit=${code} line=${BASH_LINENO[0]}\" >&2",
        "  echo \"[BDA_FIX_PATH] ${BDA_FIX_PATH}\" >&2",
        "  echo \"[BDA_SOURCE_CONFIG] ${BDA_SOURCE_CONFIG}\" >&2",
        "  echo \"[BDA_JOB_SCRIPT] $(pwd)/submit.lsf\" >&2",
        "  echo \"[BDA_LOG_DIR] $(pwd)/logs\" >&2",
        "  exit \"$code\"",
        "}",
        "trap on_error ERR",
        *[str(line) for line in setup],
        command,
        "",
    ])
    script = output_dir / "submit.lsf"
    script.write_text("\n".join(lines))
    (output_dir / "EDIT_THIS_PATH.txt").write_text(str(fix_path) + "\n")
    print(f"[OK] rendered {script}")
    if cfg.get("description"):
        print(f"[INFO] {cfg['description']}")
    print(f"[BDA_FIX_PATH] {fix_path}")
    return script


def list_models() -> None:
    for name, model in sorted(catalog()["models"].items()):
        print(f"{name}\t{model['parameter_count']}\t{model['repo']}@{model['commit'][:12]}")


def list_examples() -> None:
    files = sorted(EXAMPLES_DIR.rglob("*.json"))
    if not files:
        fail("no example configs found", EXAMPLES_DIR)
    for path in files:
        rel = path.relative_to(EXAMPLES_DIR)
        try:
            cfg = json.loads(path.read_text())
        except json.JSONDecodeError:
            print(f"{rel}\t(invalid JSON)")
            continue
        model = cfg.get("model", "?")
        description = str(cfg.get("description", "")).replace("\t", " ")
        print(f"{rel}\t{model}\t{description}")


def list_parameters(model_name: str) -> None:
    models = catalog()["models"]
    if model_name not in models:
        fail(f"unknown model {model_name!r}", CATALOG_PATH)
    for item in models[model_name]["parameters"]:
        help_text = str(item.get("help", "")).replace("\t", " ").replace("\n", " ")
        print("\t".join([
            item["key"], item.get("type", "string"),
            json.dumps(item.get("default"), ensure_ascii=False),
            "required" if item.get("required") else "",
            item.get("group", "parameters"),
            help_text,
        ]))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate model parameters and render a reproducible LSF job bundle."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("models", help="List catalogued models and parameter counts.")
    sub.add_parser("examples", help="List bundled example configs and what they do.")
    params_parser = sub.add_parser("params", help="List every parameter for one model.")
    params_parser.add_argument("model")
    validate_parser = sub.add_parser("validate", help="Check a config against the catalog.")
    validate_parser.add_argument("config", type=Path)
    render_parser = sub.add_parser("render", help="Render a config into an LSF job bundle.")
    render_parser.add_argument("config", type=Path)
    render_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "models":
        list_models()
    elif args.command == "examples":
        list_examples()
    elif args.command == "params":
        list_parameters(args.model)
    elif args.command == "validate":
        cfg, _, _ = validate(args.config)
        print(f"[OK] valid: {args.config}")
        if cfg.get("description"):
            print(f"[INFO] {cfg['description']}")
        print(f"[BDA_FIX_PATH] {args.config.resolve()}")
    elif args.command == "render":
        render(args.config, args.output)


if __name__ == "__main__":
    main()
