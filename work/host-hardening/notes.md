Committed the host hardening work on `wt/host-hardening` as `524b131` (`Harden local draft hosting and static paths`). The worktree is clean.

The server now returns guarded JSON 404s for missing sprites, traversal, and NUL paths. `host.sh` checks the port before building and watches for a dropped tunnel; the client distinguishes a missing room from a connection failure and offers Retry. The requested documentation is updated.

`scripts/gate.sh` **passed**: Ruff, shellcheck, client build, and 249 Python tests passed.

Self-check results:

- **Busy port:** a scratch `curl` stub confirmed a fast refusal before the build. The live listener check could not run because this sandbox denied the HTTP server’s bind.
- **Tunnel restart:** scratch stubs confirmed the warning, new share link, and cleanup.
- **Failed restart:** warnings repeated about 33 seconds apart; at most one stub tunnel ran, and cleanup succeeded.
- **`TUNNEL=none`:** the scratch check confirmed the banner and SIGTERM cleanup.

The live `/health` check, `pgrep` check, and `dev.sh` browser check remain unverified because the sandbox blocks local binds and process listing. No code outside the plan footprint was changed.

## Orchestrator verification (2026-10-06, outside the implementer sandbox)

- Gate: `scripts/gate.sh` PASS (249 passed, 4 skipped).
- Busy port (`http.server` on 8765, `PORT=8765 TUNNEL=none ./host.sh`): rc=1 in <1 s, before the build, "Port 8765 is in use" message; no leftover processes.
- Stub tunnel restart (PORT=8766): Share link test-1 → TUNNEL DOWN → New share link test-2 + repost line; `/health` ok; SIGTERM → rc 143, `pgrep` clean. Cosmetic: bash job-control prints "Terminated: 15 cloudflared …" on shutdown.
- Stub failed restart (PORT=8767, 100 s): 3× TUNNEL DOWN + "Tunnel restart failed…", ~30 s apart; max 1 stub process concurrently; `/health` ok; SIGTERM → `pgrep` clean.
- Not run: the manual dev.sh browser Retry check.
