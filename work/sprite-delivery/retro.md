# Retro: sprite-delivery (v2026.11.0)

## What did the gate miss that a reviewer caught?

The Claude reviewer (MEDIUM) ran the code and found that BSD `mktemp` only randomises trailing X's, so `tunnel-<ts>-XXXXXX.log` keeps a literal `XXXXXX` and a second copy in the same second is lost. shellcheck can't see it. It's in `work/sprite-delivery/deferrals.md`.

**Route: contextual.** Added to the bash 3.2 line at the top of `knowledge/host-sh-testing.md`.

The plan reviewer caught that a fresh worktree has no `sprites/`, and that a 15 s retry budget would have reproduced the reported symptom on any longer stall. **Route: not worth keeping.** Both now live in the plan and the code.

## What did every check miss?

- **The plan had no `## Demonstration`, and nothing noticed until `harness demo` exited 2.** The plan was drafted from the repo's `skills/1-plan/prompts/plan.tpl`, which is older than the installed skill's template. The plan reviewer has no reason to look for a section its template doesn't mention. **Route: contextual** for the workaround, in `knowledge/orca-worktree-loop.md`. Syncing the repo's copy is outside this branch's file boundary. **Named follow-up unit: `sync-skill-templates`.**
- **No real browser has retried through a real tunnel.** Retries were tested with injected failures, and the burst used `curl`. The first real draft on v2026.11.0 is the test: the 98 remaining 429s in the "after" burst are what retries must absorb. **Route: not worth keeping.** It's a one-off gap, and `host.sh` now keeps the tunnel log if it recurs.

## What got re-derived that a doc would have prevented?

- **The real failure, measured.** The Owner's report was "grey boxes", and the plan's cause was a guess from memory. A one-second burst through a real quick tunnel reproduced it (27% of requests loaded) and exposed a 502 failure nobody had predicted. It should have run before the plan was written, not after it was approved. **Route: contextual.** Recipe added to `knowledge/host-sh-testing.md`.
- **`getBoundingClientRect` during the pick flash** reads 47.1 px, because the animation opens at `scale(0.98)`. **Route: contextual.** One bullet in the browser section of the same doc.

## What friction repeated from a prior retro?

The session started on `fix/stratified-clamp`, 13 commits behind `origin/main`, and `knowledge/orca-worktree-loop.md` wasn't on that branch. So several things it documents were rediscovered the hard way:
- `sync-artifacts` refusing to run outside the primary checkout;
- the `PLAN.md` Now entry added too early, which this doc warns about after host-hardening;
- two pages in one browser context sharing `localStorage`, documented in the draft-persistence section of `host-sh-testing.md`.

**Route: process.** One line in `PLAN.md` Decisions: read the loop doc from `origin/main` before starting.

- **Stale local `main` blocked Codex review.** `codex-review.sh` reads `main:config.yaml`, and local `main` predated the harness, so it exited 2. The loop doc said only that it "reads `config.yaml`". **Route: contextual.** That bullet now says which ref, and what to do.
- **`drive-multiplayer-draft`'s driver is stale.** Its two tabs share one browser profile, so the per-room identity in `localStorage` hides the second tab's join form. Fixing it is outside this branch's file boundary. **Named follow-up unit: `refresh-e2e-driver`.**

Not worth keeping: the Claude reviewer's three LOWs, recorded in `work/sprite-delivery/review-r1.md` with no action.
