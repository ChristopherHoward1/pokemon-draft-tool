#!/usr/bin/env bash
# Run a read-only Codex code review for wt/<slug>. The only write is the
# reviewer stdout artifact in the primary checkout's work/<slug>/ directory.
set -uo pipefail

usage() {
  echo "Usage: scripts/codex-review.sh <slug>" >&2
}

die2() {
  echo "codex-review: $*" >&2
  exit 2
}

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

slug="$1"
branch="wt/$slug"
plan_path="work/$slug/plan.md"
deferrals_path="work/$slug/deferrals.md"
root=$(git rev-parse --show-toplevel) || die2 "not inside a git checkout"
artifact="$root/work/$slug/codex-review.md"
current_branch=$(git symbolic-ref --quiet --short HEAD || true)

if [[ "$current_branch" == "$branch" ]]; then
  die2 "run from the primary checkout, not the $branch worktree"
fi

git rev-parse --verify --quiet "$branch" >/dev/null \
  || die2 "missing branch: $branch"

config=$(git show "main:config.yaml") \
  || die2 "cannot read config.yaml from main"

reviewer_command=$(
  awk '
    /^[^[:space:]#][^:]*:/ {
      if (f) exit
      if ($0 ~ /^reviewer:/) {
        f = 1
      }
      next
    }
    f && /^[[:space:]]*command:/ {
      sub(/^[[:space:]]*command:[[:space:]]*/, "")
      if ($0 ~ /^'\''/) {
        sub(/^'\''/, "")
        sub(/'\''[[:space:]]*$/, "")
      } else {
        sub(/[[:space:]]*#.*$/, "")
      }
      print
      found = 1
      exit
    }
    END {
      if (!found) exit 1
    }
  ' <<<"$config"
) || die2 "reviewer.command missing in main:config.yaml"

[[ -n "$reviewer_command" ]] || die2 "reviewer.command empty in main:config.yaml"
[[ -d "$root/work/$slug" ]] || die2 "missing work directory: $root/work/$slug"

prompt=$(mktemp)
artifact_tmp=""
trap 'rm -f "$prompt" "$artifact_tmp"' EXIT

{
  printf "You are an independent code reviewer for work unit \`%s\`.\n\n" "$slug"
  printf 'This is review round %s.\n\n' "${REVIEW_ROUND:-1}"
  printf 'Review the plan body and diff below. Report substantive findings first.\n'
  printf '\n'
  printf '%s\n' "--- PLAN ($branch:$plan_path) ---"
} >"$prompt"

git show "$branch:$plan_path" >>"$prompt" \
  || die2 "cannot read plan from $branch:$plan_path"

{
  printf '\n%s\n' "--- ACCEPTED DEFERRALS ($branch:$deferrals_path) ---"
  printf 'These findings were reviewed in an earlier round and deliberately deferred to a\n'
  printf 'later work unit. They are settled scope: do not raise them as findings here.\n'
  printf 'If one has become blocking, say so under a heading "Deferral challenge" and name\n'
  printf 'what changed since it was accepted.\n\n'
} >>"$prompt"

if git cat-file -e "$branch:$deferrals_path" 2>/dev/null; then
  git show "$branch:$deferrals_path" >>"$prompt" \
    || die2 "cannot read deferrals from $branch:$deferrals_path"
else
  printf '(none recorded)\n' >>"$prompt"
fi

git fetch origin --quiet 2>/dev/null || true
if git show-ref --verify --quiet refs/remotes/origin/main; then
  base=origin/main
else
  base=main
fi

printf '\n%s\n' "--- DIFF ($base...$branch excluding work/$slug) ---" >>"$prompt"
git diff "$base...$branch" -- ':/' ":(exclude,top)work/$slug" >>"$prompt" \
  || die2 "cannot diff $base...$branch"

{
  printf '\n'
  printf '## Severity\n\n'
  printf 'Every finding gets exactly one severity:\n'
  printf '- CRITICAL: data loss, security hole, or silent wrong result. Blocks in any round.\n'
  printf '- HIGH: incorrect behavior under a realistic scenario. Blocks in any round.\n'
  printf '- MEDIUM: robustness gap, missing validation, or incomplete contract. Never sets the verdict; report it for the orchestrator to route.\n'
  printf '- LOW: style, naming, log hygiene, non-blocking edge cases. Never blocks.\n\n'
  printf 'A finding without a concrete failure scenario is LOW by definition.\n\n'
  printf '## Calibration\n\n'
  printf 'Focus on what breaks the acceptance criteria, not on what you would write differently.\n'
  printf 'A diff that meets every criterion with no CRITICAL/HIGH findings is an APPROVE,\n'
  printf 'even if you see things you would improve. Report those as LOW.\n'
  printf 'REQUEST CHANGES requires at least one CRITICAL or HIGH finding.\n'
  printf 'If all findings are LOW, the verdict must be APPROVE with findings attached.\n\n'
  printf 'Your final line must be exactly one of:\n'
  printf 'Codex verdict: APPROVE\n'
  printf 'Codex verdict: REQUEST CHANGES\n'
} >>"$prompt"

artifact_tmp=$(mktemp "$root/work/$slug/.codex-review.XXXXXX") \
  || die2 "cannot create temporary artifact in $root/work/$slug"

bash -c "$reviewer_command" <"$prompt" >"$artifact_tmp"
reviewer_status=$?
if [[ "$reviewer_status" -ne 0 ]]; then
  die2 "reviewer command failed (exit $reviewer_status)"
fi

mv "$artifact_tmp" "$artifact" \
  || die2 "cannot write artifact: $artifact"
artifact_tmp=""

verdict_line=$(grep -E '^[[:space:]]*Codex verdict:' "$artifact" | tail -n 1 || true)
if [[ -z "$verdict_line" ]]; then
  die2 "no verdict in $artifact"
fi

verdict=${verdict_line#"${verdict_line%%[![:space:]]*}"}
verdict=${verdict#Codex verdict:}
verdict=${verdict#"${verdict%%[![:space:]]*}"}
verdict=${verdict%"${verdict##*[![:space:]]}"}

case "$verdict" in
  APPROVE)
    exit 0
    ;;
  "REQUEST CHANGES")
    exit 1
    ;;
  *)
    die2 "malformed verdict in $artifact: $verdict"
    ;;
esac
