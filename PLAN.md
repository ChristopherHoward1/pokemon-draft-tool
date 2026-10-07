# Plan

One screen, always. Reasoning lives in work units — link, don't restate.

## Objective

Run live Pokémon draft leagues (AAA + Pokébilities) for a Discord league: a multiplayer draft room (FastAPI + React) hosted locally with `host.sh` as the main path, Render as the fallback, and the single-screen Streamlit board for in-person/streamed drafts. The engine is the one source of draft rules.

## Now

- Harness adopted (2026-10-05): gate wired (ruff, shellcheck, client build, whole-repo pytest), repo brought to ruff-clean.
- [local-host-live-draft](work/local-host-live-draft/plan.md) — reviewed 2026-10-05: `./host.sh` + cloudflared link for live Discord drafts; rejoin picker. Unit 2 picks up `deferrals.md`.

## Decisions

- 2026-10-06 — The Orchestrator runs live-server / `host.sh` scenarios outside the implementer sandbox before review (Codex cannot bind ports). See [the retro](work/local-host-live-draft/retro.md).
- 2026-10-05 — Host live drafts locally via `host.sh`; keep Render as the fallback. See [the work plan](work/local-host-live-draft/plan.md).
- 2026-10-05 — Adopted the agentic-coding harness; gate extended via `scripts/gate.d/` rather than editing `gate.sh`, so harness updates copy over cleanly.

## Risks

- `main` may auto-deploy on Render; a merged release PR ships to the live draft site.
