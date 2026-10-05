#!/usr/bin/env bash
# Opt-in notebook cleanliness gate. Copy to scripts/gate.d/nb-clean.sh to enable.
set -uo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1

notebook_has_outputs_or_counts() {
  local notebook="$1"

  awk '
    /"execution_count"[[:space:]]*:[[:space:]]*[0-9]+/ { dirty = 1 }

    {
      line = $0
      while (match(line, /"outputs"[[:space:]]*:[[:space:]]*\[/)) {
        line = substr(line, RSTART + RLENGTH)
        if (line ~ /^[[:space:]]*\]/) {
          continue
        }
        if (line ~ /[^[:space:]]/) {
          dirty = 1
        } else {
          in_outputs = 1
        }
        break
      }
      if (in_outputs && line !~ /"outputs"[[:space:]]*:[[:space:]]*\[/) {
        if (line ~ /^[[:space:]]*\]/) {
          in_outputs = 0
        } else if (line ~ /[^[:space:]]/) {
          dirty = 1
        }
      }
    }

    END { exit dirty ? 0 : 1 }
  ' "$notebook"
}

dirty=()
while IFS= read -r notebook; do
  if notebook_has_outputs_or_counts "$notebook"; then
    dirty+=("$notebook")
  fi
done < <(git ls-files '*.ipynb')

if [[ ${#dirty[@]} -eq 0 ]]; then
  exit 0
fi

echo "Tracked notebooks must not contain outputs or execution counts:"
printf '  %s\n' "${dirty[@]}"
echo
echo "Fix with one of:"
echo "  nbstripout --install"
echo "  jupyter nbconvert --clear-output --inplace <notebook.ipynb>"
exit 1
