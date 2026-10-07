# Survive a server restart mid-draft

**Slug:** draft-persistence · **Date:** 2026-10-07 · **Status:** implemented

## Goal

Draft rooms live only in `SessionManager._sessions` (`server/session_manager.py`, whose docstring says "a server restart clears them"). On draft night the server is the Owner's laptop. If uvicorn dies, `host.sh` exits, or the Owner has to Ctrl-C and re-run it, every started draft is lost: the generated pool and all picks made. The draft then has to start over from Setup with a different random pool.

Done = after a restart, `./host.sh` brings back every **started** room with the same code, slots, pool, rosters, budgets and turn, and says so on startup. Players open the new share link at `/draft/<CODE>`, use the existing "Rejoin as…" picker and carry on. Nothing changes when there's no restart.

Lobby rooms (not yet started) are not persisted. Recreating one takes seconds, and on a new tunnel origin a restored lobby would be a dead end. See Review, finding 2.

## Approach

**Snapshot, not event log.** Write one JSON file per started room after every state change (start, pick, undo), and load them all when the server starts. A room is small (config, ≤ 8 team names, ≤ a few hundred pool names, rosters), so rewriting the whole file each time is cheap.

Snapshot shape (`version: 1`):

```json
{"version": 1, "id": "ABC234", "config": {…CreateSessionRequest…},
 "slots": ["Team A", "Team B"],
 "pool": ["slug", …], "rosters": {"Team A": ["slug", …], …}, "can_undo": true}
```

It stores canonical slugs only. Entries are re-read from the format's data file, so pick order and budgets are recomputed rather than trusted.

**Engine (`engine/`)**: two small additions, since rebuilding draft state is an engine rule.

- `DraftPool.load_pool(names)` sets `_pool` and `_available` from `_all` in the given order. It raises `ValueError` naming any slug that isn't in the format.
- `DraftState.restore(rosters, can_undo)` takes a freshly built `DraftState` with no picks and replays the picks in turn order. For each pick number `t`, take `team = _team_at(t)` and that team's next roster slug, then call `self.pick(slug)`.
  - Any invalid pick raises `ValueError`.
  - So does a mismatch: a roster with picks left over, or a roster the turn order can't reach.
  - Picks go through the normal validator, so budgets come out the same as during the live draft.
  - Afterwards, if `can_undo` is false, set `_undo_record = None`. Otherwise the replay leaves it on the last pick, which is exactly what a live draft would allow. This keeps one-step undo exact.
  - The plan reviewer verified this replay against real drafts: both orders, every stop point, with and without an undo.
- `DraftState.can_undo()` returns `self._undo_record is not None`.

**Server (`server/session_manager.py`).**

- `SessionManager(store_dir: Path | None = None)`. With `None` (the default), there is no persistence, exactly as today.
- `save(session)`:
  - Writes `<store_dir>/<id>.json` atomically (temp file in the same dir, then `os.replace`).
  - Does nothing without a `store_dir` or when the room hasn't started.
  - An `OSError` is logged as a warning and swallowed. A full disk must not break a live pick; the draft keeps running in memory.
- `start` calls `save` before returning.
- `start`'s per-room override block (copy `pool._config`, set budget and roster_size) moves into a helper, so restore builds the pool with the same overrides.
- `_load_all()` runs in `__init__` when `store_dir` is set. It creates the dir if missing and reads every `*.json`.
  - A file that fails to parse, has an unknown `version`, fails `CreateSessionRequest` validation, or fails engine restore is logged as a warning and skipped, never fatal. The file is left in place for inspection.
  - When N > 0, it logs `Restored N draft room(s): ABC234, …` at INFO.
- **Logging.** All of these messages go to `logging.getLogger("uvicorn.error")`, which uvicorn's default config prints at INFO. A `__name__` logger has no handler under uvicorn, so its INFO lines would be dropped (Review, finding 1).
- The module docstring changes from "ephemeral" to "in memory; started rooms optionally snapshotted to `store_dir`".

**Server (`server/main.py`).**

- `manager = SessionManager(store_dir=Path(d) if (d := os.environ.get("DRAFT_SESSIONS_DIR")) else None)`.
- Call `manager.save(session)` inside the lock, right after a successful pick and a successful undo. Then the file on disk always matches what was broadcast.

**Tests.**

- A new `server/tests/conftest.py` deletes `DRAFT_SESSIONS_DIR` from `os.environ` at import, before anything imports `server.main`. Then an exported variable in the gate's shell can't make `test_backend.py` read or write real room files.
- HTTP/WS persistence tests swap in `monkeypatch.setattr(server.main, "manager", SessionManager(store_dir=tmp_path))`. The handlers read the module global, so this works.

**`host.sh`.**

- Resolve the folder once: `sessions_dir="${DRAFT_SESSIONS_DIR:-sessions}"` (`host.sh` already `cd`s to the repo root).
- Pass `DRAFT_SESSIONS_DIR="$sessions_dir"` in the env of both uvicorn launch lines.
- After "join first — slot 1 is the host", echo `Started drafts are saved in $sessions_dir/; re-running ./host.sh restores them`.
- Fold in the host-polish deferral: before printing "Tunnel restart failed… Retrying soon.", check `kill -0 "$server_pid"`. If the server is gone, skip the message; the loop exits on its own next check.
- Per the 2026-10-07 decision, verification follows `knowledge/host-sh-testing.md`.

**Repo.** `.gitignore` gets `/sessions/`.

Not done, deliberately:
- **Lobby rooms aren't persisted** (see Goal).
- **`dev.sh` and Render stay in-memory.** Render's disk is ephemeral anyway, and `--reload` restoring rooms during dev would be surprising. Anyone can opt in with `DRAFT_SESSIONS_DIR`.
- **No expiry or cleanup of old room files.** Restoring finished drafts is harmless, and keeps them around for the results-export unit that comes next. The dir is easy to clear by hand.
- **No client changes.**
  - On the default cloudflared tunnel, the new origin has empty `localStorage`, so Draft shows the "Rejoin as…" picker.
  - On the same origin (`TUNNEL=none` or localhost), the socket may have given up retrying during the rebuild (5 tries, about 23 s), so players reload the page. The README says "reload".
- **Regenerating a data file mid-league isn't guarded.** If tier costs change, a restored room's budgets follow the new costs, or replay fails and the room is skipped with a warning. Data is regenerated only by hand through `scripts/`, never during a draft.

Alternatives considered:
- *Pickle `Session`*: rejected. It's brittle across code changes, and unpickling a file is unsafe.
- *SQLite*: rejected. It's more machinery than a handful of small JSON files need.
- *Append-only pick log*: rejected. Rosters plus turn order already determine the pick sequence.

## Footprint

Files to modify:
- engine/pool.py: `load_pool(names)`
- engine/draft_state.py: `restore(rosters, can_undo)`, `can_undo()`
- engine/tests/test_pool.py, engine/tests/test_draft_state.py: tests for the above
- server/session_manager.py: `store_dir`, `save`, `_load_all`, override helper, docstring
- server/main.py: `DRAFT_SESSIONS_DIR` → `SessionManager`; `save` after pick and undo
- server/tests/conftest.py (new): clear `DRAFT_SESSIONS_DIR`
- server/tests/test_persistence.py (new): round-trip, corrupt-file and logging tests
- host.sh: `sessions_dir` for uvicorn and the echo, the "Retrying soon" `kill -0` guard
- .gitignore: `/sessions/`
- README.md: the `./host.sh` subsection (one or two sentences on restore and reloading)
- work/host-polish/deferrals.md: mark the "Retrying soon" deferral resolved

Files NOT to touch:
- client/: the rejoin flow already covers started drafts. If a client change turns out to be needed, stop and raise it.
- ARCHI.md: it's regenerated by `/compact`, never hand-edited. Refresh it after merge.
- engine/validator.py, app/streamlit_app.py, dev.sh, render.yaml: out of scope.

## Acceptance criteria

Engine:
- [ ] `DraftPool.load_pool` with a list of slugs makes `available()` return exactly those entries. An unknown slug raises `ValueError` naming it.
- [ ] Round trip, for snake and linear orders, 3 teams, at partial and complete states, each with and without a preceding undo: after `restore(rosters_as_slugs, can_undo)` on a fresh `DraftState`, `export()` and `can_undo()` equal the original's.
- [ ] `restore` with `can_undo=False` makes `undo()` raise `RuntimeError`.
- [ ] `restore` raises `ValueError` in each of these cases: a roster slug not in the pool; a slug in two rosters; an impossible shape (e.g. team 2 has more picks than snake order allows).

Server (pytest, `tmp_path` as `store_dir`, manager swapped in via `monkeypatch`):
- [ ] Create, join, start and pick through the HTTP and WS API. Then build a new `SessionManager(store_dir=tmp_path)`. Its `state_payload()` for that room equals the original's, and `slots`, `started` and `config` match.
- [ ] Rooms that haven't started write no file.
- [ ] Undo then restore: the restored room's `can_undo()` is false, and a WS `undo` from slot 1 returns the "No pick to undo" error.
- [ ] A garbage `.json`, a `version: 2` file and a file whose roster slug isn't in the pool are each skipped with a logged warning (checked with `caplog`), and valid rooms in the same dir still load.
- [ ] Restoring one room logs `Restored 1 draft room(s): <CODE>` at INFO on the `uvicorn.error` logger (`caplog`).
- [ ] If `save` raises `OSError` (monkeypatched), the pick still succeeds and broadcasts, and a warning is logged.
- [ ] Under pytest, `server.main.manager` has no store dir, even when `DRAFT_SESSIONS_DIR` is exported in the shell that runs pytest.
- [ ] The existing `server/tests/test_backend.py` tests are unchanged and pass.
- [ ] Diff inspection: `save` writes through a temp file plus `os.replace`, and pick and undo call `save` inside `session.lock`.

`host.sh`, run by the Orchestrator outside the implementer sandbox per `knowledge/host-sh-testing.md`:
- [ ] Restart scenario. Use a bash script with `set -m` (or a pty), `TUNNEL=none`, and the same absolute scratch `DRAFT_SESSIONS_DIR` for both runs.
  1. Start `./host.sh`. Create a room and join 2 teams via curl, then start it.
  2. Make 1 pick with a short Python `websockets` client. Take the slug from `GET /session/<CODE>/state`, the first `pool[]` entry where `taken` is false.
  3. Send SIGINT; expect rc 130. The `pgrep` leftover check is empty.
  4. Re-run `./host.sh`.

  Pass: the output shows `Restored 1 draft room(s): <CODE>` and the saved-dir line naming the scratch dir. `GET /session/<CODE>/state` shows the pick and the same `current_team`.

  Also: the same scenario against `git show origin/main:host.sh` fails, because the room is gone. Record the script and output in `notes.md`.
- [ ] Diff inspection: one `sessions_dir` variable feeds both uvicorn launch lines and the echo.
- [ ] Diff inspection: "Retrying soon" is printed only when `kill -0 "$server_pid"` succeeds.
- [ ] Regression: the quiet-shutdown and `pgrep`-empty checks from `knowledge/host-sh-testing.md` still pass.

Manual (run by the Orchestrator before `/4-release`, per the 2026-10-06 decision):
- [ ] Real-browser restart on the default cloudflared tunnel:
  1. Two Chrome profiles draft over `./host.sh`; make 3 picks.
  2. Ctrl-C and re-run `./host.sh`.
  3. Open `/draft/<CODE>` on the new link in both profiles.

  Pass: the "Rejoin as…" picker appears, both rejoin, the board shows the 3 picks, and the 4th pick goes through.

Docs and gate:
- [ ] Diff inspection: README's `./host.sh` subsection says started drafts survive a restart, where they're stored, and that players open the new link (or reload) and rejoin. No other README section changes.
- [ ] `scripts/gate.sh` passes.

## Release

Release note: Started drafts hosted with `./host.sh` survive a restart. Re-running it restores each room's pool, picks and turn, and players rejoin with the "Rejoin as…" picker.

## Verification

- `python3 -m pytest engine server -q`
- The `host.sh` restart scenario above, per `knowledge/host-sh-testing.md` (cited for the Verification section and the handoff, per the 2026-10-07 decision).

## Review

Round 1 (fresh plan reviewer, 2026-10-07): REVISE, 9 findings. The `plan-reviewer` agent type isn't registered in this session, so a fresh general-purpose agent was given its definition verbatim. The reviewer confirmed the replay design by experiment. Applied:
1. A `__name__` logger's INFO is dropped under uvicorn, so the restore line would never print. Messages now use the `uvicorn.error` logger, with a `caplog` criterion.
2. On a new tunnel origin, a restored *lobby* room is a dead end: no host Start button and no rejoin picker in Lobby, and re-joining returns 409. Took option (a): persist started rooms only.
3. ARCHI.md is regenerated, never hand-edited. Removed from the footprint; refresh via `/compact` after merge.
4. The `host.sh` echo hard-coded `sessions/`. It now uses one `sessions_dir` variable, checked by diff inspection.
5. The restart criterion now names the harness details: `set -m`, rc 130, the `pgrep` check, a shared absolute dir, the websockets client and the fails-on-main check.
6. Sockets give up after about 23 s, which a rebuild can exceed. Changed "auto-reconnect" to "reload the page".
7. Simpler version (started rooms only) adopted, together with finding 2.
8. Env var leaking into tests: added `server/tests/conftest.py`, named the monkeypatch mechanism, and added a criterion.
9. A regenerated data file changing tier costs is noted under "Not done".

No disagreements.
Plan verdict: REVISE (round 1); all findings applied. Owner approved 2026-10-07, including started-rooms-only scope.

Code review: round 1, both APPROVE. The Claude reviewer raised one MEDIUM (no `fsync` before the rename), which the Orchestrator fixed in 58d78aa, plus one LOW (no action). Round 2, both APPROVE with two LOWs (no action). See [review-r1.md](review-r1.md) and [review-r2.md](review-r2.md).
Code-review verdict: APPROVE
Codex-review verdict: APPROVE
