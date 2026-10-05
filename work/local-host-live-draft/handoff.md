You are the implementer for this work unit. Read AGENTS.md in the repo root first — it is your contract.
Follow its build-discipline section while staying inside the plan footprint.

Work unit: work/local-host-live-draft/plan.md  (read it in full; it is your source of truth)
Branch: wt/local-host-live-draft (already checked out in this worktree — verify with `git branch --show-current` before changing anything)

Footprint (from the plan, repeated here as the hard boundary):
- server/main.py — module-level `CLIENT_DIST`, catch-all GET route registered after every other route (after `/health`)
- server/tests/test_backend.py or a new server/tests/test_static.py — static/fallback tests using a monkeypatched tmp `CLIENT_DIST`
- client/src/identity.js — new: `teamKey`, `getTeam(code)`, `setTeam(code, name)`, `clearTeam(code)` over localStorage, try/catch-wrapped
- client/src/pages/Lobby.jsx, client/src/pages/Draft.jsx — use identity.js (no `sessionStorage`); Draft.jsx always fetches `getSession(code)` first and branches per plan §3 (room not found / not started / connect / "Rejoin as…" picker, clearing stale names)
- host.sh — new, repo root, executable (`chmod +x`), `#!/usr/bin/env bash`, `set -euo pipefail`
- README.md — "Host it from your machine (`./host.sh`)" subsection under Mode B
- PLAN.md — Objective line (local `host.sh` is the main path for live drafts, Render the fallback) and one Decisions line dated 2026-10-05 linking work/local-host-live-draft/plan.md. Leave the existing "Now" entry for this unit as it is.

Key constraints:
- Do NOT touch: engine/, render.yaml, client/vite.config.js, client/.env.production, dev.sh, server/session_manager.py, client/src/hooks/useDraftSocket.js, client/scripts/e2e-drive.mjs. If you believe one must change, stop and report it instead.
- `client/.env.production` (tracked) sets VITE_API_URL to a Render placeholder. host.sh must build with `VITE_API_URL= npm --prefix client run build` (set-but-empty) — `unset` is NOT enough. After building, verify `! grep -rq onrender client/dist/assets`.
- Catch-all: serve a real file only if its resolved path stays inside CLIENT_DIST (no traversal); paths whose first segment is `session`, `sprites` or `health` return 404 JSON `{"reason": "Not found"}`, never index.html; missing index.html → 404 JSON with reason "Client not built — run npm --prefix client run build". Existing routes and tests must behave identically.
- host.sh tunnel: `TUNNEL` = `cloudflared` (default) | `none`; no Tailscale/Funnel. cloudflared runs in the background with output redirected to a temp log; poll (~30 s timeout) for the first `https://…trycloudflare.com` URL. Missing cloudflared with TUNNEL=cloudflared → exit non-zero with a `brew install cloudflared` hint. uvicorn binds 127.0.0.1:$PORT (default 8000), no --reload, under `caffeinate -i` when available; wait for /health before opening the tunnel. Cleanup trap on EXIT/INT/TERM runs once, kills children (`kill 0` pattern like dev.sh), removes the temp log. Sprites missing/empty → warning with `python3 scripts/fetch_sprites.py`, continue. Banner prints share link, local link, and "join first — slot 1 is the host (Start / Undo)".
- Must pass shellcheck (gate lints every tracked *.sh — so `git add host.sh` before running the gate).
- Run Python tests as `python3 -m pytest`. Match surrounding code style; keep comments sparse like the existing files.
- Do not run host.sh with a real tunnel. You may run `TUNNEL=none ./host.sh` briefly to self-check, then stop it and make sure no uvicorn process from it is left running.

When done:
1. Run scripts/gate.sh from the repo root — it must pass.
2. Commit your work on this branch with a clear message.
3. Print a final summary: what changed and why, criteria partially met (if any), out-of-scope observations.
