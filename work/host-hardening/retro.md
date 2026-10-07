# Retro: host-hardening (v2026.10.2)

## What did the gate miss that a reviewer caught?

Two things:
- **A path segment longer than the filesystem name limit still returns 500.** `is_file()` raises `ENAMETOOLONG` outside the try.
- **The `PLAN.md` Now entry was committed before review**, so Codex flagged it as an out-of-footprint HIGH.

**Route: not worth keeping.**
- The 500 is already in `work/host-hardening/deferrals.md` with a fix and a test to add, and it lands in the next unit that touches `server/main.py`. Recording it again would duplicate it.
- The PLAN.md ordering is already covered by `knowledge/orca-worktree-loop.md`, which was written from this unit during the previous retro.

## What did every check miss?

Nobody ran the plan's manual criterion: the `./dev.sh` browser check of the Retry button. The implementer couldn't (sandbox), the reviewers marked it "unverifiable", and it shipped listed as unverified in PR #16. The repo already has a real-Chrome driver (`drive-multiplayer-draft` skill), so it could have been run.
**Route: process.** A `PLAN.md` Decisions line says manual and browser criteria are run by the Orchestrator before `/4-release` (via `drive-multiplayer-draft` or Chrome), or the Owner explicitly waives them.

## What got re-derived that a doc would have prevented?

The `host.sh` test recipe was worked out four separate times: by the implementer, by the Orchestrator, and by both code-reviewer rounds. Each one wrote its own fake cloudflared, counter-file trick, port scheme and `pgrep` check. Two related constraints were also only in handoff text: bash 3.2 compatibility, and `exec sleep` hiding the stub from `pgrep`.
**Route: contextual.** Added `knowledge/host-sh-testing.md`.

## What friction repeated from a prior retro?

Two items from the local-host-live-draft retro came up again:
- **The implementer sandbox can't bind ports.** This time the routed process worked: the Orchestrator ran the scenarios before review.
- **`codex-review.sh` exits 2 against the stale local `main`.** That happened again before the knowledge doc existed. Its fix is still the follow-up `/1-plan` unit named in that retro (default `REVIEW_BASE` to `origin/main`).

**Route: not worth keeping.** No new routing; the follow-up unit is already named and is the next candidate task.
