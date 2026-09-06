#!/usr/bin/env bash
# One command to run the multiplayer draft locally: starts the FastAPI backend
# and the Vite dev server together, and shuts both down on Ctrl-C.
set -euo pipefail
cd "$(dirname "$0")"

BACKEND_PORT="${BACKEND_PORT:-8000}"

# Install client deps on first run.
[ -d client/node_modules ] || (cd client && npm install)

# Kill both child processes when this script exits.
trap 'kill 0' EXIT

uvicorn server.main:app --reload --port "$BACKEND_PORT" &
(cd client && npm run dev) &
wait
