# Retro: local-host-live-draft (v2026.10.1)

## What did the gate miss that a reviewer caught?

Three runtime bugs that pytest, the client build and shellcheck can't see:
- `host.sh`'s `kill 0` killed the caller's shell.
- The share-link scrape matched `api.trycloudflare.com`.
- Rejoin couldn't be reached from the `/lobby` invite link.

The Codex implementer sandbox can't bind ports or list processes. So nobody ran `host.sh` before review, and these bugs only surfaced there.
**Route: process.** The orchestrator runs a unit's live-server / `host.sh` scenarios outside the implementer sandbox before review. This was applied in host-hardening, where all three stub scenarios were run before review.

## What did every check miss?

Two server bugs slipped past every check:
- With no `sprites/` dir, `GET /sprites/<file>` returned a 500 (ARCHI claimed a 404).
- `GET /%00` also returned a 500.

The first was found only incidentally by a reviewer; the second came up in review round 3.
**Route: not worth keeping.** Both are fixed with regression tests in host-hardening (`server/tests/test_static.py`), so the tests now hold the lesson.

## What got re-derived that a doc would have prevented?

Driving the loop from an orca worktree instead of the primary checkout (`~/Documents/repos/pokemon-draft-tool`, whose local `main` is stale) means relearning these each time:
- `sync-artifacts` refuses to run outside the primary checkout.
- `codex-review.sh` reads `config.yaml` from local `main`, which exits 2 there.
- `tag-after-merge` needs a rebase merge.
- `release.sh` needs the previous unit's `retro.md` on `origin/main`.

All of these were hit again in host-hardening.
**Route: contextual.** Added `knowledge/orca-worktree-loop.md`.
**Follow-up `/1-plan` unit (scripts are off-limits here):** default `codex-review.sh`'s `REVIEW_BASE` to `origin/main` when it exists.

## What friction repeated from a prior retro?

None. This is the first retro in this repo.
