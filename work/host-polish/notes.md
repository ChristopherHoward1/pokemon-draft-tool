# Orphan check attempt

The sandbox prevents a conclusive orphan check: `pgrep` cannot list processes, and binding `127.0.0.1` raises `PermissionError: [Errno 1] Operation not permitted`. The Orchestrator must run the live host scenarios outside this sandbox. The temporary edit below was restored before the final diff.

Commands run from the repo root (the scratch directory contained the `curl`, `uvicorn`, and `cloudflared` stub scripts):

```sh
STUB=$(mktemp -d)
cp host.sh "$STUB/host.sh.orig"
trap 'cp "$STUB/host.sh.orig" host.sh' EXIT
cat > "$STUB/curl" <<'EOF'
#!/bin/bash
case "$*" in *'/health'*) exit 0;; *) exit 7;; esac
EOF
cat > "$STUB/uvicorn" <<'EOF'
#!/bin/bash
sleep 300
EOF
cat > "$STUB/cloudflared" <<'EOF'
#!/bin/bash
printf '%s\n' 'https://test-1.trycloudflare.com'
sleep 300
EOF
chmod +x "$STUB/curl" "$STUB/uvicorn" "$STUB/cloudflared"
/opt/miniconda3/bin/python -c 'from pathlib import Path; p=Path("host.sh"); s=p.read_text(); old="  tunnel_pid=$!\n"; assert s.count(old)==1; p.write_text(s.replace(old, "  tunnel_pid=\"\" # simulate signal before PID assignment\n"))'
PATH="$STUB:$PATH" TUNNEL=cloudflared ./host.sh > "$STUB/host.log" 2>&1 &
host_pid=$!
for n in 1 2 3 4 5 6 7 8 9 10; do
  if rg -q 'Share link:' "$STUB/host.log"; then break; fi
  sleep 1
done
cat "$STUB/host.log"
printf 'before TERM:\n'
pgrep -fl "$STUB/cloudflared|uvicorn server.main|caffeinate -i uvicorn" || true
kill -TERM "$host_pid"
wait "$host_pid"; printf 'host exit=%s\n' "$?"
printf 'after TERM:\n'
pgrep -fl "$STUB/cloudflared|uvicorn server.main|caffeinate -i uvicorn" || true
```

Output relevant to the check:

```text
Warning: sprites missing. Run python3 scripts/fetch_sprites.py to add them.
cloudflared did not provide a share link:
before TERM:
sysmon request failed with error: sysmond service not found
pgrep: Cannot get process list
zsh:kill:30: kill 23984 failed: no such process
host exit=1
after TERM:
sysmon request failed with error: sysmond service not found
pgrep: Cannot get process list
```

The simulated empty PID let `start_tunnel` fail before the stub link was scraped. `host.sh` had exited before SIGTERM, and the unavailable `pgrep` prevented checking for surviving children. This run does not meet the orphan acceptance criterion.

## Orchestrator live run (2026-10-07, outside the sandbox, at cfcfb5c)

The implementer's orphan attempt above did not exercise the race: emptying `tunnel_pid` at launch made `start_tunnel` fail first. Re-run with a scratch copy of host.sh whose cleanup clears `tunnel_pid` right after `trap - EXIT INT TERM`, so cleanup cannot see the tunnel PID. Against `origin/main`'s host.sh, the same edit leaves the stub cloudflared running after SIGTERM; on this branch nothing is left. Harness: stub cloudflared in a mktemp dir, `set -m` for SIGINT, pgrep on the stub path.

```text
== PORT validation
PASS: PORT=abc
PASS: PORT=70000
PASS: PORT=0080
== missing curl
PASS: no curl
== busy port
PASS: busy port
== tunnel restart regression
PASS: restart
PASS: restart no leftovers
== quiet shutdown
PASS: quiet none/INT rc=130
PASS: quiet none/INT no leftovers
PASS: quiet none/TERM rc=143
PASS: quiet none/TERM no leftovers
PASS: quiet up/INT rc=130
PASS: quiet up/INT no leftovers
PASS: quiet up/TERM rc=143
PASS: quiet up/TERM no leftovers
== server death during failed restart
PASS: failed-restart exited in 3s
PASS: failed-restart no leftovers
== server death during initial tunnel
PASS: initial-death rc=1 in 1s
PASS: initial-death no leftovers
== orphan (tunnel_pid cleared in cleanup, scratch copy)
before TERM: 43458 /opt/miniconda3/bin/python /opt/miniconda3/bin/uvicorn server.main:app --host 127.0.0.1 --port 8770;43460 caffeinate -i uvicorn server.main:app --host 127.0.0.1 --port 8770;43478 /bin/bash /var/folders/y6/cqq_kqw13z58pgr6c9f3fzdm0000gn/T/tmp.8lUmLtbJqY/cloudflared tunnel --url http://127.0.0.1:8770;
PASS: orphan no leftovers
done
```
