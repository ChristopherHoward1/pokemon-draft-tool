#!/usr/bin/env bash
# Dispatch the implementer agent into a worktree with a handoff on stdin.
# Usage: scripts/agent-exec.sh <worktree-path> <handoff-file>
#
# The implementer command comes from config.yaml (implementer.command) —
# this script is the ONLY place an external agent is invoked, so swapping
# vendors is a one-line config change, not a script rewrite.
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
WORKTREE=${1:?usage: agent-exec.sh <worktree-path> <handoff-file>}
HANDOFF=${2:?usage: agent-exec.sh <worktree-path> <handoff-file>}

[[ -d "$WORKTREE" ]] || { echo "Error: worktree not found: $WORKTREE" >&2; exit 1; }
WORKTREE=$(cd "$WORKTREE" && pwd -P)
[[ -s "$HANDOFF" ]] || { echo "Error: handoff missing or empty: $HANDOFF" >&2; exit 1; }

CMD=$(awk "/^implementer:/{f=1;next} f&&/command:/{sub(/^[[:space:]]*command:[[:space:]]*'/,\"\");sub(/'[[:space:]]*\$/,\"\");print;exit}" "$ROOT/config.yaml")
[[ -n "$CMD" ]] || { echo "Error: implementer.command not set in config.yaml" >&2; exit 1; }

HANDOFF_ABS=$(cd "$(dirname "$HANDOFF")" && pwd -P)/$(basename "$HANDOFF")
HEAD_BEFORE=$(git -C "$WORKTREE" rev-parse HEAD)
STATUS_BEFORE=$(git -C "$WORKTREE" status --porcelain)

echo "Dispatching implementer in $WORKTREE" >&2
echo "  $CMD < $HANDOFF_ABS" >&2
cd "$WORKTREE"
set +e
eval "$CMD" < "$HANDOFF_ABS"
status=$?
set -e
if [[ "$status" -ne 0 ]]; then
  exit "$status"
fi

HEAD_AFTER=$(git -C "$WORKTREE" rev-parse HEAD)
if [[ -z "$STATUS_BEFORE" && "$HEAD_AFTER" == "$HEAD_BEFORE" && -z "$(git -C "$WORKTREE" status --porcelain)" ]]; then
  echo "Error: implementer produced no new commit and left no worktree changes" >&2
  exit 1
fi
