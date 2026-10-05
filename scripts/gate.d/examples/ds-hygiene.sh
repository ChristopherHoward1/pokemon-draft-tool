#!/usr/bin/env bash
# Opt-in data-science repo hygiene gate. Copy to scripts/gate.d/ds-hygiene.sh to enable.
set -uo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1

: "${DS_DATA_MAX_BYTES=1048576}"
: "${DS_DATA_ALLOW_DIRS=tests/fixtures}"
: "${DS_PATH_SCAN=1}"

file_size_bytes() {
  local path="$1"

  stat -c %s "$path" 2>/dev/null || stat -f %z "$path"
}

is_data_artifact() {
  local path="$1"

  case "$path" in
    *.csv|*.tsv|*.parquet|*.pkl|*.pickle|*.h5|*.hdf5|*.onnx|*.joblib|*.npy|*.npz) return 0 ;;
    *) return 1 ;;
  esac
}

is_allowed_data_path() {
  local path="$1"
  local prefix
  local -a prefixes

  [[ -z "$DS_DATA_ALLOW_DIRS" ]] && return 1

  IFS=: read -r -a prefixes <<<"$DS_DATA_ALLOW_DIRS"
  for prefix in "${prefixes[@]}"; do
    [[ -z "$prefix" ]] && continue
    case "$path" in
      "$prefix"*) return 0 ;;
    esac
  done
  return 1
}

check_data_artifacts() {
  local path
  local size
  local found=0

  [[ -z "$DS_DATA_MAX_BYTES" ]] && return 0

  while IFS= read -r path; do
    [[ -f "$path" ]] || continue
    is_data_artifact "$path" || continue
    is_allowed_data_path "$path" && continue

    size=$(file_size_bytes "$path")
    if [[ "$size" -gt "$DS_DATA_MAX_BYTES" ]]; then
      printf 'Tracked data/model artifact exceeds DS_DATA_MAX_BYTES (%s bytes): %s (%s bytes)\n' \
        "$DS_DATA_MAX_BYTES" "$path" "$size" >&2
      found=1
    fi
  done < <(git ls-files)

  return "$found"
}

check_local_paths() {
  local path
  local found=0

  [[ -z "$DS_PATH_SCAN" ]] && return 0

  while IFS= read -r path; do
    [[ -f "$path" ]] || continue
    if grep -Eq '(/Users/|/home/|C:\\)' "$path"; then
      printf 'Tracked code/notebook contains a hardcoded local path: %s\n' "$path" >&2
      found=1
    fi
  done < <(git ls-files '*.py' '*.ipynb')

  return "$found"
}

fail=0
check_data_artifacts || fail=1
check_local_paths || fail=1
exit "$fail"
