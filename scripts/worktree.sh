#!/usr/bin/env bash
# Manage isolated implementation worktrees.
# Usage:
#   scripts/worktree.sh add <slug>      # create worktree + branch wt/<slug>, print its path
#   scripts/worktree.sh remove <slug>   # remove worktree, keep the branch
#   scripts/worktree.sh sync-artifacts <slug>  # copy primary work artifacts into worktree + commit
#   scripts/worktree.sh list
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"

# Naive-but-sufficient config read; override with WORKTREES_DIR env var.
WT_DIR=${WORKTREES_DIR:-$(awk '/^worktrees:/{f=1;next} f&&/dir:/{print $2; exit}' config.yaml)}
WT_DIR=${WT_DIR:-../$(basename "$ROOT")-worktrees}

cmd=${1:-}
slug=${2:-}

worktree_for_branch() {
  local branch="$1"

  git worktree list --porcelain | awk -v branch="refs/heads/$branch" '
    $1 == "worktree" {
      path = substr($0, 10)
      next
    }
    $1 == "branch" && $2 == branch {
      print path
      found = 1
      exit
    }
    END {
      if (!found) exit 1
    }
  '
}

case "$cmd" in
  add)
    [[ -n "$slug" ]] || { echo "usage: worktree.sh add <slug>" >&2; exit 1; }
    mkdir -p "$WT_DIR"
    path="$WT_DIR/$slug"
    [[ -e "$path" ]] && { echo "Error: $path already exists" >&2; exit 1; }
    if git show-ref --verify --quiet "refs/heads/wt/$slug"; then
      git worktree add "$path" "wt/$slug" >&2
    else
      git fetch origin --quiet 2>/dev/null || true
      if git show-ref --verify --quiet refs/remotes/origin/main; then
        git worktree add -b "wt/$slug" "$path" origin/main >&2
      else
        git worktree add -b "wt/$slug" "$path" >&2
      fi
    fi
    if [[ -f "$ROOT/work/$slug/plan.md" ]] &&
      [[ -z "$(git -C "$path" ls-tree -r --name-only HEAD -- "work/$slug/plan.md")" ]]; then
      mkdir -p "$path/work/$slug"
      cp "$ROOT/work/$slug/plan.md" "$path/work/$slug/plan.md"
      git -C "$path" add -- "work/$slug/plan.md"
      git -C "$path" commit -q -m "Record plan for $slug"
    fi
    # stdout carries only the path, so callers can capture it
    cd "$path" && pwd -P
    ;;
  remove)
    [[ -n "$slug" ]] || { echo "usage: worktree.sh remove <slug>" >&2; exit 1; }
    git worktree remove "$WT_DIR/$slug"
    echo "Removed worktree. Branch wt/$slug kept; delete with: git branch -D wt/$slug" >&2
    ;;
  sync-artifacts)
    [[ -n "$slug" ]] || { echo "usage: worktree.sh sync-artifacts <slug>" >&2; exit 1; }
    [[ "$(git rev-parse --git-dir)" == "$(git rev-parse --git-common-dir)" ]] || { echo "Error: sync-artifacts must run from the primary checkout" >&2; exit 1; }
    wt_root=$(worktree_for_branch "wt/$slug") || { echo "Error: no worktree for $slug" >&2; exit 1; }
    [[ -d "$ROOT/work/$slug" ]] || { echo "Error: primary checkout has no work/$slug directory" >&2; exit 1; }
    mkdir -p "$wt_root/work/$slug"
    for src in "$ROOT/work/$slug"/*; do
      [[ -f "$src" && ! -L "$src" && "$(basename "$src")" != plan.md ]] || continue
      cp "$src" "$wt_root/work/$slug/"
    done
    git -C "$wt_root" add -- "work/$slug"
    if ! git -C "$wt_root" diff --cached --quiet -- "work/$slug/plan.md"; then
      git -C "$wt_root" reset -q -- "work/$slug/plan.md"
    fi
    if ! git -C "$wt_root" diff --cached --quiet -- "work/$slug" ":(exclude)work/$slug/plan.md"; then
      git -C "$wt_root" commit -q -m "Record artifacts for $slug" -- "work/$slug" ":(exclude)work/$slug/plan.md"
    fi
    ;;
  list)
    git worktree list
    ;;
  *)
    echo "usage: worktree.sh {add|remove|sync-artifacts|list} [slug]" >&2
    exit 1
    ;;
esac
