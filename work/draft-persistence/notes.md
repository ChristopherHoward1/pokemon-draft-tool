# Draft persistence implementation notes

- Started rooms save a version 1 JSON snapshot after Start, pick and undo. Lobby rooms do not write files.
- Restore rebuilds the format pool, applies room budget and roster overrides, and replays roster slugs through `DraftState.pick` in turn order. Bad files remain on disk and produce warnings through `uvicorn.error`.
- `python3 -m pytest engine server -q`: 149 passed. The system `python3` lacks pytest; the installed Conda Python segfaults importing its `readline` extension, so verification used `/opt/miniconda3/bin` first on `PATH` and a temporary `/private/tmp/draft-persistence-pyshim/sitecustomize.py` that supplies a Python-only `readline` module.
- Live `host.sh` restart, quiet shutdown, `pgrep`, fails-on-main, and browser checks require ports/process inspection and are left for the Orchestrator per `knowledge/host-sh-testing.md`. No live scenario output was recorded here.

## Orchestrator live checks (2026-10-07, outside the sandbox, per knowledge/host-sh-testing.md)

Harness: `set -m` bash script, `TUNNEL=none`, one absolute scratch `DRAFT_SESSIONS_DIR` for both runs. Create a room, join Alpha/Beta, start, pick via a Python `websockets` client, SIGINT, re-run, compare `current_team` and Alpha's roster.

```
# wt/draft-persistence host.sh, port 8771
before: Beta ['corviknight']
run1 rc=130, leftovers: none
INFO:     Restored 1 draft room(s): L59A37
Started drafts are saved in <scratch>/sessions-8771/; re-running ./host.sh restores them
after:  Beta ['corviknight']
run2 rc=130, leftovers: none, no Terminated/Interrupt/Killed lines
RESULT: PASS

# origin/main (8a542e1) host.sh + server, port 8772: must fail
before: Beta ['latios']
after:  MISSING {'reason': "No session 'R4QSD3'"}
RESULT: FAIL (expected)

# Quiet-shutdown regression (stub cloudflared stays up)
none INT rc=130 noise=0 left=[]
none TERM rc=143 noise=0 left=[]
cloudflared INT rc=130 noise=0 left=[] link=https://test-1.trycloudflare.com
cloudflared TERM rc=143 noise=0 left=[] link=https://test-2.trycloudflare.com
```
