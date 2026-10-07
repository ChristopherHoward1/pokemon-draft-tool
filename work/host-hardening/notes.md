Committed the host hardening work on `wt/host-hardening` as `524b131` (`Harden local draft hosting and static paths`). The worktree is clean.

The server now returns guarded JSON 404s for missing sprites, traversal, and NUL paths. `host.sh` checks the port before building and watches for a dropped tunnel; the client distinguishes a missing room from a connection failure and offers Retry. The requested documentation is updated.

`scripts/gate.sh` **passed**: Ruff, shellcheck, client build, and 249 Python tests passed.

Self-check results:

- **Busy port:** a scratch `curl` stub confirmed a fast refusal before the build. The live listener check could not run because this sandbox denied the HTTP server’s bind.
- **Tunnel restart:** scratch stubs confirmed the warning, new share link, and cleanup.
- **Failed restart:** warnings repeated about 33 seconds apart; at most one stub tunnel ran, and cleanup succeeded.
- **`TUNNEL=none`:** the scratch check confirmed the banner and SIGTERM cleanup.

The live `/health` check, `pgrep` check, and `dev.sh` browser check remain unverified because the sandbox blocks local binds and process listing. No code outside the plan footprint was changed.
