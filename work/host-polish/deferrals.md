# Deferrals — host-polish

- **Raised (codex-review r1, MEDIUM):** `PORT=''` (explicitly empty) falls back to 8000 instead of being refused, because `PORT="${PORT:-8000}"` runs before validation. **No action:** pre-existing behavior, and treating an empty variable as unset is the usual shell convention.
- **Resolved (draft-persistence):** if the server dies during a failed tunnel restart, `host.sh` skips "Tunnel restart failed; the draft remains available locally. Retrying soon." by checking `kill -0 "$server_pid"` first.
- **Dropped (Owner, 2026-10-07):** `kill -0` hitting a reused PID (host-hardening deferral). Won't fix; see plan.md Review finding 8.
