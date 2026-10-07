# Harden draft-night hosting

**Slug:** host-hardening · **Date:** 2026-10-06 · **Status:** implemented

## Goal

Close the items deferred from [local-host-live-draft](../local-host-live-draft/deferrals.md) so a live draft doesn't fail confusingly. Five problems, all reproduced on `main` at 593bf8f:

1. With no `sprites/` dir, `GET /sprites/<file>` returns a 500 with a traceback. ARCHI says it should 404.
2. `GET /%00` and `GET /lobby/%00` return 500, because `Path.resolve` raises `ValueError` on a NUL byte in the catch-all.
3. If `$PORT` is already taken (say, a leftover `dev.sh` uvicorn), the other server answers `/health`. `host.sh` then opens a tunnel and prints a share link, and our uvicorn dies on bind. The link points at the wrong server, or at nothing.
4. If the cloudflared process exits mid-draft, `host.sh` keeps serving silently and every remote player is cut off. (Out of scope: a laptop network drop or sleep usually leaves cloudflared alive and reconnecting; that isn't detected.)
5. `Draft.jsx` shows "Room not found — ask the host for a new link" on *any* `getSession` failure, including network errors and tunnel blips. Players then go hunting for a new link instead of retrying.

Done = each of these fails loudly and correctly: 404 JSON for (1) and (2), a refusal to start for (3), a loud warning plus a fresh share link for (4), and a distinct retryable message for (5).

## Approach

**Server (`server/main.py`).**
- Replace the `/sprites` `StaticFiles` mount with a GET route `/sprites/{name:path}` over a new module-level `SPRITES_DIR` (`_REPO_ROOT / "sprites"`), so tests can monkeypatch it.
- Factor the catch-all's traversal-guarded lookup into one helper, `_resolve_inside(root, rel) -> Path | None`. It catches `ValueError`/`OSError` from `resolve()` and returns `None`, and both routes use it.
- A missing file, missing dir, traversal attempt or NUL byte returns `404 {"reason": "Not found"}`.
- The catch-all's existing behaviour is otherwise unchanged, including bare `/sprites` → 404 JSON.
- Alternative considered: keep `StaticFiles` and wrap it to catch `RuntimeError`. That fixes (1) but not (2), and keeps two lookup paths.

**`host.sh`.** The machine's `bash` is 3.2, so there is no `wait -n`. The fix must stay shellcheck-clean.
- *Port check:* first thing after the `TUNNEL` check, before `npm ci`/build, probe `127.0.0.1:$PORT`. If anything accepts the connection (`curl` exit ≠ 7, connection refused; capture with `|| rc=$?` under `set -e`), exit 1 with `Port $PORT is in use — stop the other server or run PORT=<n> ./host.sh`. No post-health `kill -0` backstop: a squatter answers the first health curl before our uvicorn fails to bind, so it would catch nothing.
- *Tunnel watch:* move tunnel start + link scrape into a function, `start_tunnel`, with the same 30 s timeout and the `api.trycloudflare.com` filter. Its contract:
  - It is called in the current shell (`if start_tunnel; then …`), never as `$(start_tunnel)`, because it sets the globals `tunnel_pid`, `tunnel_log` and `share_link`.
  - On failure it returns 1 and never exits. The first-link caller turns that into today's `exit 1` with the log tail. A bare call under `set -e` would kill the draft.
  - On failure it kills that attempt's cloudflared if it's still alive (alive with no link is never retried otherwise) and resets `tunnel_pid`.
  - Each attempt gets a fresh `mktemp` log and removes the previous one, so the scrape never returns a stale link. Cleanup removes whichever log is current. Replace the final `wait "$server_pid"` with a poll loop that runs every ~2 s while the server is alive. If the tunnel PID is dead, print a loud multi-line warning (`TUNNEL DOWN — players are disconnected`) and call `start_tunnel` again. On success, print `New share link: …` and tell the host to repost it in Discord. Rooms are in memory and the server keeps running, so the draft survives; only the URL changes. That makes it a new origin, so players' stored team is gone and they land on the existing **Rejoin as…** picker. If the restart fails, warn and retry on the next tick, at most once per 30 s, and keep serving locally.
- When the server dies, the loop exits with the server's status, and cleanup runs as today.
- The cleanup trap must still stop whichever cloudflared PID is current.

**Client.**
- `api.js` `request()` attaches `status` to the thrown error (`err.status = resp.status`). Network failures stay the native `TypeError` with no `status`.
- `Draft.jsx` treats only `err.status === 404` as "Room not found". Any other failure shows "Can't reach the draft server — check your connection, or ask the host for a new link" with a **Retry** button. Retry bumps a retry counter that is added to the fetch effect's dependencies (today `[code]`). The "new link" wording covers players stuck on a dead tunnel hostname, where Retry can never succeed.
- Alternative considered: auto-retry with backoff. Retry is simpler and the player stays in control; `useDraftSocket` already auto-reconnects once a room is loaded.

**Docs.** ARCHI: drop the "sprite file requests then 500 (deferred fix…)" clause, describe `/sprites` as a guarded file route, and mention the port check and tunnel restart in the `./host.sh` entry point. README: one line under the `./host.sh` subsection saying a dropped tunnel is restarted automatically, the new link must be reposted, and players pick their team again from **Rejoin as…**.

## Footprint

Files to modify:
- server/main.py — `SPRITES_DIR`, `_resolve_inside` helper, `/sprites/{name:path}` route (replacing the mount), catch-all uses the helper
- server/tests/test_static.py — new tests: missing sprites dir → 404 JSON (including `/sprites/` and `/sprites/%00`); sprite served from a monkeypatched `SPRITES_DIR`; sprite traversal → 404; `/%00` and `/lobby/%00` → 404 JSON
- host.sh — port pre-check, post-health liveness check, `start_tunnel` function, watch loop
- client/src/api.js — `status` on thrown errors
- client/src/pages/Draft.jsx — 404 vs unreachable branches, Retry
- ARCHI.md — sprites line + host.sh entry point
- README.md — one line in the `./host.sh` subsection

Files NOT to touch:
- engine/, server/session_manager.py, client/src/hooks/useDraftSocket.js, client/.env.production, client/vite.config.js, render.yaml, dev.sh — out of scope; the Vite proxy still forwards `/sprites` unchanged.

## Acceptance criteria

- [ ] With `SPRITES_DIR` pointing at a nonexistent dir, `GET /sprites/pikachu.png`, `/sprites/` and `/sprites/%00` → 404, `application/json`, `{"reason": "Not found"}` (test).
- [ ] With `SPRITES_DIR` containing `a.png`, `GET /sprites/a.png` → 200 with the file bytes; `GET /sprites/..%2Fsecret` → 404 and never the secret's contents (test).
- [ ] `GET /%00` and `GET /lobby/%00` → 404 JSON, not 500 (test, `raise_server_exceptions=False`).
- [ ] The existing test functions in `server/tests/test_static.py` and `server/tests/test_backend.py` are unchanged and pass.
- [ ] `grep -n StaticFiles server/main.py` returns nothing.
- [ ] With a listener on the port (`python3 -m http.server 8765 --bind 127.0.0.1 &`), `PORT=8765 TUNNEL=none ./host.sh` exits non-zero within ~2 s without running the client build, prints the "Port 8765 is in use" message, and leaves no uvicorn/caffeinate process behind.
- [ ] `TUNNEL=none ./host.sh` still starts, prints the banner, and stops cleanly on SIGINT/SIGTERM with no leftover processes (same as v2026.10.1).
- [ ] Diff inspection: `host.sh` has a `start_tunnel` function used both for the first link and for restarts, is called only as `if start_tunnel` (never inside `$(…)`), returns rather than exits on failure, kills a failed live attempt, uses a fresh log per attempt; a poll loop replaces `wait "$server_pid"`; no `wait -n`; cleanup kills the *current* tunnel PID and removes the current log.
- [ ] Tunnel restart, verified with a stub. The fake `cloudflared` lives in a scratch temp dir (never the repo) that is put first on `PATH`. It ignores its `tunnel --url …` args and keeps a counter file in that temp dir. Run 1 prints `https://test-1.trycloudflare.com` and exits after ~3 s; run 2 prints `https://test-2.trycloudflare.com` and stays up. Start `PORT=8766 ./host.sh` in the background with output to a file, then wait for `New share link: https://test-2`. Pass: the output shows `Share link: https://test-1…`, then `TUNNEL DOWN`, then `New share link: https://test-2…`; `curl -fsS 127.0.0.1:8766/health` succeeds; after SIGTERM to host.sh, `pgrep -fl 'uvicorn server.main|cloudflared|caffeinate -i uvicorn'` is empty.
- [ ] Failed restart, verified with a stub variant whose run 2+ stays alive but never prints a link. Pass: `TUNNEL DOWN` repeats roughly every 30 s, `/health` keeps answering, at most one stub process runs at any time, and after SIGTERM `pgrep` is empty.
- [ ] Diff inspection: in `Draft.jsx`, only `err.status === 404` leads to "Room not found…"; any other rejection shows "Can't reach the draft server…" with a Retry button wired through a retry counter in the fetch effect's dependencies.
- [ ] Manual: under `./dev.sh`, create a room, kill the uvicorn backend, and open `/draft/<CODE>` on :5173. Expect "Can't reach the draft server…" and Retry. Restart the backend and click Retry: the page refetches and shows "Room not found…", because the room was lost with the restart.
- [ ] ARCHI.md no longer says sprite requests 500, and the `./host.sh` entry mentions the port check and tunnel restart.
- [ ] `scripts/gate.sh` passes (ruff, shellcheck on `host.sh`, client build, pytest).

## Release

Release note: Draft night is sturdier — missing sprites and `%00` URLs return 404 instead of crashing, `host.sh` refuses a busy port and restarts a dropped tunnel with a fresh link, and players see "can't reach server" with Retry instead of a false "room not found".

## Verification

- `python3 -m pytest server/tests/test_static.py -q`
- The `host.sh` scenarios above (busy port; the two stub-cloudflared runs); afterwards `pgrep -fl 'uvicorn server.main|cloudflared|caffeinate -i uvicorn'` prints nothing.

## Review

Round 1 (fresh plan reviewer, 2026-10-06): REVISE, 6 findings. All were applied:
1. `start_tunnel` contract: current-shell call, return not exit, kill a failed live attempt, fresh log per attempt. Added a failed-restart stub criterion.
2. Dropped the `kill -0` post-health backstop (it can't catch a squatter) and moved the port check before the build.
3. Replaced the impossible "server stopped" Draft check with the dev.sh backend-kill check, and specified the Retry counter.
4. Stated that network drop or sleep with cloudflared still alive is out of scope; a restart lands players on Rejoin as… (README); "Can't reach" wording points stale-link players to the host.
5. Made the stub test reproducible (counter file, args ignored, scratch dir, explicit sequence).
6. Added `/sprites/` and `/sprites/%00` tests, and reworded the "unchanged" criterion.

No disagreements.
Plan verdict: REVISE (round 1); all findings applied, no second review round run

Code review: round 1 Codex REQUEST CHANGES (PLAN.md bookkeeping commit; reverted, orchestrator-side); round 2 both APPROVE. One MEDIUM deferred: [deferrals.md](deferrals.md).
Code-review verdict: APPROVE
Codex-review verdict: APPROVE
