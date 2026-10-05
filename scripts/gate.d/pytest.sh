#!/usr/bin/env bash
# gate.sh only runs pytest for a top-level tests/; this repo's tests live in
# engine/tests, server/tests, and scripts/test_*.py.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)" || exit 1
python3 -m pytest -q  # -m puts the repo root on sys.path for `import engine`
