---
name: docs
description: Dispatch codex/GPT into an isolated worktree to write or rewrite documentation prose for an approved docs work unit.
---

# /docs — dispatch documentation writer

Input: a docs work unit slug with `work/<slug>/plan.md`. The plan names which documentation to write or rewrite and declares the file footprint.

## Steps

1. **Create the worktree:** `WT=$(scripts/worktree.sh add <slug>)`. Documentation work happens in worktrees, never the primary checkout.
2. **Render the handoff** from `prompts/handoff.tpl` into `work/<slug>/handoff.md`. It must be self-contained — the docs writer starts cold.
3. **Dispatch codex/GPT:** `scripts/agent-exec.sh "$WT" work/<slug>/handoff.md`. This intentionally uses the existing two-argument dispatch form and reuses `implementer.command`, which is codex/GPT; GPT authors the prose. Capture the writer's final summary, then from the repo root run `scripts/worktree.sh sync-artifacts <slug>`.
4. **Present the diff** to the Owner. The Owner and coworkers are the readers of prose quality; there is no automated prose-quality judge.
5. **Ship lane:** use the small-fix path: branch + tell the Owner. Do not send pure documentation prose through `/3-review` -> `/4-release`, because the dual-vendor `/3-review` bases diffs on `origin/main` and gates on code-review sentinels, which reviews prose as code.

## Rules

- **No gate loop.** Prose has no exit-code contract. If a docs change also edits code or scripts, that is out of scope for `/docs`; `/docs` is for documentation prose.
- **No self-review; writer never reviews.** codex writes the prose; the orchestrator does not rewrite codex's prose in-thread. This preserves the framework's writer != reviewer invariant.
- Footprint violations reported by the docs writer go back to planning, not into ad-hoc scope expansion.
