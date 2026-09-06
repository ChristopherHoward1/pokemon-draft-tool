# Pokémon Draft Tool

A tool for running live Pokémon draft leagues in the **AAA** and **Pokébilities**
formats. Build a draft pool, give each team a points budget, and pick Pokémon in
turn — with tier-based costs, type/tier filters, and a live board.

It comes in **two flavors**, both built on the same draft engine:

| | **Single-screen (Streamlit)** | **Multiplayer (web app)** |
|---|---|---|
| Who looks where | Everyone shares **one screen** | **One browser per player** |
| Best for | In-person drafts, or one host driving on a stream | Remote drafts over Discord — each player picks from their own device |
| How players pick | The host clicks for the current team | Each player clicks on their own turn; it's locked to whoever's turn it is |
| Team names | Host types them up front | Each player names their own team when they join |
| Setup | `streamlit run app/streamlit_app.py` | A backend + a frontend (see below) |

New to the project? The single-screen mode is the quickest way to see a draft
run. The multiplayer mode is the one you'd use for a real remote league night.

---

## Draft concepts (shared by both modes)

These are the same no matter which mode you run.

- **Formats** — **AAA** and **Pokébilities**, each with its own roster and Smogon
  Viability Ranking (VR) tiers. AAA has 356 Pokémon (81 VR-ranked, 275 unranked);
  Pokébilities has 309 (79 ranked, 230 unranked).
- **The pool** — you don't draft from every Pokémon in the format; you first
  generate a smaller **pool** to draft from. Three ways to build it:
  - **Full Random** — draw *N* Pokémon at random from the format.
  - **VR-Weighted** — choose how many VR-ranked vs. unranked Pokémon appear.
  - **Stratified** — set an exact count per tier band (S, A, B, C, D, Unranked),
    so no band is over- or under-represented.
- **Budget & tier costs** — every team gets a points budget (default **60**).
  Each Pokémon costs points based on its VR tier — stronger tiers cost more
  (S = 11 down to Unranked = 2). You can't pick a Pokémon you can't afford. Costs
  and the budget live in `config/draft_config.yaml`.
- **Rosters** — each team drafts a fixed number of Pokémon (default **10**).
- **Draft order** — **snake** (order reverses each round: 1-2-3-3-2-1-…) or
  **linear** (same order every round: 1-2-3-1-2-3-…). Snake is the usual choice —
  it evens out the advantage of picking first.
- **Undo** — reverses the **most recent pick only** (a single step). Once a pick
  is undone, or a new pick is made, earlier picks can't be undone.

> **Pool size vs. the format.** You can only draft as many Pokémon as the format
> actually has. If you ask for more than exists — say 100 VR-ranked when AAA has
> 81 — you'll get a clear error telling you the maximum, rather than a broken
> draft. Just lower the number. Also make sure the pool is at least
> `teams × roster size` (e.g. 4 teams × 10 picks = 40), or there won't be enough
> Pokémon to fill every roster.

---

## Requirements

- **Python 3.10+** — for the engine, the Streamlit app, and the multiplayer backend.
  ```
  pip install -r requirements.txt
  ```
- **Node.js 18+** — only for the multiplayer frontend (`client/`).

---

## Mode A — Single-screen draft (Streamlit)

Everyone gathers around one screen; the host drives.

```
streamlit run app/streamlit_app.py
```

Open `http://localhost:8501`.

**Setup screen**
1. Choose a format (AAA or Pokébilities).
2. Set the number of teams (2–8) and type each team name.
3. Choose a pool generation mode and its size.
4. Click **Confirm and generate pool**.

**Draft board**
- **Left sidebar** — current team, pick number, remaining budget, **Undo last
  pick**, **Export draft JSON** (writes `exports/draft_<format>_<timestamp>.json`),
  a scrollable pick history, and **Reset draft** (returns to setup).
- **Main grid** — every pool Pokémon sorted by cost (highest first) then name.
  Filter by name, type, or tier. Click **Draft** to pick for the current team;
  invalid picks show an inline reason. Drafted Pokémon stay visible with a
  **TAKEN** marker.
- **Team Rosters** — one tab per team with sprite, name, tier, and cost per pick.

---

## Mode B — Multiplayer draft (web app)

A real-time draft where **each player uses their own browser**. A Python backend
(`server/`) holds the shared draft state and pushes every pick to all players
over WebSockets; a React frontend (`client/`) is what players actually see.

### Run it locally

Two terminals:

```
# 1) Backend — from the repo root
uvicorn server.main:app --reload --port 8000

# 2) Frontend — from client/
cd client
npm install
npm run dev
```

Then open `http://localhost:5173`.

### The draft flow

1. **Host** opens the app, configures the draft (format, number of teams, budget,
   draft order, pool), and clicks **Create draft room**. They get a **6-character
   room code** (e.g. `DRFT4X`).
2. The host shares that code (e.g. in Discord). Everyone — including the host —
   opens the app, enters the code, and **types their own team name** to join.
   **The order players join is the draft order: the first to join picks first.**
3. Once every slot is filled, the **host** (the first to join) clicks **Start
   Draft**, and everyone's screen jumps to the live board together.
4. On your turn, click a Pokémon to draft it. It's **not your turn** → cards
   aren't clickable, and the active team is highlighted. Every pick updates all
   players' boards instantly. A big **"On the clock"** banner (with a pick-reveal
   flash) makes the current pick easy to follow on a stream.

Only the host (slot 1) can use **Undo**, and — as above — it reverses just the
most recent pick.

### Notes

- **Sessions are in-memory.** If the backend restarts, active rooms are cleared.
  That's fine for a scheduled league night; just don't restart mid-draft.
- **Reconnecting.** If a player's connection drops, the client retries
  automatically and reloads the current board on reconnect.
- **Config points at the backend.** The frontend reads `VITE_API_URL` — see
  `client/.env.development` (defaults to `http://localhost:8000`) and
  `client/.env.production`. More detail in [`client/README.md`](client/README.md).

### Deploying (Render)

`render.yaml` defines two services from this one repo — the FastAPI backend and
the static frontend build. After the first deploy, point the two at each other
(`FRONTEND_URL` on the backend, `VITE_API_URL` on the frontend) and redeploy.
The file's comments walk through it. On Render's free tier the backend sleeps
after ~15 min idle and takes ~30s to wake, so open the app a minute before draft
time.

---

## Configuration

`config/draft_config.yaml` controls the budget, roster size, team-count limits,
default pool size, and per-tier point costs — shared by both modes. (In
multiplayer, the host can override the budget and roster size per room; the tier
costs always come from this file.)

```yaml
budget: 60
roster_size: 10
min_teams: 2
max_teams: 8
default_pool_size: 120

tier_costs:
  S: 11
  A+: 10
  A: 9
  A-: 8
  B+: 7
  B: 6
  B-: 5
  C+: 4
  C: 4
  D: 3
  Unranked: 2
```

---

## Project layout

```
app/
  streamlit_app.py      # Mode A — single-screen UI (setup + draft board)
server/                 # Mode B — multiplayer backend
  main.py               # FastAPI: REST + lobby/draft WebSockets, sprite serving
  session_manager.py    # in-memory rooms → engine orchestration
  models.py             # request / message shapes
  tests/                # backend acceptance tests
client/                 # Mode B — React/Vite frontend (see client/README.md)
engine/                 # shared draft logic (used by both modes)
  pool.py               # DraftPool — pool generation, available-Pokémon tracking
  draft_state.py        # DraftState — turn order (snake/linear), pick, undo, export
  validator.py          # PickResult — budget and roster validation
  tests/                # engine tests
config/
  draft_config.yaml     # budget, roster size, tier costs
data/
  aaa_pokemon.json      # format rosters with VR tiers
  pokebilities_pokemon.json
sprites/                # Pokémon sprites keyed by national dex ID
scripts/                # data pipeline (scrape → normalize → build pool → fetch sprites)
exports/                # timestamped JSON exports written by Mode A
```

The engine is the single source of truth for draft rules; both modes wrap it and
neither changes it.

---

## Tests

```
python -m pytest engine/tests server/tests   # 91 engine + 13 backend
```

(The frontend has no unit tests; it's exercised end-to-end by the
`drive-multiplayer-draft` project skill, which drives a real browser through a
full lobby → draft → pick flow.)

---

## Data pipeline

The `data/` files and `sprites/` were produced by the scripts in `scripts/`
(scrape Smogon → normalize names → build pool → fetch sprites) and are checked
in — you don't need to re-run them unless you want to refresh VR tier data.
