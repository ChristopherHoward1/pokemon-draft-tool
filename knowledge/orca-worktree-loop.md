# Running the loop from an orca worktree

The Owner drives the loop from orca worktrees (`~/orca/workspaces/pokemon-draft-tool/*`), not from the primary checkout (`~/Documents/repos/pokemon-draft-tool`), whose local `main` is stale. The harness scripts assume the primary checkout, so:

- **Artifacts:** `scripts/worktree.sh sync-artifacts` refuses to run anywhere but the primary checkout. Instead, copy `work/<slug>/*` (never over `plan.md`) into `wt/<slug>` by hand and commit it as `Record artifacts for <slug>`.
- **Codex review:** run `REVIEW_ROUND=<n> scripts/codex-review.sh <slug>` from the orca checkout that isn't on `wt/<slug>`. It reads `config.yaml` and diffs against `origin/main` (set `REVIEW_BASE` only for stacked branches).
- **PLAN.md Now entry:** add it on `wt/<slug>` *after* both reviews approve. Added earlier, it shows up in the review diff as an out-of-footprint file (Codex raised it as HIGH in host-hardening).
- **Merge:** rebase-merge the release PR (`gh pr merge <n> --rebase`). `release.sh tag-after-merge` requires the tip of `origin/main` to be titled exactly `Release v<version>`, which a merge or squash commit would break.
- **Retro first:** `release.sh` refuses to release while the slug in `work/.last-released` has no `work/<slug>/retro.md` on the branch. So merge the previous unit's retro PR, then rebase `wt/<slug>` onto `origin/main`.
- **Implementer sandbox:** Codex can't bind ports or list processes. Run the live `host.sh` / server scenarios yourself before review.
