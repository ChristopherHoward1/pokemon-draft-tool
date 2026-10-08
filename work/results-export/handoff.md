You are the implementer for this work unit. Read AGENTS.md in the repo root first — it is your contract.
Follow its build-discipline section while staying inside the plan footprint.

Work unit: work/results-export/plan.md  (read it in full; it is your source of truth)
Branch: wt/results-export (already checked out in this worktree — verify with `git branch --show-current` before changing anything)

Footprint (from the plan, repeated here as the hard boundary):
- engine/draft_state.py: `pick_log()`
- engine/tests/test_draft_state.py: `pick_log` tests, using the existing fixture as is
- server/results.py (new): `require_complete`, `results_csv`, `results_text`
- server/main.py: the routes `GET /session/{session_id}/results.csv` and `/results.txt`, registered above the catch-all, plus the import
- server/tests/test_results.py (new)
- client/src/api.js: `resultsCsvUrl(id)`, `getResultsText(id)`
- client/src/pages/Draft.jsx: the Results block
- work/results-export/notes.md: your notes

Key constraints:
- Engine rules change only in `engine/`. The overall pick order comes from `DraftState.pick_log()`. `server/results.py` must not re-derive turn order. Leave the client's existing `buildLog` alone.
- Do not touch `server/session_manager.py`, `host.sh`, `app/`, `ARCHI.md`, `PLAN.md`, `client/src/hooks/`, or `client/scripts/e2e-drive.mjs`. If you think one needs to change, stop and say so in your summary instead.
- Results are only available when the draft is complete: raise the existing `NotReady` (409) otherwise, and let `manager.get` give 404 for an unknown room.
- The Discord text format is exact, as specified in the plan:
  - the header `**<Label> draft — <CODE>**`;
  - then one line per team in slot order: `**<team>** (<left> left): Name Tier, …`, with `Unranked` → `U`;
  - team names escaped for `* _ ~ \` | \ @`.
- CSV: the header `pick,round,team,pokemon,slug,tier,cost`, using `csv` with `lineterminator="\n"`. A team cell starting with `= + - @` gets a leading `'`. Send `Content-Disposition: attachment; filename="draft_<format>_<CODE>.csv"`.
- In the server tests, build completed rooms directly, as the plan describes: `DraftPool` + `_apply_overrides` + `DraftState` + `state.pick`, then a `Session(..., started=True, ...)` inserted into a monkeypatched manager's `_sessions`, with `manager.save(session)` before the restart test. Existing tests in `test_backend.py`, `test_persistence.py` and `test_static.py` stay unchanged and must pass.
- Draft.jsx:
  - Put every new hook above `DraftBoard`'s `if (!state) return …` early return.
  - Key the fetch effect on `state?.complete`, with an `active` flag in its cleanup, and clear the text when the draft isn't complete.
  - Use a second, separate `useCopy()` instance and a local `resultsError`.
  - Put no `fetch`/`await` inside the copy click handler.
  - Show the block to every player, not only the host.
- Your sandbox can't bind ports, and committing may fail. Don't attempt the browser criteria; the Orchestrator runs those. Do run `python3 -m pytest engine server -q` and `scripts/gate.sh`. If `git commit` fails on `index.lock`, leave the changes uncommitted and say so.

When done:
1. Run scripts/gate.sh from the repo root — it must pass.
2. Commit your work on this branch with a clear message (or report that the sandbox blocked it).
3. Print a final summary: what changed and why, criteria partially met (if any), out-of-scope observations.
