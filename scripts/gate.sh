#!/usr/bin/env bash
# The gate. Exit 0 = pass. Non-zero = fail, and everything printed is the
# feedback the implementer gets. Agents do not overrule this script.
#
# Auto-detects the stacks present and runs every applicable check.
# Profile- or project-specific checks go in scripts/gate.d/*.sh (run last).
set -uo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1

fail=0
fail_message() {
  echo "GATE: FAIL — fix everything marked ✗ above."
}

run() {
  echo "▶ $*"
  if ! "$@"; then
    fail=1
    echo "✗ FAILED: $*"
  fi
}

required_tools=
if [[ ${GATE_REQUIRED_TOOLS+set} ]]; then
  required_tools=$GATE_REQUIRED_TOOLS
elif [[ -f config.yaml ]]; then
  required_tools=$(awk '
    /^[^[:space:]#][^:]*:/ {
      f = ($0 ~ /^gate:[[:space:]]*($|#)/)
      next
    }
    f && /^[[:space:]]*required_tools:/ {
      sub(/^[[:space:]]*required_tools:[[:space:]]*/, "")
      sub(/[[:space:]]+#.*$/, "")
      gsub(/^[[:space:]]+|[[:space:]]+$/, "")
      if (($0 ~ /^".*"$/) || ($0 ~ /^'\''.*'\''$/)) {
        sub(/^["'\'']/, "")
        sub(/["'\'']$/, "")
      }
      print
      exit
    }
  ' config.yaml)
fi

missing_required=()
if [[ -n "$required_tools" ]]; then
  IFS=: read -r -a required_tool_list <<<"$required_tools"
  for tool in "${required_tool_list[@]}"; do
    [[ -z "$tool" ]] && continue
    if ! command -v "$tool" >/dev/null; then
      missing_required+=("$tool")
    fi
  done
fi

if [[ ${#missing_required[@]} -gt 0 ]]; then
  for tool in "${missing_required[@]}"; do
    echo "✗ missing required tool: $tool"
  done
  fail_message
  exit 1
fi

skip() {
  echo "⊘ skipped: $1 (not installed)"
}

# --- Node ---------------------------------------------------------------
if [[ -f package.json ]]; then
  if command -v node >/dev/null; then
    typecheck_script=0
    for s in lint typecheck test; do
      if node -e "process.exit(require('./package.json').scripts?.['$s'] ? 0 : 1)" 2>/dev/null; then
        run npm run --silent "$s"
        [[ "$s" == typecheck ]] && typecheck_script=1
      fi
    done
    # No typecheck script but a TypeScript project: let the compiler judge.
    if [[ $typecheck_script -eq 0 && -f tsconfig.json ]]; then
      if npx --no-install tsc --version >/dev/null 2>&1; then
        run npx --no-install tsc --noEmit
      else
        skip tsc
      fi
    fi
  else
    skip node
  fi
fi

# --- Python -------------------------------------------------------------
if [[ -f pyproject.toml || -f setup.py || -f requirements.txt ]]; then
  if command -v ruff >/dev/null; then
    run ruff check .
  else
    skip ruff
  fi
  if compgen -G "tests/*" >/dev/null; then
    if command -v pytest >/dev/null; then
      run pytest -q
    else
      skip pytest
    fi
  fi
fi

# --- Shell --------------------------------------------------------------
shell_files=()
while IFS= read -r f; do shell_files+=("$f"); done \
  < <(git ls-files '*.sh' 2>/dev/null)
if [[ ${#shell_files[@]} -gt 0 ]]; then
  if command -v shellcheck >/dev/null; then
    run shellcheck "${shell_files[@]}"
  else
    skip shellcheck
  fi
fi

# --- Rust / Go ----------------------------------------------------------
if [[ -f Cargo.toml ]]; then
  if command -v cargo >/dev/null; then
    run cargo clippy -q -- -D warnings
    run cargo test -q
  else
    skip cargo
  fi
fi
if [[ -f go.mod ]]; then
  if command -v go >/dev/null; then
    run go vet ./...
    run go test ./...
  else
    skip go
  fi
fi

# --- Profile / project extensions ---------------------------------------
for hook in scripts/gate.d/*.sh; do
  [[ -f "$hook" ]] && run bash "$hook"
done

if [[ $fail -eq 0 ]]; then
  echo "GATE: PASS"
else
  fail_message
fi
exit $fail
