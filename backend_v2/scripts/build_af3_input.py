"""Build an AlphaFold 3 fold_input.json from FASTA files.

The same converter the platform runs at dispatch, exposed for use outside a workflow —
checking what a node will produce, or preparing a specification by hand.

    python backend_v2/scripts/build_af3_input.py designs.fa target.fa -o fold_input.json
    python backend_v2/scripts/build_af3_input.py designs.fa --name my_job --seeds 1 2 3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend_v2.app.compute.input_adapters.af3_fold_input import build_fold_input, parse_fasta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("fasta", nargs="+", type=Path, help="FASTA file(s); each record becomes a chain")
    parser.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    parser.add_argument("--name", default=None, help="job name (default: first file's stem)")
    parser.add_argument("--seeds", type=int, nargs="+", default=None, help="model seeds (default: 1)")
    args = parser.parse_args(argv)

    records: list[tuple[str, str]] = []
    for path in args.fasta:
        if not path.is_file():
            print(f"error: {path} is not a file", file=sys.stderr)
            return 2
        records.extend(parse_fasta(path.read_text(encoding="utf-8")))

    if not records:
        print("error: no FASTA records found", file=sys.stderr)
        return 1

    payload = build_fold_input(records, name=args.name or args.fasta[0].stem, model_seeds=args.seeds)
    rendered = json.dumps(payload, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"wrote {args.output} with {len(records)} chain(s)", file=sys.stderr)
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
