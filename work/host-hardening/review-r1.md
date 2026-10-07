# Review round 1 — host-hardening

**Code-review (Claude, fresh):** APPROVE. Gate re-run: PASS. 13/14 criteria met. The manual dev.sh browser check was not verified, though code reasoning supports it. Findings, all LOW, no action:
1. A signal arriving between `cloudflared &` and `tunnel_pid=$!` could orphan that cloudflared (window of microseconds).
2. A failed restart attempt blocks the poll loop for up to 30 s, which delays the exit if uvicorn crashes during it.
3. On shutdown, bash job control prints "Terminated: 15 cloudflared …".
4. `HEAD /sprites/<file>` now returns 405 (the StaticFiles mount answered HEAD). No client sends HEAD.
5. Any curl exit other than 7 reads as "port in use" (e.g. curl missing → 127). curl is already required later in the script.

**Codex-review:** REQUEST CHANGES. One HIGH: `PLAN.md` is outside the footprint. Routed to the orchestrator, not the implementer: that commit (9442cd9, the Now entry) was orchestrator bookkeeping added before review. It is reverted on the branch and gets re-added after approval, matching local-host-live-draft (71737b4). No implementer change.

Codex tooling note: the first run exited 2 because local `main` predates the harness (no config.yaml). Re-run with `REVIEW_BASE=origin/main`.
