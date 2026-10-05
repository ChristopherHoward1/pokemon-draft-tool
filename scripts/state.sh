#!/usr/bin/env bash
# Derive one work unit's execution state from observable repo facts.
set -uo pipefail

usage() {
  echo "Usage: scripts/state.sh <slug>" >&2
}

die() {
  echo "state: $*" >&2
  exit 1
}

has_line() {
  local line="$1"
  grep -qx -- "$line" <<<"$plan"
}

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

slug="$1"
branch="wt/$slug"
plan_path="work/$slug/plan.md"
root=$(git rev-parse --show-toplevel) || die "not inside a git checkout"
cd "$root" || die "cannot cd to repo root: $root"

[[ -f "$plan_path" ]] || die "not a work unit: $slug"

branch_exists=false
if git rev-parse --verify --quiet "$branch" >/dev/null; then
  branch_exists=true
fi

if [[ "$branch_exists" == true ]]; then
  plan=$(git show "$branch:$plan_path") \
    || die "cannot read plan from $branch:$plan_path"
else
  plan=$(<"$plan_path")
fi

if has_line 'Code-review verdict: APPROVE' && has_line 'Codex-review verdict: APPROVE'; then
  review=approve
else
  review=pending
fi

last_released=
if [[ -f work/.last-released ]]; then
  last_released=$(
    awk '
      NR == 1 {
        gsub(/^[[:space:]]+|[[:space:]]+$/, "")
        print
        exit
      }
    ' work/.last-released
  )
fi

if ! has_line 'Plan verdict: APPROVE'; then
  stage=plan
  next_action='finish /1-plan'
elif [[ ! -f "work/$slug/handoff.md" && "$branch_exists" == false ]]; then
  stage=implement
  next_action='/2-implement'
elif [[ "$review" != approve ]]; then
  stage=review
  if [[ -f "work/$slug/codex-review.md" ]]; then
    next_action='/3-review'
  else
    next_action='run scripts/gate.sh'
  fi
elif [[ "$last_released" != "$slug" ]]; then
  stage=release
  next_action='/4-release'
elif [[ ! -s "work/$slug/retro.md" ]]; then
  stage=release
  next_action='/5-retro'
else
  stage='done'
  next_action=none
fi

printf 'slug: %s\n' "$slug"
printf 'stage: %s\n' "$stage"
printf 'review: %s\n' "$review"
printf 'next_action: %s\n' "$next_action"
