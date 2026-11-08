# Make sprites load reliably over the tunnel

**Slug:** sprite-delivery · **Date:** 2026-11-08 · **Status:** approved

## Goal

During a live draft hosted through the `host.sh` Cloudflare quick tunnel, sprites showed grey boxes that stayed (Owner-reported). It isn't missing data: all 356 AAA and 294 Pokébilities entries point to a file that exists and isn't truncated. Checked against `origin/main` at caeb67b:

1. **A single failure is permanent.** `PokeCard.jsx:55` sets `imgError` on the first error with no retry. `TeamRoster.jsx:13` and `OnTheClock.jsx:63` hide the image the same way.
2. **The files are oversized.** Every sprite is 475×475 official artwork: 48.4 MB across 366 files, median 132 KB. They display at 64px or smaller, and each player downloads them through the host's uplink and the tunnel. A room shows 120 cards by default (`config/draft_config.yaml`).
3. **Caching is weak.** `server/main.py:301` returns `FileResponse(requested)`, which sends no `Cache-Control`. It also answers `If-None-Match` with a full 200, never a 304.

Why requests fail on the tunnel is unconfirmed: no draft logs exist because `host.sh` deletes its tunnel log. The working hypothesis is the quick tunnel's in-flight request cap (about 200, 429 above it, from memory). The fix doesn't depend on it: smaller cached files mean fewer and shorter requests, and retries recover failures that last up to about 80 s. An outage longer than that still leaves grey boxes until a reload, which is an accepted limitation. `host.sh` now keeps the tunnel log, so a recurrence leaves some evidence.

Done = a sprite failure lasting up to about 80 s heals itself without a reload, the sprite bytes a player downloads drop by more than 80%, and a host with no thumbnails still gets full-size sprites with hosting unaffected.

## Approach

**Thumbnails: `scripts/make_thumbnails.py` (new, with sibling `scripts/test_make_thumbnails.py`).**
- For each `sprites/*.png` (non-recursive), write `sprites/thumbs/<same name>.png`, fitted within 128×128 with LANCZOS, RGBA preserved, PNG `optimize=True`.
- 128px covers the largest 64 CSS px slot at 2× DPR. Measured on the real set: 6.46 MB total, median 17.6 KB, 2.7 s for all 366 files.
- Idempotent: skip a thumbnail that exists and is at least as new as its source. Write through a temp file in `sprites/thumbs/` and rename, so an interrupted run can't leave a truncated PNG.
- A source that can't be decoded logs a warning and is skipped. The script processes the rest and exits 1 if any failed. No `sprites/` directory, or an empty one, is a no-op with exit 0, so `host.sh`'s existing warning stays the single message for that case. This check runs before Pillow is imported, so a machine with neither sprites nor Pillow doesn't get a second, misleading warning.
- Alternatives rejected: WebP (2.17 MB, but 131 s to encode and it renames every file away from the `sprite_path` in `data/*.json`); shrinking originals in place (destructive: they're the only full-size copy and restoring them needs a re-download); changing `sprite_path` (rewrites pipeline output for no benefit).

**Server: `sprite_file` in `server/main.py`.**
- Look in `SPRITES_DIR / "thumbs"` first, then `SPRITES_DIR`, each through the existing `_resolve_inside` + `_is_file` guards. `sprite_path` values, the URL and the client's URL logic don't change. With no thumbnails, the original file is served as it is today, plus the cache header below.
- Successful GET and HEAD responses add `Cache-Control: public, max-age=86400`. A day covers a draft and keeps the staleness window short. The 404 JSON gets no cache header, so a miss is never cached.
- No 304 handling. With a fresh `max-age` the browser doesn't revalidate during a draft, so it isn't worth hand-rolling on top of `FileResponse`.

**Client: new `client/src/components/Sprite.jsx`, used by all three components.**
- Props: `path`, `alt`, `width`, `height`, `className`, `loading`, `fallback`.
- On `onError`, retry up to 6 times after 1, 2, 4, 8, 30 and 60 s, each with ±25% jitter so players don't retry in lockstep. That's 7 attempts over roughly 80–130 s. The slow tail is there because the cause is unconfirmed and a 15 s budget would reproduce the reported symptom on any longer stall. A retry appends `?retry=<n>` so the browser really refetches. The server ignores the query.
- While waiting and after the last failure, render `fallback` rather than the `<img>`, so no broken-image icon ever shows. A sprite that recovers replaces it. Clear the pending timer on unmount. A changed `path` resets the attempts.
- Fallbacks preserve today's look: `PokeCard` passes its grey box, `TeamRoster` an empty `h-10 w-10 shrink-0` spacer (today's `visibility: hidden` keeps layout), `OnTheClock` nothing.
- Accepted cost: if sprites are absent entirely (Render fallback), each card makes 7 requests over about 2 minutes instead of 1, and shows the same grey box throughout. `<img>` can't see the status code, and those 404s are small JSON.

**`host.sh`.** Right after the sprites-missing warning (`host.sh:100–102`), run `python3 scripts/make_thumbnails.py`. A failure, including Pillow being absent, prints one warning that sprites will be served full-size, and hosting continues. The call must be inside an `if`, because the script runs under `set -e`.

Also in `host.sh`, keep the tunnel log. Before each of the two `rm -f "$tunnel_log"` calls (`host.sh:51` and `:85`), copy the log to `$sessions_dir/tunnel-<timestamp>.log`. Copying is best-effort and never fails the script. `sessions/` is gitignored and session restore only reads `*.json` (`session_manager.py:229`). Edge-side 429s may not reach cloudflared's log at all, so this captures tunnel and origin errors, not necessarily the cap.

Bash 3.2 per [knowledge/host-sh-testing.md](../../knowledge/host-sh-testing.md).

**Docs.** `ARCHI.md`: the `scripts/` and `sprites/` bullets (`make_thumbnails.py`, `sprites/thumbs/`), the `server/` bullet (thumbnail-first lookup, cache header), the `client/` bullet (`Sprite.jsx` retry), and the `./host.sh` entry point (makes thumbnails, keeps tunnel logs). `README.md` lines 239–240 and 278 (`host.sh` makes thumbnails; a manual run is only needed for `./dev.sh`).

Out of scope: 304 support, a concurrency limiter on the client, `image-rendering: pixelated`.

## Footprint

Files to modify:
- `scripts/make_thumbnails.py` (new)
- `scripts/test_make_thumbnails.py` (new)
- `server/main.py`
- `server/tests/test_static.py`
- `client/src/components/Sprite.jsx` (new)
- `client/src/components/PokeCard.jsx`
- `client/src/components/TeamRoster.jsx`
- `client/src/components/OnTheClock.jsx`
- `host.sh`
- `ARCHI.md`
- `README.md`

Files NOT to touch:
- `data/*.json` — `sprite_path` stays as it is.
- `app/streamlit_app.py` — keeps reading originals from disk.
- `scripts/fetch_sprites.py` — downloading stays separate from resizing.
- `client/src/api.js` — `spriteUrl` is unchanged.

## Acceptance criteria

Pipeline (pytest, in `scripts/test_make_thumbnails.py`):
- [ ] A 475×475 RGBA source yields a thumbnail in `thumbs/` no larger than 128×128 that still has an alpha channel.
- [ ] A second run doesn't rewrite an up-to-date thumbnail (mtime unchanged). A source newer than its thumbnail is regenerated.
- [ ] An undecodable source is skipped, the others still get thumbnails, and the script exits 1. Nothing partial is left in `thumbs/`.
- [ ] A missing or empty `sprites/` exits 0, including when Pillow can't be imported.
- [ ] On the real set, the summed `st_size` of `sprites/thumbs/*.png` divided by that of `sprites/*.png` is below 0.20 (Orchestrator-run; `sprites/` isn't available to pytest).

Server (pytest, in `server/tests/test_static.py`):
- [ ] `/sprites/a.png` serves `thumbs/a.png` when both exist, and the original when there is no thumbnail.
- [ ] GET and HEAD on a found sprite return `Cache-Control: public, max-age=86400`. A missing sprite returns the 404 JSON with no `Cache-Control`.
- [ ] `/sprites/..%2Fsecret` still returns 404 with `thumbs/` present, and every existing test in `test_static.py` still passes.
- [ ] `/sprites/a.png?retry=2` returns the same body as `/sprites/a.png`.

Host and client (diff inspection and Orchestrator-run, per the 2026-10-06 decisions):
- [ ] `PokeCard`, `TeamRoster` and `OnTheClock` render through `Sprite`. `git grep -n "<img" client/src` shows only `Sprite.jsx`.
- [ ] Fault injection, recovery: with Playwright `page.route` aborting the first 2 requests per `URL.pathname` (query ignored, so `?retry=n` counts against the same sprite), all cards in view end with `naturalWidth > 0` and no grey box, with no reload. The same check against the `origin/main` client leaves grey boxes.
- [ ] Fault injection, exhaustion: aborting every `/sprites/` request, each card in view makes exactly 7 attempts for its pathname, then shows the grey box. Throughout, an in-page sampler every 100 ms never finds the same `<img>` with `complete && naturalWidth === 0` on two consecutive samples.
- [ ] Real run: on the live server, a decoded sprite response is at most 128×128 and carries the cache header. `getBoundingClientRect` reports 64 px for a pool sprite, 40 px for a roster sprite and 48 px for the pick-flash sprite. The pick flash shows for only 3.2 s, so the script makes a pick and reads `.animate-pickflash img` with `waitForSelector` straight away.
- [ ] `host.sh` with stubbed cloudflared: `sprites/thumbs/` is created before the server starts and the run reaches a share link. With a corrupt `sprites/bad.png` temporarily in place to force exit 1, it prints the warning and still reaches a share link. That second scenario fails against a copy without the `if` guard.
- [ ] `host.sh` with stubbed cloudflared: after a shutdown, and after a `STUB_MODE=restart` tunnel restart, a `tunnel-*.log` holding the stub's output exists in `DRAFT_SESSIONS_DIR` for each tunnel started. An unwritable `DRAFT_SESSIONS_DIR` for the copy step doesn't change the exit status.

## Release

Release note: Sprites stop turning into permanent grey boxes on draft night — images are about 85% smaller, cached by the browser, and failed loads retry on their own.

## Verification

- `python3 -m pytest -q scripts/test_make_thumbnails.py server/tests/test_static.py`
- **Sprites in the worktree.** `sprites/` is gitignored and a fresh worktree has none. Copy the originals in with `cp -R`, never a symlink, which would write `thumbs/` into another checkout. Without this the thumbnail, browser and `host.sh` criteria can't pass.
- `python3 scripts/make_thumbnails.py`, then sum `st_size` for the ratio criterion. Don't use `du`, which counts disk blocks.
- Host scenarios per [knowledge/host-sh-testing.md](../../knowledge/host-sh-testing.md), run by the Orchestrator outside the implementer sandbox. Check by hand for bash 3.2 compatibility.
- Browser criteria run from a scratch Playwright script over CDP against the worktree's production build served by uvicorn. Don't use `drive-multiplayer-draft` for these: it hardcodes the primary checkout, runs Vite dev and has no `page.route`. Scratch files stay out of the repo.
- Burst test, only with the Owner's go-ahead since it opens a public link: fire parallel sprite requests through a real quick tunnel before and after, and count non-200s. It tests the unconfirmed hypothesis and isn't a release criterion. Owner decision: approved (2026-11-08).

## Review

Round 1 (`plan-reviewer`, fresh thread, against `origin/main` at caeb67b): **REVISE**, 10 findings. Its factual checks of the line numbers, data coverage, sizes and `FileResponse` behaviour all passed. All 10 applied, no disagreements:

1. Retry budget too short for an unconfirmed cause → added 30 s and 60 s retries (7 attempts) and narrowed Done to about 80 s, with longer outages an accepted limitation.
2. No tunnel evidence → `host.sh` keeps the tunnel log; burst test put to the Owner before implementation.
3. Verification environment unspecified → `cp -R` sprites into the worktree; scratch CDP script against the production build.
4. ">80% bytes" had no criterion → `st_size` ratio below 0.20.
5. Done contradicted the Approach → reworded.
6. Recovery injection ambiguous → counter per `URL.pathname`.
7. Two browser criteria uncheckable → `getBoundingClientRect` values, pick-flash capture, two-sample broken-image check.
8. `host.sh` failure injection unnamed, and a double warning with no Pillow → corrupt `bad.png`; no-op check runs before the Pillow import.
9. Docs footprint understated → listed by `ARCHI.md` section.
10. `TeamRoster` spacer could be squeezed → `shrink-0`.

The revised plan has not had a second review round.

Owner approval (2026-11-08): approved the plan as revised over the round 1 REVISE, with all 10 findings applied and no second review round; also approved the burst test through a real quick tunnel.
Plan verdict: APPROVE
