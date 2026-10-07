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

## Orchestrator browser restart check (2026-10-07)

Headless Chrome through playwright-core over CDP. Two separate browser contexts stand in for the two Chrome profiles (each has its own localStorage). `TUNNEL=none`, scratch `DRAFT_SESSIONS_DIR`.

- **Run 1** on `http://localhost:8796`: create the room through the UI, Alpha and Bravo join, start, 3 picks.
- SIGINT (rc 130), then re-run `./host.sh`.
- **Run 2** on `http://127.0.0.1:8796`: a different origin, so localStorage starts empty, the same as a new cloudflared link.

The run didn't use a real cloudflared tunnel. The origin swap tests the same client path (no stored identity, then the "Rejoin as…" picker) without opening a public link.

```
phase1 room MD9MDB
phase1 Alpha picked Kingambit / Bravo picked Moltres / Bravo picked Zapdos
phase1 3 picks made; Alpha on the clock
run1 host.sh rc=130
INFO:     Restored 1 draft room(s): MD9MDB
phase2 Alpha: Rejoin picker shown / Bravo: Rejoin picker shown
phase2 A, B: pick history shows restored picks
phase2 Alpha picked Cobalion; 4th pick recorded and reached Bravo's board
run2 host.sh rc=130, leftovers: none
REJOIN: PASS
```

Bravo's screenshot after the 4th pick shows 4 taken cards, all 4 picks in the history, Bravo at 44 pts and Alpha at 45 pts, and the correct rosters. Sprites were blank because the worktree has no `sprites/` dir; that's expected and cosmetic.
