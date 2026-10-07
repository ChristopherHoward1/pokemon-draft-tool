# Polish draft-night hosting edges

**Slug:** host-polish · **Date:** 2026-10-07 · **Status:** implemented

## Goal

Close the LOW, no-action items from [host-hardening/deferrals.md](../host-hardening/deferrals.md). None has hurt a real draft, but each one misleads the host, hides a failure, or adds noise. All were checked against `main` at f7e1319:

1. **Missing curl or a bad `PORT`.** If `curl` is missing, or `PORT` isn't a number (`PORT=abc`), the pre-check's `curl` exits with something other than 7, so `host.sh` prints "Port … is in use".
2. **Orphaned tunnel.** A signal that arrives between `cloudflared … &` and `tunnel_pid=$!` (`host.sh:42–43`) runs cleanup while `tunnel_pid` is still empty, so that cloudflared outlives the script.
3. **Missed server death.** A failed tunnel restart spends up to 30 s in `start_tunnel`'s scrape loop, which never checks whether the server is still alive.
4. **Shutdown noise.** Ctrl-C or SIGTERM prints bash's job notice (`Terminated: 15 …`) for the processes cleanup kills.
5. **HEAD returns 405.** `HEAD /sprites/<file>` returns 405, and so does HEAD on the client catch-all (`/`, `/assets/…`), because both are GET-only routes.
6. **Port grabbed during the build.** The port check runs before `npm ci` and the build, which can take tens of seconds. If another copy of this app grabs the port in that window, it answers our `/health`, and `host.sh` prints a share link to the wrong server.

Not fixed (won't-fix, confirmed by the Owner): the deferral about `kill -0` hitting a reused PID. See Review, finding 8.

Done = each fixed item has a criterion below that shows it, and nothing changes on draft night when nothing goes wrong.

## Approach

**`host.sh`** (bash 3.2, no `wait -n`; must stay shellcheck-clean)

- **(1) Validate curl and `PORT`** before the port probe:
  - Missing curl → print `curl is required`, exit 1.
  - `PORT` must match `^[1-9][0-9]*$` and be ≤ 65535, compared as `10#$PORT`. Leading zeros are rejected, so `0080` never reaches arithmetic. Otherwise print `PORT must be a number from 1 to 65535` and exit 1.
  - Exit-code handling is unchanged: 7 (connection refused) means free, anything else means in use.
- **(6) Re-check the port after the build.** Factor the probe into `check_port_free`. Call it at the top (fail fast, before the build) and again immediately before launching uvicorn. That cuts the race window from the build time to about a second of uvicorn startup. It doesn't close it.
  - Alternative considered: a per-run token in `/health`. Rejected: it changes an API for a low-value race.
- **(2) Sweep children on cleanup.** After stopping the tracked PIDs, cleanup also stops every remaining direct child of the script with `stop_process_tree`, so an untracked cloudflared can't survive.
  - Collect the list exactly as `kids=$(pgrep -P $$)`. Bash then execs pgrep directly and pgrep excludes itself, so the list holds only real children.
  - Don't use a pipeline (`pgrep … | …`). The other pipeline stage is also a child and would be swept.
- **(3) Watch the server during the scrape.** `start_tunnel`'s scrape loop also stops when `kill -0 "$server_pid"` fails, then returns 1 (killing that attempt, as today). The watch loop then sees the dead server and exits with its status.
  - On the *initial* `start_tunnel`, if the server is dead, print `Server stopped before the tunnel was ready` instead of the "cloudflared did not provide a share link" message and log tail.
- **(4) Silence shutdown.** Wrap the body of `cleanup` (after the `cleaned` guard and `trap -` line) in `{ …; } 2>/dev/null`.
  - Bash 3.2 prints the job notice at whichever command runs after a child dies. The existing `wait … 2>/dev/null` lines don't help, because other commands run first.
  - Don't use `disown`: it breaks the final `wait "$server_pid"` and changes the server-death exit status.
  - Don't change the exit status `host.sh` returns when the server dies.

**`server/main.py` (5).**
- Register `/sprites/{name:path}`, the `/{full_path:path}` catch-all and `/health` for both GET and HEAD, via `@app.api_route(..., methods=["GET", "HEAD"])`. `FileResponse` already omits the body for HEAD.
- `/health` has to be included. Once the catch-all accepts HEAD, a HEAD to a GET-only route falls through to the catch-all's reserved-prefix 404 instead of 405.
- With that, `HEAD /session/<id>` and other `session/…` paths return 404 JSON instead of 405. That's intended: nothing uses HEAD on the API.

**Docs.**
- ARCHI: in the `./host.sh` entry point, add "re-checks the port before launch". In the `server/` line, say the static routes and `/health` accept HEAD.
- README, `./host.sh` subsection:
  - Add `curl` to the install line, next to `cloudflared`.
  - After the `PORT=8001` sentence, add one line: `host.sh` refuses to start if `PORT` isn't a valid port number or the port is already in use, and Ctrl-C stops the server and tunnel it started.

## Footprint

Files to modify:
- host.sh: curl/PORT validation, `check_port_free` called twice, cleanup sweeps direct children and runs silenced, scrape loop watches the server
- server/main.py: GET+HEAD on `/sprites/…`, the catch-all and `/health`
- server/tests/test_static.py: HEAD tests
- ARCHI.md: the `./host.sh` entry point and the `server/` line
- README.md: `./host.sh` subsection (curl prerequisite, refusal/shutdown line)

Files NOT to touch:
- engine/, client/, server/session_manager.py, dev.sh, render.yaml, scripts/: out of scope.

## Acceptance criteria

Test harness notes:
- Stub runs put a fake `cloudflared` in a scratch dir `$STUB` first on `PATH`. Every `pgrep` check matches `"$STUB/cloudflared|uvicorn server.main|caffeinate -i uvicorn"`, never bare `cloudflared`, so a real cloudflared on the machine doesn't interfere.
- SIGINT checks start `host.sh` from a harness with job control on (`set -m`) or under a pty (`script -q /dev/null …`). Without that, a background job inherits SIGINT as ignored and its trap never fires.

Criteria:
- [ ] `PORT=abc`, `PORT=70000` and `PORT=0080` (each with `TUNNEL=none ./host.sh`) exit non-zero within ~1 s, print `PORT must be a number from 1 to 65535`, and do not print "in use".
- [ ] With curl missing from `PATH`, `TUNNEL=none ./host.sh` exits non-zero and prints `curl is required`. Set up `PATH` as a scratch dir with symlinks to bash, env, dirname and mkdir, but not curl.
- [ ] Regression: with a listener on the port (`python3 -m http.server 8765 --bind 127.0.0.1 &`), `PORT=8765 TUNNEL=none ./host.sh` still exits non-zero within ~2 s, prints the "Port 8765 is in use" message, and doesn't build.
- [ ] Diff inspection: `check_port_free` is called both before the client build and immediately before the uvicorn launch, with nothing slow in between.
- [ ] Diff inspection: cleanup stops the tracked PIDs, then the children in `kids=$(pgrep -P $$)` (that exact non-pipeline form). The cleanup body is wrapped in `{ …; } 2>/dev/null`. No `disown`.
- [ ] Orphan check, run once by the implementer:
  - In a stubbed run (stub prints `https://test-1.trycloudflare.com`, then sleeps), simulate the race with a temporary edit that leaves `tunnel_pid` empty. The edit must not be in the final diff.
  - Send SIGTERM to `host.sh`; the `pgrep` check is then empty.
  - Paste the commands and output into `work/host-polish/notes.md`.
- [ ] Server death during a failed restart:
  - Use a stub whose run 1 prints a link and exits after ~3 s, and whose run 2+ stays alive without a link.
  - Kill the uvicorn process once `TUNNEL DOWN` appears.
  - Pass: `host.sh` exits within ~5 s (not ~30 s), and the `pgrep` check is empty.
- [ ] Server death during the initial tunnel: with a stub that never prints a link, kill uvicorn after the health check passes. `host.sh` prints `Server stopped before the tunnel was ready`, does not print the cloudflared log tail, and exits non-zero within ~5 s.
- [ ] Quiet shutdown. Run each of these, start then stop:
  - (a) `TUNNEL=none` + SIGINT
  - (b) `TUNNEL=none` + SIGTERM
  - (c) a stubbed tunnel that stays up + SIGINT
  - (d) a stubbed tunnel that stays up + SIGTERM

  Pass, for each: the combined stdout/stderr has no line matching `Terminated|Interrupt|Killed`, and the `pgrep` check is empty afterwards.
- [ ] Regression, tunnel restart (stub run 1 exits after ~3 s, run 2 stays up). The output still shows `Share link: https://test-1…`, then `TUNNEL DOWN`, then `New share link: https://test-2…`, and `/health` keeps answering.
- [ ] Tests:
  - `HEAD /sprites/a.png` → 200, empty body, same `content-length` as GET.
  - `HEAD /` and `HEAD /assets/app.js` → 200, empty body.
  - `HEAD /sprites/missing.png` → 404.
  - `HEAD /health` → 200.
  - `HEAD /session/X` → 404 (intended).
- [ ] The existing test functions in `server/tests/test_static.py` are unchanged and pass.
- [ ] Diff inspection: README's `./host.sh` subsection names `curl` as a prerequisite, says `host.sh` refuses an invalid or busy `PORT`, and says Ctrl-C stops what it started. No other README section changes.
- [ ] `scripts/gate.sh` passes (ruff, shellcheck on `host.sh`, client build, pytest).

## Release

Release note: `host.sh` explains a bad `PORT` or missing curl instead of claiming the port is busy, re-checks the port after the build, never leaves a stray tunnel behind, notices a dead server during a tunnel restart, and shuts down quietly; sprites, client files and `/health` answer HEAD requests.

## Verification

- `python3 -m pytest server/tests/test_static.py -q`
- The `host.sh` scenarios above. Afterwards, the `pgrep` check prints nothing.

## Review

Round 1 (fresh plan reviewer, 2026-10-07): REVISE, 10 findings. The `plan-reviewer` agent type wasn't registered in this session, so a fresh general-purpose agent was given its definition verbatim. Applied:
1. Making the catch-all accept HEAD would turn HEAD `/health` and `/session/*` from 405 into 404. `/health` now gets HEAD too, `HEAD /session/X` → 404 is stated as intended, and both are tested.
2. Shutdown noise: chose the `{ …; } 2>/dev/null` cleanup wrapper, which the reviewer verified on bash 3.2, and dropped `disown`. Stub-tunnel runs added to the quiet-shutdown criterion.
3. SIGINT checks must use `set -m` or a pty, because a background job ignores SIGINT.
4. The `is_child` details are moot because item 6 was dropped (finding 8).
5. Cleanup must collect children as the exact form `kids=$(pgrep -P $$)`.
6. `PORT=0080` slipped past the arithmetic check. Leading zeros are now rejected, the comparison uses `10#`, and `0080` is in the criterion.
7. The port re-check narrows the race to about a second of uvicorn startup; it doesn't close it. Restated.
8. Simpler: dropped the PID-reuse item. macOS assigns PIDs sequentially and wraps only at 99999, so reuse within a 1–2 s poll is theoretical. The fix added a `ps` fork every tick and had its own false positive. The Owner confirmed it is dropped as won't-fix (2026-10-07).
9. `pgrep` checks now match the stub path. The orphan check is recorded in `notes.md`. A server that dies during the initial tunnel now gets its own message and criterion.
10. README addition accepted as is.

No disagreements.
Plan verdict: REVISE (round 1); all findings applied

Code review: round 1 both APPROVE. Codex: one MEDIUM (`PORT=''` falls back to 8000), accepted as no action. Claude reviewer: three LOW, one deferred. See [deferrals.md](deferrals.md) and [review-r1.md](review-r1.md).
Code-review verdict: APPROVE
Codex-review verdict: APPROVE
