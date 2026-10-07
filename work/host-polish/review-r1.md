# Code review r1 — host-polish

Fresh Claude reviewer (code-reviewer definition, verbatim; the agent type was not registered in the session), 2026-10-07, against `origin/main...wt/host-polish` at 5327d45.

Verdict: APPROVE. Gate re-run by the reviewer: PASS (252 passed, 4 skipped). Footprint: only the five declared files. All acceptance criteria met; the reviewer re-ran PORT validation (incl. `0`, `65536`, `" 80"`, 21 digits), missing curl, server death during a failed restart (3 s), and quiet shutdown (c)/(d).

Findings (all LOW, non-blocking):
1. `host.sh` — when the server dies during a tunnel restart, the loop prints "Tunnel restart failed; the draft remains available locally. Retrying soon." and then exits. Deferred, see deferrals.md.
2. `ARCHI.md:13` — the rewritten `server/` line reads as if `/sprites` also has SPA fallback, and drops the `CLIENT_DIST` name.
3. `notes.md` — the valid orphan evidence is the Orchestrator's variant (tunnel_pid cleared inside cleanup, compared against main), not the implementer's run. Accepted.
