You are the implementer for this work unit. Read AGENTS.md in the repo root first — it is your contract.
Follow its build-discipline section while staying inside the plan footprint.

Work unit: work/host-hardening/plan.md  (read it in full; it is your source of truth)
Branch: wt/host-hardening (already checked out in this worktree — verify with `git branch --show-current` before changing anything)

Footprint (from the plan, repeated here as the hard boundary):
- server/main.py — module-level `SPRITES_DIR`, a `_resolve_inside(root, rel) -> Path | None` helper (catches ValueError/OSError from resolve; rejects paths outside root), a GET `/sprites/{name:path}` route replacing the `StaticFiles` mount, and the catch-all using the same helper
- server/tests/test_static.py — add new test functions only; leave the existing ones as they are
- host.sh — port pre-check, `start_tunnel` function, watch loop
- client/src/api.js — attach `status` to errors thrown for non-OK responses
- client/src/pages/Draft.jsx — 404 vs unreachable branches, Retry via a retry counter in the fetch effect's dependencies
- ARCHI.md — the `sprites/` line (drop the "then 500 (deferred fix…)" clause; describe the guarded `/sprites` route) and the `./host.sh` entry point (port check, tunnel restart)
- README.md — one line in the `./host.sh` subsection: a dropped tunnel restarts automatically, repost the new link, players re-pick their team from "Rejoin as…"

Key constraints:
- Do NOT touch: engine/, server/session_manager.py, client/src/hooks/useDraftSocket.js, client/.env.production, client/vite.config.js, render.yaml, dev.sh, scripts/. If you believe one must change, stop and report it instead.
- Server: missing file, missing dir, traversal, empty name (`/sprites/`) and NUL byte all return 404 `{"reason": "Not found"}` (application/json). Bare `/sprites` still hits the catch-all → 404 JSON. Afterwards `grep -n StaticFiles server/main.py` must print nothing. Existing routes and existing tests behave identically.
- host.sh must stay bash 3.2 compatible (macOS /usr/bin/env bash is 3.2.57): no `wait -n`, no associative arrays, no `${var,,}`. It must pass shellcheck; the gate lints every tracked *.sh.
- Port pre-check runs right after the TUNNEL validation, BEFORE `npm ci` / the client build: `curl` to 127.0.0.1:$PORT; exit code 7 (connection refused) means free; anything else → exit 1 with `Port $PORT is in use — stop the other server or run PORT=<n> ./host.sh`. Capture the curl status with `|| rc=$?` under `set -e`. No post-/health `kill -0` backstop.
- `start_tunnel` contract (all four are required):
  (a) called in the current shell as `if start_tunnel; then …` — never inside `$(…)` — because it sets the globals `tunnel_pid`, `tunnel_log`, `share_link`;
  (b) on failure it `return 1`s, never exits; the first-link caller converts that to today's behavior (print the log tail, exit 1);
  (c) on failure it kills that attempt's cloudflared if it is still alive (use stop_process_tree) and clears `tunnel_pid`;
  (d) each attempt uses a fresh `mktemp` log and removes the previous one; cleanup kills the current `tunnel_pid` and removes the current `tunnel_log`.
  Keep the 30 s timeout and the `api.trycloudflare.com` exclusion.
- Watch loop replaces `wait "$server_pid"`: every ~2 s while `kill -0 "$server_pid"` succeeds; if TUNNEL=cloudflared and the tunnel PID is dead, print a loud multi-line warning containing `TUNNEL DOWN — players are disconnected`, then try `start_tunnel` again (at most one attempt per 30 s). On success, print `New share link: <url>` plus a line telling the host to repost it in Discord. On failure, keep serving and retry on a later tick. When the server dies, exit with the server's status (`wait "$server_pid"` to collect it) so cleanup runs as today. Ctrl-C / SIGTERM must still leave no uvicorn, caffeinate or cloudflared process behind.
- Client: only `err.status === 404` shows "Room not found — ask the host for a new link". Every other failure shows "Can't reach the draft server — check your connection, or ask the host for a new link" plus a Retry button that increments a counter in the fetch effect's dependency list. Match the existing Centered/text-muted styling.
- Run Python tests as `python3 -m pytest`. Match surrounding code style; keep comments sparse like the existing files.
- Do NOT run host.sh with a real tunnel. Self-check with the plan's scenarios instead, run from a scratch temp dir (never add stub files to the repo): (1) a busy port: `python3 -m http.server 8765 --bind 127.0.0.1 &` then `PORT=8765 TUNNEL=none ./host.sh` → fast non-zero exit; (2) a fake `cloudflared` first on PATH that ignores its args and uses a counter file in its temp dir: run 1 prints `https://test-1.trycloudflare.com` and exits after ~3 s; run 2 prints `https://test-2.trycloudflare.com` and stays up. Start `PORT=8766 ./host.sh` in the background with output to a file, wait for `New share link: https://test-2`, check `curl -fsS 127.0.0.1:8766/health`, send SIGTERM, then confirm `pgrep -fl 'uvicorn server.main|cloudflared|caffeinate -i uvicorn'` is empty. (3) A variant whose run 2+ stays alive but never prints a link: `TUNNEL DOWN` should repeat about every 30 s and at most one stub should run at a time. Kill every helper process you start (http.server, stubs, host.sh) before you finish.

When done:
1. Run scripts/gate.sh from the repo root — it must pass.
2. Commit your work on this branch with a clear message.
3. Print a final summary: what changed and why, the result of each self-check scenario, criteria partially met (if any), out-of-scope observations.
