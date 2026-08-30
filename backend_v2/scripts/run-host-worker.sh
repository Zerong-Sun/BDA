#!/usr/bin/env bash
# Run the compute worker on the host.
#
# The dispatch/poll/collect queues talk to the compute cluster. On this deployment the
# route to the cluster is a host VPN, which a container's network namespace does not
# inherit, so those queues run here instead of in docker. Everything else (research,
# copilot, maintenance) stays containerised.
#
#   backend_v2/scripts/run-host-worker.sh            # run in the foreground
#   backend_v2/scripts/run-host-worker.sh --check    # verify connectivity and exit
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
venv="$repo_root/backend_v2/.venv"
host_env="$repo_root/backend_v2/scripts/host-worker.env"

if [[ ! -x "$venv/bin/celery" ]]; then
  echo "error: $venv is missing. Create it with:" >&2
  echo "  python3.13 -m venv backend_v2/.venv && backend_v2/.venv/bin/pip install -e 'backend_v2[dev]'" >&2
  exit 1
fi
if [[ ! -f "$host_env" ]]; then
  echo "error: $host_env not found." >&2
  echo "  cp backend_v2/scripts/host-worker.env.example backend_v2/scripts/host-worker.env" >&2
  exit 1
fi

# Repository .env first, then the host overrides, so the host file only needs to state
# what actually differs from the containerised configuration.
set -a
# shellcheck disable=SC1091
[[ -f "$repo_root/.env" ]] && . "$repo_root/.env"
# shellcheck disable=SC1090
. "$host_env"
set +a

export PYTHONPATH="$repo_root${PYTHONPATH:+:$PYTHONPATH}"

if [[ "${1:-}" == "--check" ]]; then
  exec "$venv/bin/python" "$repo_root/backend_v2/scripts/check_host_worker.py"
fi

# Solo pool: the SSH transport holds a live connection per adapter, which does not
# survive being forked into prefork children.
exec "$venv/bin/celery" -A backend_v2.app.compute.tasks.celery_app worker \
  --pool=solo \
  -Q dispatch,poll,collect \
  --hostname="host-compute@%h" \
  --loglevel="${BDA_WORKER_LOGLEVEL:-info}"
