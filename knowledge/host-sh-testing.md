# Testing host.sh without a real tunnel

`host.sh` runs under macOS `/usr/bin/env bash`, which is **bash 3.2**: no `wait -n`, no associative arrays, no `${var,,}`. shellcheck (in the gate) doesn't catch these, so check by hand.

The gate never runs `host.sh`. Live scenarios need port binds and `pgrep`, and the Codex implementer sandbox has neither. The Orchestrator runs these before review ([PLAN.md decision, 2026-10-06](../PLAN.md)). Put stubs in a scratch dir, never in the repo, and give every run its own port.

**Before you start**, check that nothing real matches the patterns you'll `pkill`: `pgrep -fl 'uvicorn server.main|caffeinate -i uvicorn|cloudflared'`.

**Fake cloudflared.** Put it first on `PATH` (`PATH=$STUB:$PATH`). It ignores its args, and a counter file in its own dir tells runs apart. Keep the stub itself alive with a `sleep` loop (not `exec sleep`), so `pgrep` on its path can see it.

```bash
#!/bin/bash
D=$(dirname "$0")
n=$(( $(cat "$D/count" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$D/count"
case ${STUB_MODE:-up} in
  up) echo "https://test-$n.trycloudflare.com" ;;                                   # stays up
  restart) echo "https://test-$n.trycloudflare.com"; if (( n == 1 )); then sleep 3; exit 0; fi ;;
  failrestart) if (( n == 1 )); then echo "https://test-1.trycloudflare.com"; sleep 3; exit 0; fi ;;
  nolink) ;;                                                                         # never prints a link
esac
while :; do sleep 1; done
```

**Harness rules.**
- **SIGINT:** a script started with `&` from a non-interactive shell inherits SIGINT as *ignored*, so `host.sh`'s INT trap never fires and the check proves nothing. Run the harness under `set -m` (in a bash script, not zsh `-c`), or use a pty.
- **Leftover check:** match the stub's path, never bare `cloudflared`: `pgrep -fl "$STUB/cloudflared|uvicorn server.main|caffeinate -i uvicorn"` must print nothing after each run.
- **New checks:** run them once against `git show origin/main:host.sh` (saved as a scratch copy inside the checkout, so `cd "$(dirname "$0")"` works) and confirm they *fail* there. A check that passes on both proves nothing.

**Scenarios** (v2026.10.3 behavior):

| Scenario | How | Expect |
|---|---|---|
| Bad PORT | `PORT=abc` / `70000` / `0080`, `TUNNEL=none` | rc 1 within 1 s, `PORT must be a number from 1 to 65535`, no "in use" |
| No curl | `PATH` = scratch dir with symlinks to bash, env, dirname, mkdir only | rc 1, `curl is required` |
| Busy port | `python3 -m http.server 8765 --bind 127.0.0.1 &`, then `PORT=8765 TUNNEL=none` | rc 1 within 2 s, before the build |
| Tunnel restart | `STUB_MODE=restart` | `Share link: …test-1`, `TUNNEL DOWN`, `New share link: …test-2`; `/health` still answers |
| Quiet shutdown | `TUNNEL=none` and `STUB_MODE=up`, each with SIGINT and SIGTERM | rc 130 / 143, no `Terminated\|Interrupt\|Killed` line, nothing left |
| Death during failed restart | `STUB_MODE=failrestart`; after `TUNNEL DOWN`, `pkill -f 'uvicorn server.main'` | `host.sh` exits within ~5 s |
| Death before first link | `STUB_MODE=nolink`; once `/health` answers, kill uvicorn | `Server stopped before the tunnel was ready`, no cloudflared log tail |
| Orphaned tunnel | `STUB_MODE=up` on a scratch copy whose cleanup clears `tunnel_pid` right after `trap - EXIT INT TERM`; SIGTERM once the share link prints | nothing left (on v2026.10.2 the stub survives) |

Don't simulate the orphan race by emptying `tunnel_pid` at launch. `start_tunnel` then fails before any link appears, and the race is never exercised.
