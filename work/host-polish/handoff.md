You are the implementer for this work unit. Read AGENTS.md in the repo root first — it is your contract.
Follow its build-discipline section while staying inside the plan footprint.

Work unit: work/host-polish/plan.md  (read it in full; it is your source of truth)
Branch: wt/host-polish (already checked out in this worktree — verify with `git branch --show-current` before changing anything)

Footprint (from the plan, repeated here as the hard boundary):
- host.sh — curl/PORT validation, `check_port_free` called twice, cleanup sweeps direct children and runs silenced, scrape loop watches the server
- server/main.py — GET+HEAD on `/sprites/{name:path}`, the `/{full_path:path}` catch-all, and `/health`
- server/tests/test_static.py — HEAD tests (add new test functions; do not modify existing ones)
- ARCHI.md — `./host.sh` entry point (re-checks the port before launch) and the `server/` line (static routes and `/health` accept HEAD)
- README.md — `./host.sh` subsection only: curl prerequisite next to cloudflared; one line after the `PORT=8001` sentence about refusing an invalid/busy PORT and Ctrl-C stopping what it started
- work/host-polish/notes.md — record of the orphan-check run (commands + output)

Key constraints:
- The machine's bash is 3.2.57 (`#!/usr/bin/env bash` resolves to /bin/bash). No `wait -n`, no bash 4+ features. host.sh must stay shellcheck-clean.
- The PID-reuse deferral is dropped as won't-fix: do NOT add an `is_child`/`ps -o ppid=` helper; keep plain `kill -0` liveness checks.
- PORT validation: `^[1-9][0-9]*$` and ≤ 65535 compared as `10#$PORT`; message exactly `PORT must be a number from 1 to 65535`. Missing curl message exactly `curl is required`. Both exit 1 before any probe or build.
- Cleanup: stop tracked PIDs first, then the children from exactly `kids=$(pgrep -P $$)` (no pipeline). Wrap the cleanup body (after the `cleaned` guard and `trap -` line) in `{ …; } 2>/dev/null`. No `disown`. The exit status when the server dies must not change.
- `start_tunnel`'s scrape loop also breaks when `kill -0 "$server_pid"` fails. On the initial tunnel, a dead server prints `Server stopped before the tunnel was ready` (no cloudflared log tail) and exits non-zero.
- The orphan check needs a temporary edit to host.sh; it must NOT be in your final diff. Record the commands and output in work/host-polish/notes.md.
- Your sandbox may not be able to bind ports or run host.sh scenarios. If it can't, say so in your summary; the Orchestrator runs the live host.sh scenarios afterwards. Do not mark those criteria as met unless you actually ran them.
- Stub cloudflared and any test scaffolding live in a scratch temp dir, never in the repo.
- Do not touch engine/, client/, server/session_manager.py, dev.sh, render.yaml, scripts/.

When done:
1. Run scripts/gate.sh from the repo root — it must pass.
2. Commit your work on this branch with a clear message.
3. Print a final summary: what changed and why, criteria partially met (if any), out-of-scope observations.
