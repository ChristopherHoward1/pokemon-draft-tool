# Multiplayer frontend (`client/`)

The React + Vite web app for **Mode B — Multiplayer draft**. It's a thin,
real-time UI over the backend in `server/`; all draft rules live in the Python
`engine/`. See the [root README](../README.md) for the overall project and how to
run a draft.

## Prerequisites

- Node.js 18+
- The backend running on port 8000

The easiest way to get both is `./dev.sh` from the repo root — it starts the
backend and this dev server together (and installs deps on first run). The steps
below are for running the frontend on its own against an already-running backend.

## Develop

```
npm install
npm run dev        # Vite dev server on http://localhost:5173
```

In dev the app runs same-origin: the Vite dev server proxies `/session`
(WebSockets included), `/sprites`, and `/health` to the backend on port 8000
(see `vite.config.js`), so no `VITE_API_URL` is needed.

## Build for production

```
npm run build      # outputs static files to dist/
npm run preview    # serve the production build locally
```

## Configuration

In **dev**, `VITE_API_URL` is unset and the app runs same-origin, relying on the
Vite proxy (see above) to reach the backend.

In **production**, the app talks to the backend at `VITE_API_URL` (WebSocket URLs
are derived from it — `http://` → `ws://`, `https://` → `wss://`). Vite loads it
from `.env.production`, used by `npm run build`. It is baked in **at build time**,
so set it to your deployed backend URL *before* building for deployment.

## Structure

```
src/
  pages/       Setup (host) · Lobby (join + name your team) · Draft (live board)
  components/  PokeCard · TeamRoster · OnTheClock · type/tier/points badges
  hooks/       useDraftSocket · useLobbySocket  (auto-reconnecting WebSockets)
  api.js       REST helpers + API/WS URL derivation
  constants.js canonical Pokémon type & tier colors
scripts/
  e2e-drive.mjs  browser end-to-end driver (see below)
```

## End-to-end browser test

`npm run e2e:browser` drives a full two-player lobby → draft → pick flow through
real Chrome, asserting the live broadcast reaches a player who never clicked. It
connects to an already-running Chrome over the DevTools Protocol (via
`playwright-core` — no browser download). The repo's `drive-multiplayer-draft`
skill documents the full launch/teardown; in short, you need the backend, the
Vite dev server, and a Chrome started with `--remote-debugging-port=9222` all
running, then run the script.
