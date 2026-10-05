# Host a live draft from the Owner's machine

**Slug:** local-host-live-draft · **Date:** 2026-10-05 · **Status:** implemented

## Goal

Let the Owner run a live multiplayer draft for the Discord league entirely from their own machine: one command starts the app and prints a public HTTPS link to paste into Discord; friends click it and draft in their browser with no setup. Today this needs two dev servers (`dev.sh`) or the Render deploy, and a player who closes their tab mid-draft is permanently locked out. Done = `./host.sh` yields a working shareable link, and a player who loses their tab can get back to their team.

## Approach

**1. Single-origin serving (`server/main.py`).** FastAPI serves the production client build from `client/dist` in addition to the API, so one port carries everything. The client's same-origin fallback in `client/src/api.js` (`VITE_API_URL || ""`) then works through a tunnel — **provided the build sets `VITE_API_URL` to empty**: the tracked `client/.env.production` sets it to the Render placeholder, and Vite only lets a shell variable override it if the variable *exists* (so `unset` is not enough; see §2).
- A module-level `CLIENT_DIST = _REPO_ROOT / "client" / "dist"` (monkeypatchable in tests).
- A catch-all `GET /{full_path:path}` registered **after** every API route and the `/sprites` mount: if `full_path` resolves to an existing file inside `CLIENT_DIST` (resolved path must stay under `CLIENT_DIST` — no traversal), return it via `FileResponse`; otherwise return `CLIENT_DIST/index.html` (SPA fallback so `/lobby/ABCD` and `/draft/ABCD` deep links load). If `index.html` is absent (no build), return 404 with `{"reason": "Client not built — run npm --prefix client run build"}`.
- Paths under the API namespaces (`session`, `sprites`, `health`) never fall back to `index.html`; an unmatched GET there returns 404 JSON (`{"reason": "Not found"}`) so API typos don't masquerade as HTML.
- Dev (`dev.sh` + Vite proxy) and the Render split deploy keep working: the catch-all only answers GETs nothing else matched. Side effect, accepted: a non-GET to an unmatched path now returns 405 instead of 404.

**2. `host.sh` (repo root, sibling of `dev.sh`).** One command for draft night:
- Install client deps if `client/node_modules` is missing (`npm --prefix client ci`), then always run `VITE_API_URL= npm --prefix client run build` — set-but-empty, which overrides `client/.env.production` and yields a same-origin bundle. (`client/.env.production` itself stays untouched; Render still uses it.)
- If `sprites/` is missing or empty, print a warning with the fix (`python3 scripts/fetch_sprites.py`) and continue — sprites are cosmetic.
- Start `uvicorn server.main:app --host 127.0.0.1 --port "$PORT"` (default 8000; no `--reload`), wrapped in `caffeinate -i` when `caffeinate` exists (macOS) so the machine doesn't sleep mid-draft.
- Wait for `/health` to answer before opening the tunnel.
- Tunnel: **one backend, cloudflared quick tunnel** (no account, no admin-console step). `TUNNEL` env var: `cloudflared` (default) | `none`. If `TUNNEL=cloudflared` and `cloudflared` is not on PATH, exit non-zero with `brew install cloudflared`.
  - Run `cloudflared tunnel --url "http://127.0.0.1:$PORT"` in the background with stdout+stderr redirected to a temp log file; poll the log (timeout ~30 s) for the first `https://[a-z0-9-]+\.trycloudflare\.com` URL. On timeout, print the log tail and exit non-zero.
  - Tailscale Funnel (stable URL) is deferred: it needs a one-time tailnet admin step and outlives the script (`--bg`), doubling the hard-to-test surface. Add later if the Owner wants a pinned link.
- Print a clear banner: the share link, the local link (`http://localhost:$PORT`), and the reminder "join first — slot 1 is the host (Start / Undo)".
- `trap` cleanup on EXIT/INT/TERM tears down uvicorn, caffeinate, and cloudflared (all children of the script, so the `dev.sh`-style `kill 0` covers them), guarded so it runs only once, and removes the temp log.
- Must pass `shellcheck` (the gate lints every tracked `*.sh`).

**3. Rejoin after a lost tab (client only).**
- `Lobby.jsx` and `Draft.jsx`: store the team identity in `localStorage` instead of `sessionStorage` (same `draft:<code>:team` key), so closing and reopening the tab — or the browser — restores it. Hoist the duplicated `teamKey` helper into one shared module (e.g. `client/src/identity.js` exporting `teamKey`, `getTeam(code)`, `setTeam(code, name)`), with storage access wrapped in try/catch so a blocked-storage browser degrades to the picker rather than crashing.
- `Draft.jsx`: **always** fetch `getSession(code)` (already returns `slots` and `started`) before connecting the socket, and branch:
  - request fails (404 — room gone, e.g. server restarted): show "Room not found — ask the host for a new link", never "Connecting…".
  - session not started: keep the "Go to lobby" button.
  - stored name present **and** in `slots`: connect as today.
  - no stored name, **or** stored name not in `slots` (stale `localStorage` from an older room with a reused code): clear the stale entry and show a **"Rejoin as…"** picker — one button per slot; clicking stores that name and connects.
  - This keeps a 4403/4404 socket close from ever being reachable from a fresh page load, so `client/src/hooks/useDraftSocket.js` is left unchanged (mid-draft server restarts still fall to its existing "Disconnected" status).
- Trust model is explicit: among friends, anyone with the link can claim any slot. Per-slot tokens are deferred to Unit 2.

**4. Docs.** `README.md` Mode B gains a short "Host it from your machine (`./host.sh`)" subsection: prerequisites (Tailscale with Funnel enabled, or `cloudflared`), the command, `TUNNEL`/`PORT` overrides, what to paste in Discord, and the rejoin behavior. `PLAN.md` gets a decision line: local hosting via `host.sh` is the primary path for live drafts; Render remains as a fallback.

Alternatives considered:
- Serving the client via `StaticFiles(html=True)` mount at `/` — rejected: it doesn't fall back to `index.html` for client routes like `/lobby/ABCD`, and a root mount would shadow later routes.
- Re-allowing `join` after start for a returning name — rejected: server change for no gain over picking an existing slot, and it collides with the duplicate-name check.

## Footprint

Files to modify:
- `server/main.py` — `CLIENT_DIST`, catch-all route
- `server/tests/test_backend.py` (or new `server/tests/test_static.py`) — static/fallback tests
- `client/src/pages/Lobby.jsx`, `client/src/pages/Draft.jsx` — identity storage, rejoin picker
- `client/src/identity.js` — new shared helper
- `host.sh` — new
- `README.md` — hosting subsection
- `PLAN.md` — Objective line (Render → local `host.sh` as main path, Render as fallback), decision line, Now entry

Files NOT to touch:
- `engine/` — no rule changes
- `render.yaml`, `client/vite.config.js`, `client/.env.production`, `dev.sh` — the Render and dev paths must keep working as-is
- `client/src/hooks/useDraftSocket.js`, `client/scripts/e2e-drive.mjs` — not needed; rejoin ACs are manual browser checks
- `server/session_manager.py` — no session semantics change in this unit

## Acceptance criteria

- [ ] With a fake `CLIENT_DIST` (tmp dir with `index.html` + `assets/app.js`), tests assert: `GET /` → index.html; `GET /lobby/ABCD` → index.html (200, HTML); `GET /assets/app.js` → that file; `GET /../server/main.py`-style traversal (e.g. `/assets/..%2F..%2Fsecret`) never returns a file outside `CLIENT_DIST`; `GET /health` → JSON unchanged; catch-all-only API-namespace paths `GET /session/NOPE/bogus`, `GET /health/x`, `GET /sprites` → 404 with JSON content-type and `{"reason": "Not found"}` (not HTML); with no `index.html`, `GET /lobby/ABCD` → 404 with the "Client not built" reason.
- [ ] Existing `server/tests/test_backend.py` tests still pass unchanged (REST + WebSocket routes unaffected by the catch-all).
- [ ] `host.sh` passes `shellcheck`; `TUNNEL=none ./host.sh` builds the client, starts the server, and `curl -s localhost:8000/lobby/ABCD` returns the built `index.html` while `curl -s localhost:8000/health` returns `{"status":"ok"}`; Ctrl-C leaves no uvicorn/caffeinate process behind.
- [ ] After `host.sh` builds, `! grep -rq onrender client/dist/assets` succeeds (bundle is same-origin, not pointed at Render).
- [ ] Owner-run: `./host.sh` (cloudflared installed) prints an `https://*.trycloudflare.com` link, `curl <link>/health` returns ok, and after Ctrl-C no `cloudflared` process remains.
- [ ] `client/src/pages/*.jsx` contain no `sessionStorage` references; `teamKey` is defined once.
- [ ] Manual browser check (against `TUNNEL=none ./host.sh` at `http://localhost:8000`): join two players, start; clear `localStorage` for one, reload `/draft/<code>` → one "Rejoin as" button per slot; clicking one connects as that team and the board loads.
- [ ] Manual: set the stored team for a started room to a name not in its slots, reload → picker (stale entry cleared), not "Connecting…". Open `/draft/NOPE00` → "Room not found", not "Connecting…".
- [ ] Manual: closing and reopening a player's tab mid-draft (same browser) returns them to their team without the picker.
- [ ] `scripts/gate.sh` exits 0.

## Release

Release note: Host a live draft from your own machine with `./host.sh` (one shareable link via a cloudflared quick tunnel), and players who lose their tab can rejoin their team.

## Verification

- `python3 -m pytest -q server/tests`
- `TUNNEL=none ./host.sh` then `curl -s localhost:8000/lobby/ABCD | head -5` and `curl -s localhost:8000/health`
- Owner-run, after `brew install cloudflared`: `./host.sh`, open the printed link from a phone on cellular data, create + join a room.

## Review

Reviewer (plan-reviewer, fresh thread): **REVISE**, 8 findings — all applied:
1. Blocker — tracked `client/.env.production` pins `VITE_API_URL` to Render; `unset` doesn't override it. Build now uses `VITE_API_URL=` (empty) + grep AC. Verified the file is tracked.
2. Stale `localStorage` identity / dead room → endless "Connecting…". Draft page now always fetches the session first and branches; ACs added.
3. Funnel teardown ordering — moot after (7).
4. `/session/NOPE` hits the real route, not the catch-all — AC now uses catch-all-only paths; 405-for-non-GET noted.
5. e2e driver has no rejoin step — rejoin ACs are explicitly manual; driver left out of footprint.
6. Tunnel had no check — Owner-run cloudflared AC added.
7. Two tunnel backends + auto-detect doubles untestable surface — cut to cloudflared + `none`. **Owner note:** this reverses my earlier Funnel suggestion; trade-off is a new random link each draft night vs. a stable one. Funnel can be a later unit.
8. `PLAN.md` Objective contradicts the new decision — Objective edit listed in footprint.

No disagreements.
Plan verdict: REVISE → all findings applied; awaiting Owner approval

Implementation review (3 rounds; record in review-r1.md, deferrals in deferrals.md):
- r1: code-review APPROVE; Codex REQUEST CHANGES — lobby rejoin + `kill 0` + api.trycloudflare.com fixed in followup-1; `/sprites` finding disproven.
- r2: code-review APPROVE; Codex REQUEST CHANGES (re-raised disproven `/sprites`) — Owner chose a third round with the evidence in deferrals.md.
- r3: both APPROVE; MEDIUM port-conflict + LOWs deferred to Unit 2.

Code-review verdict: APPROVE
Codex-review verdict: APPROVE
