---
name: 2-implement
description: Dispatch the implementer agent into an isolated worktree for an approved work unit, then drive the gate loop until green. Use after /1-plan approval.
---

# /2-implement — dispatch and gate

Input: an approved work unit `work/<slug>/plan.md`.

Read `implementer.fan` from `config.yaml`.

- `N=1`: use the existing single-agent steps below, textually as written.
- `N>1`: use fan mode instead of step 1. Do not create `wt/<slug>` before adoption; `scripts/fan-exec.sh adopt` creates the canonical worktree after retargeting `wt/<slug>`.

## Steps

1. **Create the worktree:** `WT=$(scripts/worktree.sh add <slug>)`.
2. **Render the handoff** from `prompts/handoff.tpl` into `work/<slug>/handoff.md`. It must be self-contained — the implementer starts cold.
3. **Dispatch:** `scripts/agent-exec.sh "$WT" work/<slug>/handoff.md`. Capture the implementer's final summary into `work/<slug>/notes.md`, then from the repo root run `scripts/worktree.sh sync-artifacts <slug>`.
4. **Run the gate in the worktree:** `cd "$WT" && scripts/gate.sh`. Trust the exit code, not the implementer's claim.
5. **On failure:** render `prompts/followup.tpl` with the gate output and re-dispatch, then from the repo root run `scripts/worktree.sh sync-artifacts <slug>` after each dispatch. Retry dispatch/gate up to `gate.max_retries` from `config.yaml`. After that, stop and escalate to the Owner with the failing output — do not fix it yourself in this stage, and do not lower the bar.
6. **On pass:** commit in the worktree if the implementer didn't, then proceed to `/3-review`.

## Rules

- You orchestrate; the implementer implements. If you catch yourself editing code in the worktree, you've collapsed the roles — stop.
- Footprint violations reported by the implementer go back to `/1-plan`, not into ad-hoc scope expansion.

## Fan Mode (`N>1`)

1. Render the same handoff from `prompts/handoff.tpl` into `work/<slug>/handoff.md`.
2. Run `scripts/fan-exec.sh dispatch <slug> work/<slug>/handoff.md <N>`. Dispatch is sequential and prints a manifest containing only gate-passing sample branches.
3. Handle the manifest:
   - 0 survivors: run `scripts/fan-exec.sh adopt <slug> <slug>-fan-1`, then run the existing failed-gate followup loop in `wt/<slug>` using `prompts/followup.tpl`, up to `gate.max_retries`; after that, stop and escalate to the Owner with the failing output.
   - 1 survivor: run `scripts/fan-exec.sh adopt <slug> <survivor>`.
   - 2+ survivors: spawn a fresh `fan-selector` thread to rank the surviving diffs against the plan, then run `scripts/fan-exec.sh adopt <slug> <winner>`.
4. The `fan-selector` is only a selector: it is distinct from `/3-review`'s `code-reviewer`, has a different output contract, and must not anchor or replace the later approver.
5. After adoption, all paths converge on populated `wt/<slug>`; from the repo root run `scripts/worktree.sh sync-artifacts <slug>`, then continue to `/3-review` as in step 6.
