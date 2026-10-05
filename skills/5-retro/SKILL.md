---
name: 5-retro
description: Close a work unit by recording lessons and routing each one to the smallest durable project artifact.
---

# /5-retro — retro

Input: a work unit slug.

## Steps

1. **Create the retro branch:** from the primary checkout, run `bash scripts/worktree.sh add retro-<slug>` and work in the returned worktree on branch `wt/retro-<slug>`. If the worktree already exists, reuse it instead of running worktree.sh add again.
2. **Answer the four questions:**
   - What did the gate miss that a reviewer caught?
   - What did every check miss?
   - What got re-derived that a doc would have prevented?
   - What friction repeated from a prior retro?
3. **Route each answer to exactly one label:**
   - `mechanical` — a `gate.d/` hook or script fix.
   - `contextual` — a `knowledge/` doc, following `knowledge/README.md`: the doc that would have prevented this instance, no bigger.
   - `process` — one line in `PLAN.md` under Decisions.
   - `not worth keeping` — say so explicitly, with why.
4. **Write the retro:** create `work/<slug>/retro.md` on the retro branch. "Nothing learned" is a valid one-line retro.
5. **Apply every routing on the retro branch.** An unapplied routing means the stage is not done.
6. **Respect the mechanical file boundary:** the retro branch may only touch `knowledge/`, `PLAN.md`, and `work/<slug>/retro.md`. Any routing that would edit `scripts/` or `gate.d/` becomes a `/1-plan` unit named in the retro instead of being applied here.
7. **Publish for review:** push `wt/retro-<slug>` and open a PR to `main`.
8. **Clean up after merge:** run `bash scripts/worktree.sh remove retro-<slug>` after the PR merges.

## Rules

- `/5-retro` can run after `/4-release` or standalone for abandoned units.
- Lessons go to one durable place each. Do not duplicate the same lesson across labels.
