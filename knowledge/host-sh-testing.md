# Testing host.sh without a real tunnel

`host.sh` runs under macOS `/usr/bin/env bash`, which is **bash 3.2**: no `wait -n`, no associative arrays, no `${var,,}`. shellcheck (in the gate) doesn't catch these, so check by hand.

The gate never runs `host.sh`. Live scenarios need port binds, and the Codex implementer sandbox can't make them. The Orchestrator runs these before review ([PLAN.md decision, 2026-10-06](../PLAN.md)). Put stubs in a scratch dir, never in the repo, and give every run its own port.

**Fake cloudflared.** Put it first on `PATH` (`PATH=$STUB:$PATH`). It ignores its args, and a counter file in its own dir tells runs apart. Use `sleep`, not `exec sleep`, so `pgrep` can see the stub.

```bash
#!/bin/bash
d=$(dirname "$0"); n=$(( $(cat "$d/count" 2>/dev/null || echo 0) + 1 )); echo $n > "$d/count"
if [ $n -eq 1 ]; then echo "INF |  https://test-1.trycloudflare.com  |"; sleep 3; exit 1; fi
echo "INF |  https://test-$n.trycloudflare.com  |"; sleep 100000
# failed-restart variant: on run 2+ print only
# 'ERR failed to request quick Tunnel: Post "https://api.trycloudflare.com/tunnel"'
```

**Scenarios** (each must end with `pgrep -fl 'uvicorn server.main|cloudflared|caffeinate -i uvicorn'` printing nothing):

- **Busy port:** `python3 -m http.server 8765 --bind 127.0.0.1 &`, then `PORT=8765 TUNNEL=none ./host.sh`. Expect rc 1 in under 1 s, before the build.
- **No tunnel:** `PORT=8768 TUNNEL=none ./host.sh &`. The banner prints and `/health` answers. SIGINT gives rc 130 and SIGTERM gives rc 143.
- **Tunnel restart:** `PATH=$STUB:$PATH PORT=8766 ./host.sh > out 2>&1 &`. Poll `out` for `New share link: https://test-2`. It should be preceded by `Share link: …test-1` and `TUNNEL DOWN`. `/health` still answers; then send SIGTERM.
- **Failed restart:** run the variant stub for about 100 s. `TUNNEL DOWN` should repeat roughly every 30 s, with at most one stub alive at a time.

Expected noise: bash prints `Terminated: 15 cloudflared …` on shutdown.
