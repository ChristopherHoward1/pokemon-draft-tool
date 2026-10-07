# Retro: host-polish (v2026.10.3)

## What did the gate miss that a reviewer caught?

Two non-blocking findings:
- **Codex (MEDIUM):** `PORT=''` falls back to 8000 instead of being refused.
- **Claude reviewer (LOW):** a server that dies during a failed tunnel restart prints "Retrying soon" right before `host.sh` exits.

**Route: not worth keeping.** Both are in `work/host-polish/deferrals.md`: the first as no action, the second landing in the next unit that touches `host.sh`.

## What did every check miss?

The implementer's orphan check didn't test the race. It emptied `tunnel_pid` at launch, so `start_tunnel` failed before any share link appeared, and the sandbox couldn't run `pgrep` anyway. The Orchestrator caught this only by reading `notes.md`. It re-ran the check by clearing `tunnel_pid` inside cleanup instead, then confirmed that the same check fails on `main`'s `host.sh`.

**Route: contextual.** Added both techniques to `knowledge/host-sh-testing.md`: the orphan simulation, and "prove a new check fails on main".

## What got re-derived that a doc would have prevented?

The `host.sh` test harness was rebuilt again, four more times: by the implementer, by the plan reviewer (bash 3.2 experiments), by the Orchestrator and by the code reviewer. That happened even though `knowledge/host-sh-testing.md` was written for exactly this in the host-hardening retro. Neither the plan nor the handoff cited it, and cold-tier docs load only when a task names them, so nobody opened it. The doc had also gone stale: it still listed `Terminated: 15` as expected shutdown noise. It also lacked the `set -m` SIGINT trap, the new scenarios, and a `pgrep` pattern that a real cloudflared on the machine can't match.

**Route: process.** Added a `PLAN.md` Decisions line: a plan that touches `host.sh` cites `knowledge/host-sh-testing.md` in its Verification section and in the handoff. The doc itself is refreshed under the previous answer's routing.

## What friction repeated from a prior retro?

The implementer sandbox again. Besides not binding ports or listing processes, this time Codex couldn't commit: `git add` fails because the worktree's gitdir lives outside the sandbox (`.git/index.lock`). The Orchestrator committed for it.

Also new this time: `.claude/agents/` types (`plan-reviewer`, `code-reviewer`) weren't registered in this session. It had started in the orca workspace parent directory, not in a checkout. Both reviews ran as fresh general-purpose agents given the definitions verbatim.

**Route: contextual.** Both notes added to `knowledge/orca-worktree-loop.md`.

Not worth keeping:
- **Merge failures:** `gh pr merge --rebase` and the REST merge endpoint both failed server-side, with GraphQL errors and an empty body, while the PR was clean. The web UI merge worked. This was transient on GitHub's side.
- **Tagging without confirmation:** the Orchestrator bundled `tag-after-merge` into a verification command without asking the Owner first, and the Owner rejected it. The Owner-confirmation rule in `CLAUDE.md` already covers this; the slip was execution, not a missing rule.
