You are the implementer for this work unit. Read AGENTS.md in the repo root first — it is your contract.
Follow its build-discipline section while staying inside the plan footprint.

Work unit: work/sprite-delivery/plan.md  (read it in full; it is your source of truth)
Absolute plan path: /Users/cboyfly/orca/workspaces/pokemon-draft-tool/cookiecutter/work/sprite-delivery/plan.md
Branch: wt/sprite-delivery (already checked out in this worktree — verify with `git branch --show-current` before changing anything)

Footprint (from the plan, repeated here as the hard boundary):
- scripts/make_thumbnails.py (new) — idempotent 128px PNG thumbnails into sprites/thumbs/
- scripts/test_make_thumbnails.py (new) — pipeline criteria from the plan
- server/main.py — `sprite_file` only: thumbs-first lookup, Cache-Control on found sprites
- server/tests/test_static.py — add new test functions; do not modify existing ones
- client/src/components/Sprite.jsx (new) — retrying image with a fallback
- client/src/components/PokeCard.jsx, TeamRoster.jsx, OnTheClock.jsx — render through Sprite
- host.sh — run make_thumbnails.py before launch; keep tunnel logs
- ARCHI.md — the `scripts/`, `sprites/`, `server/`, `client/` bullets and the `./host.sh` entry point
- README.md — lines 239–240 and 278 only

Key constraints:
- Thumbnails: fit within 128×128, LANCZOS, RGBA preserved, PNG optimize=True, same filename under sprites/thumbs/. Sources are non-recursive `sprites/*.png`. Skip a thumbnail that exists and is at least as new as its source. Write via a temp file in sprites/thumbs/ and rename. An undecodable source logs a warning and is skipped, the rest are processed, and the script exits 1. Missing or empty sprites/ exits 0, and that check runs before Pillow is imported.
- Pipeline tests import the script as a top-level module (`import make_thumbnails as m`), following scripts/test_fetch_sprites.py. Run tests as `python3 -m pytest`.
- Server: try `SPRITES_DIR / "thumbs"`, then `SPRITES_DIR`, each through the existing `_resolve_inside` + `_is_file` guards. Found sprites (GET and HEAD) send exactly `Cache-Control: public, max-age=86400`. The 404 JSON has no Cache-Control. No 304 handling.
- Sprite.jsx props: `path`, `alt`, `width`, `height`, `className`, `loading`, `fallback`. Retry delays are exactly 1, 2, 4, 8, 30 and 60 s (6 retries, 7 attempts in total), each with ±25% jitter. Retry n requests the URL from `spriteUrl(path)` with `?retry=<n>` appended; attempt 0 has no query. While waiting and after the last failure, render `fallback` instead of the `<img>`. Clear the pending timer on unmount. A changed `path` resets the attempts. Don't change `client/src/api.js`.
- Fallbacks: PokeCard keeps its grey box (`h-14 w-14 rounded bg-border`), TeamRoster an empty `h-10 w-10 shrink-0` spacer, OnTheClock nothing. After this change `git grep -n "<img" client/src` must show only Sprite.jsx. Keep each component's existing size, `loading` and className values, and keep its alt text.
- The client has no test framework. Do not add one, or any new dependency. Pillow is already in requirements.txt.
- host.sh: read knowledge/host-sh-testing.md first (this satisfies the PLAN.md decision of 2026-10-07). The machine's bash is 3.2.57: no `wait -n`, no associative arrays, no `${var,,}`. It must stay shellcheck-clean and it runs under `set -euo pipefail`.
- host.sh thumbnails: run `python3 scripts/make_thumbnails.py` right after the sprites-missing warning at host.sh:100–102, inside an `if`. On failure print one warning that sprites will be served full-size, and continue.
- host.sh logs: before each of the two `rm -f "$tunnel_log"` calls (host.sh:51 and :85), copy the log to `$sessions_dir/tunnel-<timestamp>.log`, creating the directory if needed. Each tunnel started must get its own file, so two copies in the same second must not overwrite each other. Copying is best-effort and must never change the exit status or abort under `set -e`. It must not print shutdown noise.
- Do not touch data/*.json, app/streamlit_app.py, scripts/fetch_sprites.py, client/src/api.js, engine/, or server/session_manager.py.
- sprites/ is gitignored and was copied into this worktree with `cp -R`. Never commit it and never replace it with a symlink. Scaffolding and stubs live in a scratch temp dir, never in the repo.
- Your sandbox may not be able to bind ports or run host.sh or browser scenarios. If it can't, say so in your summary; the Orchestrator runs them afterwards (PLAN.md decisions of 2026-10-06; see knowledge/host-sh-testing.md). Do not mark those criteria as met unless you actually ran them.

Context: the Orchestrator's baseline burst on the unmodified code (732 sprite requests through a real quick tunnel) returned 200 × 200, 330 × 429 and 202 × 502. The 502s were cloudflared getting `connection reset by peer` from uvicorn. Treat these as failures the retry must recover from; do not widen the footprint to tune uvicorn.

When done:
1. Run scripts/gate.sh from the repo root — it must pass.
2. Commit your work on this branch with a clear message.
3. Print a final summary: what changed and why, criteria partially met (if any), out-of-scope observations.
