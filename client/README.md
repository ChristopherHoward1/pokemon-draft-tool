# Multiplayer frontend (`client/`)

The React + Vite web app for **Mode B — Multiplayer draft**. It's a thin,
real-time UI over the backend in `server/`; all draft rules live in the Python
`engine/`. See the [root README](../README.md) for the overall project and how to
run a draft.

## Prerequisites

- Node.js 18+
- The backend running (`uvicorn server.main:app --port 8000` from the repo root)

## Develop

```
npm install
npm run dev        # Vite dev server on http://localhost:5173
```

## Build for production

```
npm run build      # outputs static files to dist/
npm run preview    # serve the production build locally
```

## Configuration

The app talks to the backend at `VITE_API_URL` (WebSocket URLs are derived from
it — `http://` → `ws://`, `https://` → `wss://`). Vite loads it from:

- `.env.development` — used by `npm run dev` (defaults to `http://localhost:8000`)
- `.env.production` — used by `npm run build` (set this to your deployed backend URL)

`VITE_API_URL` is baked in **at build time**, so change it *before* building for
deployment.

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
