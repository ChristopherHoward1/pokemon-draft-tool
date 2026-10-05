#!/usr/bin/env bash
# Check whether ARCHI.md is at least as fresh as architecture-relevant source paths.
set -uo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 2

SOURCE_PATHS=(app/ client/src/ config/ engine/ scripts/ server/ skills/ profiles/ config.yaml CLAUDE.md)

usage() {
  cat <<'EOF'
Usage: scripts/archi-fresh.sh [<ref>]

Checks ARCHI.md freshness against source paths at <ref>. Defaults to HEAD.
EOF
}

if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
  usage
  exit 0
fi

if [[ $# -gt 1 ]]; then
  usage >&2
  exit 2
fi

ref="${1:-HEAD}"

archi_epoch=$(git log -1 --format=%ct "$ref" -- ARCHI.md)
source_epoch=$(git log -1 --format=%ct "$ref" -- "${SOURCE_PATHS[@]}")

if [[ -z "$archi_epoch" ]]; then
  echo "ARCHI.md has no git history at $ref" >&2
  exit 2
fi

if [[ -z "$source_epoch" ]]; then
  echo "source paths have no git history at $ref" >&2
  exit 2
fi

if (( archi_epoch < source_epoch )); then
  newer_paths=()
  for path in "${SOURCE_PATHS[@]}"; do
    path_epoch=$(git log -1 --format=%ct "$ref" -- "$path")
    if [[ -n "$path_epoch" && "$path_epoch" -gt "$archi_epoch" ]]; then
      newer_paths+=("$path")
    fi
  done
  printf 'ARCHI.md is stale at %s; newer source path(s): %s; refresh ARCHI on the branch\n' \
    "$ref" "${newer_paths[*]}" >&2
  exit 1
fi
