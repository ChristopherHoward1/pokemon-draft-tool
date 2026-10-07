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

rc=0
curl -fsS --connect-timeout 1 --max-time 2 "http://127.0.0.1:$PORT/" >/dev/null 2>&1 || rc=$?
if (( rc != 7 )); then
  echo "Port $PORT is in use — stop the other server or run PORT=<n> ./host.sh" >&2
  exit 1
fi

cleaned=0
tunnel_log=""
server_pid=""
tunnel_pid=""
stop_process_tree() {
  local pid="$1" child
  while IFS= read -r child; do
    stop_process_tree "$child"
  done < <(pgrep -P "$pid" 2>/dev/null || true)
  kill "$pid" 2>/dev/null || true
}
start_tunnel() {
  if [[ -n "$tunnel_log" ]]; then rm -f "$tunnel_log"; fi
  tunnel_pid=""
  tunnel_log=$(mktemp) || return 1
  share_link=""
  cloudflared tunnel --url "http://127.0.0.1:$PORT" >"$tunnel_log" 2>&1 &
  tunnel_pid=$!
  for ((i = 0; i < 30; i++)); do
    share_link=$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$tunnel_log" | grep -v '^https://api\.trycloudflare\.com$' | head -n 1 || true)
    if [[ -n "$share_link" ]]; then return 0; fi
    if ! kill -0 "$tunnel_pid" 2>/dev/null; then break; fi
    sleep 1
  done
  if kill -0 "$tunnel_pid" 2>/dev/null; then stop_process_tree "$tunnel_pid"; fi
  wait "$tunnel_pid" 2>/dev/null || true
  tunnel_pid=""
  return 1
}
cleanup() {
  if (( cleaned )); then return; fi
  cleaned=1
  trap - EXIT INT TERM
  if [[ -n "$tunnel_pid" ]]; then stop_process_tree "$tunnel_pid"; fi
  if [[ -n "$server_pid" ]]; then stop_process_tree "$server_pid"; fi
  if [[ -n "$tunnel_pid" ]]; then wait "$tunnel_pid" 2>/dev/null || true; fi
  if [[ -n "$server_pid" ]]; then wait "$server_pid" 2>/dev/null || true; fi
  if [[ -n "$tunnel_log" ]]; then rm -f "$tunnel_log"; fi
}
trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

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
  if ! start_tunnel; then
    echo "cloudflared did not provide a share link:" >&2
    tail -n 20 "$tunnel_log" >&2
    exit 1
  fi
fi

echo "Share link: $share_link"
echo "Local link: http://localhost:$PORT"
echo "join first — slot 1 is the host (Start / Undo)"
last_tunnel_attempt=$((SECONDS - 30))
while kill -0 "$server_pid" 2>/dev/null; do
  if [[ "$TUNNEL" == cloudflared ]] && ! kill -0 "$tunnel_pid" 2>/dev/null; then
    if (( SECONDS - last_tunnel_attempt >= 30 )); then
      echo ""
      echo "TUNNEL DOWN — players are disconnected" >&2
      echo "The local draft is still running. Attempting a new share link…" >&2
      last_tunnel_attempt=$SECONDS
      if start_tunnel; then
        echo "New share link: $share_link"
        echo "Repost the new share link in Discord so players can rejoin."
      else
        echo "Tunnel restart failed; the draft remains available locally. Retrying soon." >&2
      fi
    fi
  fi
  sleep 2
done
wait "$server_pid"
