"""Record that a model plugin was observed to run correctly - or that it was not.

``registry_model_plugin_validate`` checks the declaration: image tag, non-empty command,
schema well-formedness, port coherence. It executes nothing, so ``validation_status=valid``
answers "is this record well formed", never "does this model work".

The difference is not pedantic. Two bugs in this project's plugins were invisible until
something actually ran: US-align segfaulted on ``-dir1``, and pdb2pqr rejected backbone-only
input. Worse, a model that does not recognise a parameter usually does not fail - RFdiffusion3
silently drops unknown conditioning keys and returns perfectly plausible unconditioned
backbones. A green exit code is compatible with the model having ignored everything you
asked for.

So evidence here is not "it exited zero". It is a list of things observed: which parameters
the model echoed back in its own logs, which output files matched the declared ports.

    python -m backend_v2.scripts.record_plugin_runtime_validation \\
        --plugin superfold --proven \\
        --evidence "log prints 'Using target structure as initial guess' => --initial_guess honoured" \\
        --evidence "output named model_4_ptm => --models 4 honoured" \\
        --job 4108871
"""

from __future__ import annotations

import argparse
import json

from backend_v2.app.core.database import session_scope
from backend_v2.app.registry.models import ModelPlugin
from backend_v2.app.registry.tasks import record_runtime_validation
from sqlalchemy import select


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", required=True, help="plugin_key, e.g. superfold")
    parser.add_argument("--plugin-version", default=None, help="disambiguate multiple versions")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--proven", action="store_true", help="observed to honour its parameters")
    group.add_argument("--failed", action="store_true", help="observed not to work")
    parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        required=True,
        help="What was observed. Repeatable. 'it did not error' is not evidence.",
    )
    parser.add_argument("--job", default=None, help="LSF job id or BDA job id")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = arguments()
    with session_scope() as session:
        query = select(ModelPlugin).where(ModelPlugin.plugin_key == args.plugin)
        if args.plugin_version:
            query = query.where(ModelPlugin.plugin_version == args.plugin_version)
        plugins = list(session.scalars(query))
        if not plugins:
            print(json.dumps({"status": "plugin_not_found", "plugin": args.plugin}))
            return 1
        if len(plugins) > 1:
            print(
                json.dumps(
                    {
                        "status": "ambiguous",
                        "plugin": args.plugin,
                        "versions": [item.plugin_version for item in plugins],
                        "hint": "pass --plugin-version",
                    }
                )
            )
            return 1
        plugin = plugins[0]
        evidence = {"observations": list(args.evidence)}
        if args.job:
            evidence["job"] = args.job
        if not args.dry_run:
            record_runtime_validation(session, plugin, proven=args.proven, evidence=evidence)
        else:
            session.rollback()
        print(
            json.dumps(
                {
                    "status": "proven" if args.proven else "failed",
                    "plugin": plugin.plugin_key,
                    "plugin_version": plugin.plugin_version,
                    "evidence": evidence,
                    "dry_run": args.dry_run,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
