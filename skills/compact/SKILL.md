---
name: compact
description: Shrink the hot context tier — regenerate ARCHI.md from the current codebase and prune PLAN.md back to one screen. Use when the hot tier drifts stale or exceeds ~300 combined lines.
---

# /compact — maintain the hot tier

## Steps

1. **ARCHI.md:** re-scan the codebase and regenerate every section from current reality. Delete anything describing code that no longer exists. Do not append — replace.
2. **PLAN.md:**
   - `Now`: drop merged/abandoned work units.
   - `Decisions`: keep one line each; a decision whose reasoning matters links to its work unit. If the list exceeds ~15 lines, move the oldest to `knowledge/decisions.md`.
   - `Risks`: delete any risk not currently shaping decisions.
3. **work/:** directories for merged units are history — leave them, git has them; but flip any stale `Status:` lines.
4. **Report** the before/after line counts of the hot tier (CLAUDE.md + ARCHI.md + PLAN.md).

Rule: compaction deletes; it never summarizes-by-expanding. If the hot tier grew after this skill ran, it failed.
