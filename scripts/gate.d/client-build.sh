#!/usr/bin/env bash
# The React client lives in client/, so gate.sh's root package.json detection
# misses it. It has no lint/test scripts; a production build is the check.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)/client" || exit 1
if [[ ! -d node_modules ]]; then
  npm ci --silent || exit 1
fi
npm run --silent build
