#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
TUNNEL="${TUNNEL:-cloudflared}"

case "$TUNNEL" in
  cloudflared)
    if ! command -v cloudflared >/dev/null; then
      echo "cloudflared is required. Install it with: brew install cloudflared" >&2
      exit 1
    fi
    ;;
  none) ;;
  *) echo "TUNNEL must be cloudflared or none" >&2; exit 1 ;;
esac

cleaned=0
tunnel_log=""
cleanup() {
  if (( cleaned )); then return; fi
  cleaned=1
  trap - EXIT INT TERM
  trap '' TERM
  kill 0 2>/dev/null || true
  if [[ -n "$tunnel_log" ]]; then rm -f "$tunnel_log"; fi
}
trap cleanup EXIT INT TERM

if [[ ! -d client/node_modules ]]; then npm --prefix client ci; fi
# shellcheck disable=SC1007
VITE_API_URL= npm --prefix client run build
if grep -rq onrender client/dist/assets; then
  echo "Build still contains a Render URL" >&2
  exit 1
fi

if [[ ! -d sprites ]] || [[ -z "$(ls -A sprites)" ]]; then
  echo "Warning: sprites missing. Run python3 scripts/fetch_sprites.py to add them." >&2
fi

if command -v caffeinate >/dev/null; then
  caffeinate -i uvicorn server.main:app --host 127.0.0.1 --port "$PORT" &
else
  uvicorn server.main:app --host 127.0.0.1 --port "$PORT" &
fi
server_pid=$!

ready=0
for ((i = 0; i < 30; i++)); do
  if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then break; fi
  sleep 1
done
if (( ! ready )); then
  echo "Server did not become healthy on port $PORT" >&2
  exit 1
fi

share_link="http://localhost:$PORT"
if [[ "$TUNNEL" == cloudflared ]]; then
  tunnel_log=$(mktemp)
  cloudflared tunnel --url "http://127.0.0.1:$PORT" >"$tunnel_log" 2>&1 &
  tunnel_pid=$!
  share_link=""
  for ((i = 0; i < 30; i++)); do
    share_link=$(grep -Eom1 'https://[a-z0-9-]+\.trycloudflare\.com' "$tunnel_log" || true)
    if [[ -n "$share_link" ]]; then break; fi
    if ! kill -0 "$tunnel_pid" 2>/dev/null; then break; fi
    sleep 1
  done
  if [[ -z "$share_link" ]]; then
    echo "cloudflared did not provide a share link:" >&2
    tail -n 20 "$tunnel_log" >&2
    exit 1
  fi
fi

echo "Share link: $share_link"
echo "Local link: http://localhost:$PORT"
echo "join first — slot 1 is the host (Start / Undo)"
wait "$server_pid"
