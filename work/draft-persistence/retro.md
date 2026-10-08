# Retro: draft-persistence (v2026.10.4)

## What did the gate miss that a reviewer caught?

The Claude code reviewer (round 1, MEDIUM) caught that `save` didn't `fsync` before `os.replace`. A power loss could have left a truncated snapshot, losing the started draft this unit exists to protect. The Orchestrator fixed it in 58d78aa, and round 2 approved.

**Route: not worth keeping.** It was a one-off detail of the atomic write, and the fix and its comment now live in `server/session_manager.py`. No gate hook can check durability.

## What did every check miss?

Nothing is known to have reached release. The closest call came at plan time: the draft plan logged the restore line on a `__name__` logger, and under uvicorn that INFO line would never print. A restored lobby room would also have been a dead end on a new tunnel origin. The plan reviewer caught both by experiment, before implementation.

**Route: not worth keeping.** The logging fact is now in ARCHI's `server/` line (`uvicorn.error`), and the lobby decision is in the plan.

## What got re-derived that a doc would have prevented?

The Orchestrator built two harnesses from scratch: the API-level `host.sh` restart scenario, and a two-context Playwright driver for the browser rejoin check. The browser driver needed a debugging pass (a stale-card race on back-to-back snake picks). The next unit, results export, will need a browser check too.

**Route: contextual.** Added a "Restart and rejoin" section to `knowledge/host-sh-testing.md`. It covers the scenario steps, the "fails on main" caveat (persistence lives in `server/`, so use a full `origin/main` checkout), the localhost/127.0.0.1 origin swap, one browser context per player, and the wait-for-pick driver rule.

## What friction repeated from a prior retro?

- **Reviewer agent types.** `plan-reviewer` and `code-reviewer` were again unregistered, because the session started in the orca workspace parent directory. Plan and code reviews ran as general-purpose agents given the definitions verbatim. **Route: not worth keeping.** This is already in `knowledge/orca-worktree-loop.md`, and the workaround worked.
- **Implementer commits.** The host-polish retro recorded that Codex can't commit. This time it committed normally, so the doc was wrong in the other direction. **Route: contextual.** `knowledge/orca-worktree-loop.md` now says committing is inconsistent: check `git status` after dispatch, and commit only if the implementer didn't.

Not worth keeping:
- **Codex reviewer gate runs.** Codex review couldn't run the gate, because `codex-review.sh` runs from a checkout detached at the baseline. The Orchestrator's and the Claude reviewer's gate runs cover this.
- **Implementer Python.** The implementer's Conda Python segfaulted importing `readline`, and it worked around this with a temporary shim outside the repo. This is specific to the sandbox environment; gate runs outside the sandbox were unaffected.
