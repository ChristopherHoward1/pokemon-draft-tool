---
name: init
description: Bootstrap this framework onto a project — scan the codebase, generate ARCHI.md, fill config.yaml, and verify the gate runs. Use once when adopting the framework, or on a freshly cloned template.
---

# /init — bootstrap a project

## Steps

1. **Scan the codebase** (or note that it's greenfield): languages, frameworks, layout, entry points, existing test/lint commands.
2. **Classify** the project and set `profile:` in `config.yaml` (`software` | `machine-learning` | `database` | `work`). Read the chosen profile and ask the Owner for any declaration it requires (e.g. ML's eval slots).
   A profile's one-time infra swaps, such as Bitbucket CI or implementer runtime changes, happen by the orchestrator following the chosen `profiles/*.md` prose.
3. **Generate `ARCHI.md`** from the scan — replace every placeholder. Conventions section: only what an agent would get wrong by guessing.
4. **Wire the gate:** confirm `scripts/gate.sh` detects the project's stacks; add anything project-specific as a `scripts/gate.d/*.sh` hook. Run it and show the Owner the output.
5. **Confirm the implementer:** check the configured runtime exists (`command -v codex` or equivalent); if not, ask the Owner what to set in `config.yaml`.
6. **Seed `PLAN.md`:** fill Objective with the Owner, leave the rest empty.

Done when: ARCHI.md has no placeholders, the gate runs (pass or legitimately fail), and config.yaml reflects reality.
