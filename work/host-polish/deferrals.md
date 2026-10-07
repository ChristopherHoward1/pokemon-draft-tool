# Deferrals — host-polish

- **Raised (codex-review r1, MEDIUM):** `PORT=''` (explicitly empty) falls back to 8000 instead of being refused, because `PORT="${PORT:-8000}"` runs before validation. **No action:** pre-existing behavior, and treating an empty variable as unset is the usual shell convention.
- **Raised (code-review r1, LOW):** if the server dies during a failed tunnel restart, `host.sh` prints "Tunnel restart failed; the draft remains available locally. Retrying soon." right before exiting. **Deferred:** fixing it would force another review round for a log line. **Lands in:** next unit that touches `host.sh` — check `kill -0 "$server_pid"` before that message.
- **Dropped (Owner, 2026-10-07):** `kill -0` hitting a reused PID (host-hardening deferral). Won't fix; see plan.md Review finding 8.
