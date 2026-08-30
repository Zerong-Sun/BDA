#!/bin/bash
set -Eeuo pipefail

if (( $# < 2 || $# > 3 )); then
  echo "Usage: $0 <rendered-job-dir> <ssh-host> [remote-root]" >&2
  echo "[BDA_FIX_PATH] $(pwd)" >&2
  exit 2
fi

LOCAL_DIR="$(cd "$1" && pwd)"
SSH_HOST="$2"
REMOTE_ROOT="${3:-/work/bme-sunzr/bda/qm-script-library}"
JOB_NAME="$(basename "$LOCAL_DIR")"
REMOTE_DIR="${REMOTE_ROOT%/}/${JOB_NAME}"
FIX_PATH="$(cat "${LOCAL_DIR}/EDIT_THIS_PATH.txt" 2>/dev/null || printf '%s' "${LOCAL_DIR}/config.resolved.json")"

on_error() {
  code=$?
  echo "[ERROR] upload failed exit=${code}" >&2
  echo "[BDA_FIX_PATH] ${FIX_PATH}" >&2
  echo "[BDA_LOCAL_BUNDLE] ${LOCAL_DIR}" >&2
  echo "[BDA_REMOTE_PATH] ${SSH_HOST}:${REMOTE_DIR}" >&2
  exit "$code"
}
trap on_error ERR

test -f "${LOCAL_DIR}/submit.lsf"
test -f "${LOCAL_DIR}/config.resolved.json"

ssh -o BatchMode=yes "$SSH_HOST" "umask 077 && mkdir -p '$REMOTE_DIR'"
tar -C "$LOCAL_DIR" -cf - . | ssh -o BatchMode=yes "$SSH_HOST" "tar -C '$REMOTE_DIR' -xf -"

echo "[OK] uploaded to ${SSH_HOST}:${REMOTE_DIR}"
echo "[SUBMIT] ssh ${SSH_HOST} \"cd '${REMOTE_DIR}' && bsub < submit.lsf\""
echo "[BDA_FIX_PATH] ${FIX_PATH}"
echo "[BDA_REMOTE_PATH] ${REMOTE_DIR}"
