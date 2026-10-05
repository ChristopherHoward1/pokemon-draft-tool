---
name: 1-plan
description: Draft a work unit and have it reviewed by a fresh plan-reviewer subagent before it becomes real. Use when starting any non-trivial piece of work.
---

# /1-plan — plan a work unit

Input: the Owner's request (argument or conversation context).

## Steps

1. **Orient.** Read `PLAN.md` and `ARCHI.md`. If the request conflicts with the current objective, raise it before planning.
2. **Pick a slug** (`kebab-case`, short) and draft `work/<slug>/plan.md` from `prompts/plan.tpl`. Verify every codebase claim against the actual code — footprints especially.
3. **Spawn the reviewer.** Launch the `plan-reviewer` agent (fresh thread, never this one) with: the draft plan path and instruction to review per its own definition.
4. **Incorporate.** Apply REVISE findings you agree with; where you disagree, record the disagreement and your reasoning in the plan's `## Review` section — the Owner arbitrates disagreements, not you.
5. **Present** the final plan to the Owner: goal, footprint, acceptance criteria, and the reviewer verdict, in a few lines. On approval, add the work unit to `PLAN.md → Now` and proceed to `/2-implement`.

## Rules

- A plan without checkable acceptance criteria is not done.
- If the honest answer is "this is trivial, skip the loop" — say that instead of planning it.
- Never implement in this stage.
