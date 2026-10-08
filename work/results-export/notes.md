# Results export implementation

- `DraftState.pick_log()` walks existing engine turn order and supplies both CSV ordering and costs.
- The backend rejects lobby and unfinished rooms with `NotReady`; completed rooms, including restored rooms, export CSV and Discord text.
- The Draft sidebar loads Discord text when completion changes, guards against stale responses, and gives each player a copy button and CSV link.
- Browser checks remain with the Orchestrator as assigned in the handoff.
- Local test commands use Conda Python on `PATH` and a temporary `sitecustomize.py` that skips a crashing macOS `readline` import in pytest. No repo files are changed for this workaround.

## Browser check (Orchestrator, 2026-10-08)

Ad-hoc Playwright run over CDP: headless Chrome, two `browser.newContext()` contexts (Alpha = host, Bravo), same-origin client build (`VITE_API_URL=`), uvicorn on 127.0.0.1:8011 with no `DRAFT_SESSIONS_DIR`. Room: AAA, 2 teams, snake, roster 2, random pool of 20. Picks were made by clicking cards in each player's page. Result: **11/11 PASS**.

- No Results block for either player before the last pick. After pick 4, both see it, enabled.
- Bravo (non-host) clicked **Copy results for Discord**. `navigator.clipboard.readText()` (clipboard permissions granted to the context) returned:
  ```
  **AAA draft — MA5ZW7**
  **Alpha** (48 left): Scream Tail A-, Kommo O C
  **Bravo** (51 left): Mamoswine B-, Deoxys Defense C
  ```
- The **Download CSV** link's `href` is `/session/MA5ZW7/results.csv`. `curl -sD-` showed `content-disposition: attachment; filename="draft_aaa_MA5ZW7.csv"` and the header plus 4 rows in snake order (Alpha, Bravo, Bravo, Alpha) with tier costs 8/5/4/4.
- The host clicked **Undo last pick**, and the Results block disappeared for both players.
