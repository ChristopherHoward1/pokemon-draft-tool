# Pokemon Draft Tool

A Streamlit app for running live Pokemon draft leagues in the **AAA** and **Pokébilities** formats. Configure teams and a draft pool, then pick Pokemon one by one in snake-draft order with a shared screen.

## Features

- **Two formats** — AAA and Pokébilities, each with their own Smogon VR tier data
- **Three pool generation modes**
  - *Full Random* — draw N Pokemon at random from the full format roster
  - *VR-Weighted* — control how many VR-ranked vs. Unranked slots appear
  - *Stratified* — set an exact count per tier group (S, A, B, C, Unranked), so no group is over- or under-represented
- **Snake draft** — 2–8 teams, 10 picks each, 60-point budget; turn order reverses each round
- **Live draft board** — sprite grid sorted by tier cost, type and tier badges, name/type/tier filters, TAKEN overlay on drafted Pokemon
- **Sidebar** — current team, pick counter, remaining budget, one-step undo, pick history log
- **Export** — saves a timestamped JSON snapshot of all rosters to `exports/`

## Requirements

Python 3.10+.

```
pip install -r requirements.txt
```

## Running

From the repo root:

```
streamlit run app/streamlit_app.py
```

Then open `http://localhost:8501` in a browser. All participants share the same browser window during a live draft.

## Setup screen

1. Choose a format (AAA or Pokébilities)
2. Set the number of teams (2–8) and enter each team name
3. Choose a pool generation mode and configure its size
4. Click **Confirm and generate pool**

The setup screen disappears once confirmed and cannot be revisited without resetting the draft.

## Draft board

**Left sidebar**
- Current team name, pick number, and remaining budget
- **Undo last pick** — reverses the most recent pick (one level only)
- **Export draft JSON** — writes `exports/draft_<format>_<timestamp>.json`
- Scrollable pick history
- **Reset draft** — returns to the setup screen

**Main grid**
- All pool Pokemon sorted by tier cost (highest first), then name
- Filter by name, type, or tier using the controls above the grid
- Click **Draft** to pick a Pokemon for the current team; failed picks show an inline error
- Drafted Pokemon remain in the grid with a disabled **TAKEN** button

**Team Rosters (tabs below grid)**
- One tab per team showing sprite, name, tier badge, and cost for each pick

## Configuration

`config/draft_config.yaml` controls the budget, roster size, team count limits, and tier point costs.

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

## Project layout

```
app/
  streamlit_app.py      # UI — setup screen and draft board
config/
  draft_config.yaml     # budget, roster size, tier costs
data/
  aaa_pokemon.json      # AAA format roster with VR tiers
  pokebilities_pokemon.json
engine/
  pool.py               # DraftPool — pool generation and available-Pokemon tracking
  draft_state.py        # DraftState — turn order, pick, undo, export
  validator.py          # PickResult — budget and roster validation
  tests/                # 88 pytest tests
exports/                # timestamped JSON exports written at runtime
scripts/                # data pipeline (scrape → normalize → build pool → fetch sprites)
sprites/                # Pokemon sprites keyed by national dex ID
```

## Data pipeline

The `data/` files and `sprites/` were produced by the scripts in `scripts/` and are checked in — no need to re-run them unless you want to refresh VR tier data from Smogon.

## Tests

```
python -m pytest engine/tests/
```
