You are the implementer for this work unit. Read AGENTS.md in the repo root first — it is your contract.
Follow its build-discipline section while staying inside the plan footprint.

Work unit: work/draft-persistence/plan.md  (read it in full; it is your source of truth)
Branch: wt/draft-persistence (already checked out in this worktree — verify with `git branch --show-current` before changing anything)

Footprint (from the plan, repeated here as the hard boundary):
- engine/pool.py: `load_pool(names)`
- engine/draft_state.py: `restore(rosters, can_undo)`, `can_undo()`
- engine/tests/test_pool.py, engine/tests/test_draft_state.py: tests for the above
- server/session_manager.py: `store_dir`, `save`, `_load_all`, override helper, docstring
- server/main.py: `DRAFT_SESSIONS_DIR` → `SessionManager`; `save` after pick and undo
- server/tests/conftest.py (new): clear `DRAFT_SESSIONS_DIR` before `server.main` is imported
- server/tests/test_persistence.py (new): round-trip, corrupt-file and logging tests
- host.sh: one `sessions_dir` variable for both uvicorn launches and the echo; the "Retrying soon" `kill -0 "$server_pid"` guard
- .gitignore: `/sessions/`
- README.md: the `./host.sh` subsection only
- work/host-polish/deferrals.md: mark the "Retrying soon" deferral resolved
- work/draft-persistence/notes.md: your notes

Key constraints:
- Persist **started** rooms only. `save` is a no-op for rooms that haven't started and when `store_dir` is None. No save in `create` or `join`.
- Engine rules change only in `engine/`. The server must not re-implement replay, budget or turn logic. Replay goes through `DraftState.pick` in `_team_at` order.
- All persistence log messages (restore count, skipped-file warnings, save failures) use `logging.getLogger("uvicorn.error")`. Not `__name__`: its INFO lines are dropped under uvicorn.
- `save` writes a temp file in the same dir, then `os.replace`. It swallows `OSError` with a warning; a pick must never fail because of disk.
- In `server/main.py`, call `manager.save(session)` inside `async with session.lock`, after a successful pick or undo.
- Do not touch `client/`, `ARCHI.md`, `engine/validator.py`, `app/`, `dev.sh` or `render.yaml`. If you think one needs to change, stop and say so in your summary instead.
- Existing test functions in `server/tests/test_backend.py` stay unchanged and must pass.
- `host.sh`: bash 3.2 compatible, shellcheck-clean, and no change to existing shutdown or exit-status behavior. Background reading: `knowledge/host-sh-testing.md`.
- Your sandbox can't bind ports, list processes or (probably) commit. Don't try to run the live `host.sh` restart scenario or the browser criterion; the Orchestrator runs those. Do run `python3 -m pytest engine server -q` and `scripts/gate.sh`. If `git commit` fails on `index.lock`, leave the changes uncommitted and say so.

When done:
1. Run scripts/gate.sh from the repo root — it must pass.
2. Commit your work on this branch with a clear message (or report that the sandbox blocked it).
3. Print a final summary: what changed and why, criteria partially met (if any), out-of-scope observations.
