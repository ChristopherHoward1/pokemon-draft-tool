# Retro: results-export (v2026.10.5)

## What did the gate miss that a reviewer caught?

Codex review (MEDIUM) and the Claude reviewer (LOW) both found that a team name with an embedded newline splits its line in the Discord text. `JoinRequest` allows it, and `join` strips only the ends. It was deferred in `work/results-export/deferrals.md`: only a hand-made API call can produce it, and it's cosmetic, since `@` is escaped.

The plan reviewer did the heavier lifting before any code existed:
- It measured the original "under 2000 chars" claim against real data. The claim failed: 275 of 356 AAA entries are `Unranked`. The compact format came from that.
- It caught three gaps: the test recipe was missing `started=True`, the new React hooks had to sit above `DraftBoard`'s early return, and the shared `useCopy` instance would have mislabelled the "Copy draft link" button.

**Route: not worth keeping.** Each detail now lives in the plan, the tests or the code. The general habit (verify size and length claims against `data/` by experiment) is already in the plan-reviewer's "verify claims against the actual code". The deferral is recorded in the ledger, which is where the next unit will find it.

## What did every check miss?

Nothing is known to have reached release.

**Route: not worth keeping.**

## What got re-derived that a doc would have prevented?

The browser check needed a third ad-hoc Playwright driver. The draft-persistence section of `knowledge/host-sh-testing.md` paid off: two contexts, `createRequire` and the wait-for-pick rule worked first time. Four things were still worked out from scratch:
- the card selector for a full UI draft;
- reading the clipboard deterministically;
- checking a download without driving it;
- building the client same-origin (the `.env.production` placeholder).

**Route: contextual.** Added those four bullets to the browser section of `knowledge/host-sh-testing.md`.

## What friction repeated from a prior retro?

- **Codex review from another orca checkout.** `scripts/codex-review.sh` exited 2 ("missing work directory") because the retro checkout it ran from had no `work/results-export/`. That was a tooling error, not a verdict; `mkdir -p` and a re-run fixed it. **Route: contextual.** `knowledge/orca-worktree-loop.md`'s Codex review bullet now says to create the dir, copy the artifact back onto `wt/<slug>` and remove it.

Not worth keeping:
- **Reviewer agent types.** They were again unregistered, because the session started in the orca parent dir. This is already documented, and the workaround worked.
- **Implementer.** Codex committed normally this time, which matches the doc's "inconsistent: check `git status`".
- **Stale PLAN.md entry.** The draft-persistence retro didn't flip its PLAN.md Now entry to "released"; it was fixed in passing on `wt/results-export`. This retro flips results-export's entry. A one-off.
