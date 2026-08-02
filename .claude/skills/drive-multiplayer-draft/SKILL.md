---
name: drive-multiplayer-draft
description: Launch and browser-drive the Phase 3 multiplayer draft (FastAPI server/ + React client/) end-to-end in real Chrome — create a room, join two players, start, pick, and verify the live broadcast. Use to confirm the multiplayer UI actually works, not just the tests.
---

# Drive the multiplayer draft in a real browser

Runs the whole stack and walks a two-player lobby → draft → pick flow through
**real Chrome**, asserting the live WebSocket broadcast reaches the client that
never clicked. Backend and engine are covered by `pytest`; this covers the
rendered React app that tests can't.

## What it needs (all already true in this repo)

- **Google Chrome** at `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` (macOS).
  On another OS, point `$CHROME` at any Chrome/Chromium binary.
- **Node** via nvm: `export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"` (node is not on PATH otherwise).
- **Python deps**: `pip install -r requirements.txt` (fastapi, uvicorn, …).
- **Client deps**: `cd client && npm install` — includes `playwright-core`
  (the driver connects to Chrome over CDP; **no browser download**).

## Run it

One block: start backend + Vite + headless Chrome, run the driver, tear down.

```bash
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh" >/dev/null 2>&1
ROOT=/Users/cboyfly/Documents/repos/pokemon-draft-tool
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SHOT_DIR="${SHOT_DIR:-/tmp}"

cd "$ROOT"
python3 -m uvicorn server.main:app --port 8000 >/tmp/uv_drive.log 2>&1 & UV=$!
( cd client && npm run dev -- --port 5173 >/tmp/vite_drive.log 2>&1 ) & VITE=$!
rm -rf /tmp/chrome-drive
"$CHROME" --headless=new --disable-gpu --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-drive about:blank >/tmp/chrome_drive.log 2>&1 & CHR=$!

# wait for all three to answer
for i in $(seq 1 40); do curl -sf http://127.0.0.1:8000/health      >/dev/null 2>&1 && break; sleep 0.3; done
for i in $(seq 1 40); do curl -sf http://127.0.0.1:5173/            >/dev/null 2>&1 && break; sleep 0.3; done
for i in $(seq 1 40); do curl -sf http://127.0.0.1:9222/json/version >/dev/null 2>&1 && break; sleep 0.3; done

SHOT_DIR="$SHOT_DIR" npm --prefix client run e2e:browser
RC=$?

kill $UV $VITE $CHR 2>/dev/null
echo "exit=$RC   screenshots in $SHOT_DIR/draft_A.png, draft_B.png"
```

The driver lives at `client/scripts/e2e-drive.mjs` and is parameterized by
`APP_URL` (default `http://localhost:5173`), `CDP_URL` (default
`http://127.0.0.1:9222`), and `SHOT_DIR`.

## What a pass looks like

Expected stdout ends with `DRIVE OK` and `exit=0`. It logs each step:
room created → Alpha joins (host) → Bravo joins → Start enabled → both reach
`/draft` → Alpha on the clock → Alpha drafts a card → **B's pick history
populates (broadcast proof)** → both boards advance to Bravo.

**Then look at the screenshots** (`draft_A.png`, `draft_B.png`) — a blank frame
is a failed launch. You should see the dark board, sprites, canonical type/tier
badges, a `TAKEN` overlay on the drafted mon, and the "ON THE CLOCK" bar.

## Gotchas already handled in the driver

- `element.innerText` returns CSS-**transformed** text: "On the clock" rendered
  with `text-transform:uppercase` reads back as "ON THE CLOCK". Match
  case-insensitively.
- `page.waitForFunction(fn, arg, opts)` — the **2nd** arg is the function
  argument, not options; pass `undefined` to reach `opts`.
- Node's `WebSocket` (if you script the wire directly instead of the browser)
  drops messages arriving between listener attaches; the browser's persistent
  `onmessage` does not. That's why this drives the real UI.

## Backend-only wire test (faster, no browser)

For the REST + WebSocket contract without a browser, the acceptance suite is
`pytest server/tests` (uses FastAPI `TestClient`).
