# Implementer notes — dispatch 3 (codex gpt-6-sol, CLI 0.160.1)

Dispatches 1–2 failed before starting: Codex CLI 0.139 rejected every model under a ChatGPT login; fixed by updating the CLI.

Implementer summary (verbatim):
> Implemented the scoped changes: FastAPI serves the built client, `host.sh` builds a same-origin bundle and starts the server, and draft players can restore or choose their team after reopening a tab. The README and PLAN updates are included.
> `scripts/gate.sh` passed: 246 tests passed, 4 skipped. `host.sh` also passed shellcheck, and the same-origin build contains no Render URL.
> **The work is not committed.** The sandbox denied `git add` access to the worktree's Git index. It also denied the local server bind, so live browser and tunnel checks remain unverified.

Orchestrator: staged + committed in the worktree after re-running the gate; artifacts synced by hand (sync-artifacts refuses non-primary checkouts — Owner chose to drive from the orca worktree).
