# Export results from a finished multiplayer draft

**Slug:** results-export · **Date:** 2026-10-08 · **Status:** implemented

## Goal

A finished multiplayer draft has no way out of the browser. Only the Streamlit app (Mode A) writes `exports/draft_<format>_<ts>.json`. After a Discord league draft, someone has to retype every roster into the league channel and the league spreadsheet by hand.

Done = once a room's draft is complete, **every player** sees two controls on the Draft page:

- **Copy results for Discord**: copies a compact, paste-ready text block. It has one line per team, in slot order: the team name, points left, and the picks in order with tier.
- **Download CSV**: downloads one row per pick, in overall pick order.

Both are served by the backend, so the text and the CSV come from the same engine data. They also work for a finished room restored from `sessions/` after a restart. That is why draft-persistence keeps finished rooms (`work/draft-persistence/plan.md`, "No expiry or cleanup").

Owner decisions (2026-10-08): the formats are Discord text and CSV, with no JSON. Access is anyone in the room, and only once the draft is complete.

## Approach

**Engine (`engine/draft_state.py`).** Overall pick order is a turn-order rule, so it lives in the engine.

- Add `DraftState.pick_log() -> list[dict]`. For each `t` in `range(_total_picks())`, take `team = _team_at(t)` and that team's roster entry at index `t // n`. It returns `{"pick": t + 1, "round": t // n + 1, "team": team.name, "entry": entry, "cost": pool.tier_cost(entry["vr_tier"])}`.
- This is the same walk that `restore` already does. The client's `buildLog` in `Draft.jsx` duplicates it, and it stays as is (out of scope, see below).

**Server: new `server/results.py`.** It holds pure formatting functions plus one guard.

- `require_complete(session) -> DraftState` raises `NotReady` when the room hasn't started (`session.state is None`) or `not state.is_complete()`. The existing handler then maps that to 409 `{"reason": …}`.
- `results_csv(session) -> str`: `csv` module with `lineterminator="\n"`. The header is `pick,round,team,pokemon,slug,tier,cost`. `pokemon` is `display_name` and `slug` is `name`. The `csv` module handles quoting, so a team name with a comma or a quote stays one cell. A `team` cell starting with `=`, `+`, `-` or `@` gets a leading `'`, so Sheets and Excel don't read it as a formula (the league spreadsheet is a destination).
- `results_text(session) -> str`: the Discord text. It is compact so that a full room fits in one message (Review, finding 1):

  ```
  **AAA draft — ABC234**
  **Team A** (3 left): Garchomp A, Rotom-Wash B+, Pikachu U, …
  **Team B** (0 left): …
  ```

  - There is one line per team, in slot order. Picks come in that team's pick order, as `display_name` plus tier, with `Unranked` written as `U`. Every other tier string stays as it is.
  - The format label comes from a small dict here (`aaa` → `AAA`, `pokebilities` → `Pokébilities`), matching the client's `FORMATS` labels.
  - Markdown characters and `@` in team names (`*`, `_`, `~`, `` ` ``, `|`, `\`, `@`) are escaped with a backslash. A name like `*Mew*` then can't break the bold markup, and `@everyone` can't ping the league channel.
  - Discord's 2000-character limit: an 8 × 10 AAA room drafting the 80 longest real `display_name`s, with 40-char team names (the `JoinRequest` max) and no markdown characters in them, must come out under 2000 characters. The reviewer measured this format at 1852. Larger custom rooms (roster up to 30), or team names full of escaped markdown characters, may go over. Discord then offers to send the text as a file, which is acceptable; splitting is out of scope.

**Server: `server/main.py`.** Two GET routes, registered next to `/session/{session_id}/state`, so above the catch-all:

- `GET /session/{session_id}/results.csv` returns `text/csv; charset=utf-8` with `Content-Disposition: attachment; filename="draft_<format>_<CODE>.csv"`.
- `GET /session/{session_id}/results.txt` returns `text/plain; charset=utf-8`.
- Both call `manager.get` (404 for an unknown room), then the `results.py` function (409 for a room that isn't complete). They take no lock: formatting never awaits, so it can't interleave with a pick.

**Client.**

- `client/src/api.js`:
  - `resultsCsvUrl(id)` returns `${API_URL}/session/${id}/results.csv`.
  - `getResultsText(id)` fetches `.txt` and returns `resp.text()`. It reuses `request`'s error handling by making `request` take a parse option, or by sharing the error-body logic; either way the JSON helpers keep their behavior.
- `client/src/pages/Draft.jsx`: when `state.complete` is true, the sidebar shows a "Results" block for every player (not host-gated), placed above the pick history:
  - **Copy results for Discord**:
    - All new hooks go **above** `DraftBoard`'s `if (!state) return …` early return: the `useState`s for the text and `resultsError`, the results effect, and the second `useCopy`. Below it, they crash with React's "Rendered more hooks" error, which `vite build` can't catch.
    - An effect keyed on `state?.complete` fetches the text when it is true, so it does nothing while `state` is null. When `state.complete` is false (e.g. after a host undo), it clears the text instead.
    - The effect uses an `active` flag cleared in its cleanup, the same pattern as the existing `getSession` effect, so a stale response can't overwrite newer text.
    - Clicking copies the already-loaded text, with no `await fetch` inside the click. Otherwise Safari drops the user gesture and the clipboard write fails.
    - The copy uses its **own** `useCopy()` instance. The existing one belongs to "Copy draft link" and would flash "Link copied!" on that button.
    - The button is disabled until the text loads. A fetch failure sets a local `resultsError` state, rendered in the same style as the socket `error` box. That `error` comes from `useDraftSocket` and has no setter.
  - **Download CSV**: an `<a href={resultsCsvUrl(code)} download>` styled as a button. The server's `Content-Disposition` sets the filename, including on the cross-origin Render fallback, where the browser ignores the `download` attribute.

Alternatives considered:
- Build the text and CSV in the client from `state`. Rejected: it would grow the client's copy of the turn-order rule (`buildLog`), and the server side can be tested with pytest; the client has no unit tests.
- One route with `?format=`. Rejected: separate `.csv` / `.txt` paths make the download link and the filename simpler.

## Footprint

Files to modify:
- `engine/draft_state.py`: `pick_log()`.
- `engine/tests/test_draft_state.py`: `pick_log` tests.
- `server/results.py` (new).
- `server/main.py`: two routes and an import.
- `server/tests/test_results.py` (new).
- `client/src/api.js`
- `client/src/pages/Draft.jsx`

Files NOT to touch:
- `server/session_manager.py`: the snapshot format and save/restore stay as they are. Restored rooms must work unchanged.
- `host.sh`: nothing here needs it.
- `app/streamlit_app.py`: Mode A export stays as it is.
- `buildLog` in `Draft.jsx`: replacing it with server `pick_log` data is a separate cleanup.

## Acceptance criteria

Engine (pytest, using the existing fixture in `engine/tests/test_draft_state.py` as is: 6 Pokémon, budget 20, roster 2; a 3-team × 2-round draft uses all six and stays within budget):
- [ ] `pick_log()` on a 3-team snake draft with 2 full rounds returns 6 entries, with `pick` 1–6, `round` 1,1,1,2,2,2 and teams A,B,C,C,B,A, each with the right roster entry and `cost == tier_cost(vr_tier)`. The same check on linear order gives A,B,C,A,B,C.
- [ ] `pick_log()` on a fresh draft is `[]`. After `undo()`, it drops exactly the last pick.

Server (pytest, `TestClient`). Completed rooms are built directly, not over WebSockets:
- Build `DraftPool(format)`, apply `SessionManager._apply_overrides`, then build `DraftState`. For the length test, call `load_pool(top80)` first.
- Call `state.pick` in turn order.
- Construct the `Session` with `slots=…, started=True, pool=…, state=…` and insert it into `manager._sessions`, with the manager swapped in via `monkeypatch`. Without `started=True`, `save` writes nothing and WS messages are rejected.
- The restored-room criterion calls `manager.save(session)` before building the second manager.
- The undo criterion uses the WS undo, as `test_backend.py` does.

Server criteria:
- [ ] Unknown room: both routes return 404. A lobby room that hasn't started, and a started room that isn't complete: both return 409 with a `reason`.
- [ ] Completed 2-team room (`roster_size` 2): `results.csv` returns 200 with `text/csv` and a `Content-Disposition` filename `draft_<format>_<CODE>.csv`. Parsed with `csv.DictReader`, it has 4 rows in snake order with the header columns listed above, and each row's `cost` matches the tier cost.
- [ ] A team name containing `,` and `"` round-trips through `csv.DictReader` unchanged. A team named `=SUM(1)` comes out as `'=SUM(1)`.
- [ ] The completed room's `results.txt` returns 200 `text/plain`. Its first line is `**<Label> draft — <CODE>**`. Then there is one line per team, `**<team>** (<remaining_budget> left): ` followed by the picks in pick order as `display_name tier`, with `Unranked` → `U`. A team named `*Mew*` comes out as `\*Mew\*`, and `@everyone` as `\@everyone`.
- [ ] Length bound: a complete 8-team × 10 AAA room produces `results_text` under 2000 characters. Its 8 team names are 40 chars each, with no markdown characters, and its pool is `load_pool` of `sorted(data, key=lambda e: -len(e["display_name"]))[:80]` over `data/aaa_pokemon.json` in file order: a stable sort, so ties at the cutoff are reproducible. Those 80 fit the default budget of 60.
- [ ] Restored room: complete a room on a `SessionManager(store_dir=tmp_path)`, build a new manager on the same dir and swap it in via `monkeypatch`. Both routes return the same bodies as before the restart.
- [ ] Undo after completion: after a host WS undo, both routes return 409 again.
- [ ] The existing `test_backend.py`, `test_persistence.py` and `test_static.py` pass unchanged. In particular, `/session/<CODE>/nope` still returns 404 JSON.

Client (diff inspection + `vite build` in the gate):
- [ ] The Results block renders only when `state.complete`, with no `isHost` condition.
- [ ] The copy click handler calls `copy(text)` on pre-loaded text, with no `fetch`/`await` of the results inside the click.

Browser, run by the Orchestrator before `/4-release` (per the 2026-10-06 decision). This uses an ad-hoc Playwright script or a manual Chrome run: `client/scripts/e2e-drive.mjs` is a fixed one-pick, single-context flow and is not changed:
- [ ] Two players in separate browser contexts finish a 2-team, `roster_size` 2 draft. Neither sees the Results block before the last pick, and both see it after.
- [ ] As the non-host player:
  - Click **Copy results for Discord**. The clipboard text starts with `**AAA draft — <CODE>**`. Check it deterministically: `ctx.grantPermissions(['clipboard-read','clipboard-write'])` then `navigator.clipboard.readText()`, or an `addInitScript` stub that records the argument of `writeText`. Pasting into the search field is the fallback only.
  - The **Download CSV** link's `href` is `…/session/<CODE>/results.csv`. `curl -sD-` of that URL shows `Content-Disposition` with `draft_<format>_<CODE>.csv` and 4 data rows.
- [ ] The host clicks Undo after completion, and the Results block disappears for both players.

## Release

Release note: Finished multiplayer drafts can be exported: every player can copy a Discord-ready roster summary or download the picks as CSV.

## Verification

- `scripts/gate.sh`
- `python3 -m pytest -q engine/tests/test_draft_state.py server/tests/test_results.py`
- Browser check: the driver rules in `knowledge/host-sh-testing.md` → "Restart and rejoin" (one browser context per player, wait for each pick to land before the next) apply here. That section is on `wt/retro-draft-persistence`; rebase onto `origin/main` once that retro merges, before dispatch.

## Review

Round 1, a fresh general-purpose agent (Opus) given `.claude/agents/plan-reviewer.md` verbatim and told to stay read-only; the agent type isn't registered in sessions started from the orca parent dir (`knowledge/orca-worktree-loop.md`). Verdict: **REVISE**, 8 findings, all applied:

1. The 2000-char claim failed on real data: 2092–2364 for the old format, because 275 of 356 AAA entries are `Unranked`. Applied the reviewer's option (a): a compact one-line-per-team format with `Unranked` → `U` and a shorter header (worst case measured at 1852). The criterion now pins the team-name length and the format.
2. The length test can't be built through REST. The criteria now say to build rooms directly (`load_pool` + `state.pick` + `manager._sessions`).
3. `error` comes from `useDraftSocket` and has no setter. Draft now uses a local `resultsError`.
4. The shared `useCopy` would mislabel "Copy draft link". The Results button gets its own instance.
5. The driver has no clipboard-read or download support. The browser check now pastes into the search field and checks the CSV with `href` + `curl`, with no driver change.
6. Stale-fetch race on undo: the effect clears the text when the draft isn't complete and uses an `active` flag.
7. The engine fixture has no slack. The criterion now says to use it as is.
8. CSV formula injection: team cells starting with `= + - @` get a leading `'`.

No disagreements.
Round 2, a fresh agent set up the same way. Verdict: **APPROVE**. It confirmed every round-1 fix against the code. It re-measured the worst case at 1849–1851 characters, and built the top-80 room through the real engine with 0 invalid picks. It also made 5 wording findings, all applied without another round:

1. The test recipe was missing `started=True` and the `manager.save` call before the restart.
2. The new hooks must go above `DraftBoard`'s early return; the effect is now keyed on `state?.complete`.
3. The driver path is `client/scripts/e2e-drive.mjs`, and the driver can't run this check. The plan now uses an ad-hoc script with a deterministic clipboard check.
4. `@` is escaped so a team name can't ping the channel.
5. The "80 longest" set is pinned with a stable sort.

Plan verdict: APPROVE

Code review: round 1, both APPROVE. Claude raised 3 LOWs (no action). Codex raised one MEDIUM (a newline in a team name splits the Discord line), deferred to [deferrals.md](deferrals.md). See [review-r1.md](review-r1.md) and [codex-review.md](codex-review.md).
Code-review verdict: APPROVE
Codex-review verdict: APPROVE
