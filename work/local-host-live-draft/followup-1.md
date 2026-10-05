The review of your implementation of work/local-host-live-draft/plan.md found issues to fix. You are resuming in the same worktree on branch wt/local-host-live-draft. The gate currently passes; it must still pass after your fixes.

Review findings to fix:
```
✗ HIGH — Rejoin is unreachable from the shared invite link. The Discord link is /lobby/<code>. In client/src/pages/Lobby.jsx, a started room with no stored team neither navigates to /draft/<code> nor offers a way there (joining is disabled once started). Fix: in Lobby.jsx, when the session has started and there is no stored team for this code, show a clear "Draft in progress — Rejoin your team" action that navigates to /draft/<code> (where the existing "Rejoin as…" picker lives). Do not duplicate the picker in Lobby.

✗ HIGH — host.sh cleanup uses `kill 0`, which signals the whole process group, including the caller's shell when host.sh is launched non-interactively (observed: the invoking shell was killed with exit 144). Fix: record the PIDs of the processes host.sh starts (uvicorn/caffeinate, cloudflared) and kill only those (and their children) in the cleanup; keep the run-once guard, temp-log removal, and EXIT/INT/TERM traps. A real Ctrl-C at a terminal must still leave no uvicorn/caffeinate/cloudflared process behind.

✗ MEDIUM — host.sh share-link extraction: `https://[a-z0-9-]+\.trycloudflare\.com` also matches `https://api.trycloudflare.com`, which cloudflared prints in error lines when quick-tunnel creation fails (e.g. `failed to request quick Tunnel: Post "https://api.trycloudflare.com/tunnel"`). The script would print a dead share link. Fix: exclude the `api` host when scraping the log, and keep the existing timeout / cloudflared-died failure path.
```

Not to fix (recorded, no action): LOW notes about two-tab localStorage sharing, "Room not found" wording on network errors, a stray blank line in DraftBoard.

Stay inside the plan's footprint (client/src/pages/Lobby.jsx and host.sh are both in it). Do not touch the do-not-touch list from the handoff. Re-run scripts/gate.sh until it passes, commit the fix (if the sandbox blocks git, leave changes in the worktree and say so), and print an updated summary. If a failure cannot be fixed within the plan's scope, stop and explain why instead of working around it.
