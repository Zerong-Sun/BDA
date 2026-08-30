"""Fail when a registered plugin reserves more than one slot without saying why.

``-n`` is not free. On this project's cluster a job that holds cores it does not use
draws a low-utilisation inspection mail, which the operating rules treat as a violation
rather than a notice (docs/QM_CLUSTER_OPERATION_RULES.md, decision D061). The cost has
been paid once already: jobs 4167123/4167124 inherited ``-n 4`` from an unrelated job and
were killed in PEND, and the replacement measured CPU PEAK 1.00 on one slot.

The declarations that produced those numbers were unreviewable, because a bare
``"cpus": 8`` records no reason. So the rule is: **more than one slot requires a
``cpus_evidence`` string** naming the measurement or the upstream flag that supports it.
Reviewing "8, because --jackhmmer_n_cpu defaults to 8" is possible; reviewing "8" is not.

Nothing here checks that the number is *correct* - no static check can. It checks that
someone had to write down a reason, which is what makes a wrong number arguable later.

    PYTHONPATH=. python backend_v2/scripts/check_plugin_cpu_declarations.py
"""

from __future__ import annotations

from backend_v2.app.core.database import session_scope
from backend_v2.app.registry.models import ModelPlugin
from sqlalchemy import select

#: Short enough to be a shrug rather than a reason.
MIN_EVIDENCE_CHARS = 20


def problems() -> list[str]:
    found: list[str] = []
    with session_scope() as session:
        for plugin in session.scalars(select(ModelPlugin)):
            resources = plugin.resources if isinstance(plugin.resources, dict) else {}
            cpus = resources.get("cpus")
            if not isinstance(cpus, int):
                # Absent means one slot, which is the default that needs no defence.
                continue
            if cpus <= 1:
                continue
            evidence = resources.get("cpus_evidence")
            if not isinstance(evidence, str) or len(evidence.strip()) < MIN_EVIDENCE_CHARS:
                found.append(
                    f"{plugin.plugin_key}: reserves {cpus} slots with no usable "
                    f"'cpus_evidence'. Name the measurement or the upstream thread flag "
                    f"that supports {cpus}, or declare 1."
                )
    return found


def main() -> int:
    failures = problems()
    for failure in failures:
        print(f"[FAIL] {failure}")
    if failures:
        return 1
    print("plugin slot declarations: every count above 1 carries its evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
