# Notes: sprite-delivery

## Burst baseline (Orchestrator, 2026-11-08, unmodified code at caeb67b)

Every sprite twice (732 requests, 300 parallel over HTTP/2) through a real quick tunnel to uvicorn. Owner approved the temporary public link.

| Result | Count |
|---|---|
| 200 | 200 |
| 429 | 330 |
| 502 | 202 |

- Only 200 of 732 requests succeeded (27%), and the run finished in about 1 s.
- The 429s are consistent with a quick-tunnel in-flight cap of about 200.
- The 502s are a second failure mode: cloudflared logged `dial tcp 127.0.0.1:8765: connect: connection reset by peer` (312 lines, including retries) and some `write: broken pipe`. uvicorn logged no errors. `kern.ipc.somaxconn` is 128 on this machine, so a full listen queue is a likely cause but is not confirmed.

## Implementer summary (agent-exec, commit 4fb9a94)

Implemented sprite delivery on `wt/sprite-delivery`: thumbnails are generated atomically, the server serves them first with a one-day cache header, and all three client views retry failed images with their specified fallbacks. `host.sh` now generates thumbnails before launch and preserves tunnel logs. The real thumbnails are 13.3% of the original sprite bytes.

`scripts/gate.sh` and `harness gate` pass: 308 tests passed, 4 skipped. Host and browser scenarios remain unverified in the implementer sandbox. The reported uvicorn connection resets were left outside the plan's footprint.

Orchestrator gate run in the worktree: GATE: PASS (308 passed, 4 skipped).

## Demo (`harness demo sprite-delivery`, exit 0, after the plan amendment)

`thumbnails: 20, size ratio: 0.133, served thumbnail with cache header`

The first run exited 2 (`no ## Demonstration section`) because the plan came from the repo's stale `plan.tpl`. Owner approved adding the section.

## Orchestrator live checks (2026-11-08, on 4fb9a94 + plan amendment)

**Real set:** 366 originals 48.40 MB, 366 thumbnails 6.46 MB, ratio 0.133 (summed `st_size`).

**Burst after the change** (same 732 requests through a real quick tunnel): 200 × 634, 429 × 98, 502 × 0. Baseline was 200 × 200, 429 × 330, 502 × 202. Success went from 27% to 87%; retries are what cover the remaining 429s.

**`host.sh` with stubbed cloudflared (25 of 25 checks passed), per knowledge/host-sh-testing.md:**
- Thumbnails built (366), share link reached, rc 130 on SIGINT, quiet shutdown, nothing left running, one tunnel log holding stub output.
- Corrupt `sprites/bad.png`: one warning, still reaches a share link. A scratch copy without the `if` guard exits 1 with no link, so the check has teeth.
- `STUB_MODE=restart`: new share link and two logs, one per tunnel.
- Unwritable `DRAFT_SESSIONS_DIR`: still reaches a link, rc 130, no log written.

**Browser (headless Chrome over CDP, production build served by uvicorn, scratch script):**
- Recovery, first 2 requests per pathname aborted: 20/20 cards in view loaded in 3.6 s with no reload and no grey boxes; first card's src ended `?retry=2`.
- Same injection on the `origin/main` client: 20/20 grey boxes still there after 15 s.
- Real run: natural width 128, cache header present, pool rect 64×64, roster rect 40×40.
- Pick flash: layout size 48×48 and rendered rect settles at 48. It reads as low as 47.1 during the animation's opening `scale(0.98)`.
- Exhaustion, every request aborted: all 65 requested pathnames made exactly 7 attempts (reached at 128 s), 20/20 grey boxes, and the sampler found 0 lingering broken images.

Harness note: `drive-multiplayer-draft`'s two-tab join no longer works in a single browser profile because the per-room identity in `localStorage` hides the second tab's join form. The scratch script joined the second player over REST.

## Artifact sync

`harness worktree sync-artifacts` refuses to run outside the primary checkout, and this session was told not to work there. `handoff.md` and `notes.md` were copied to the worktree and committed by hand, which is what that command does.
