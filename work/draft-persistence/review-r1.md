# Review round 1 — draft-persistence

The `code-reviewer` agent type isn't registered in this session, so a fresh general-purpose agent was given its definition verbatim, read-only.

- **Codex:** APPROVE, no findings. It couldn't run the gate; the Orchestrator's gate run passed.
- **Claude code-reviewer:** APPROVE. It ran the gate (PASS, 289 passed). It also ran the suite with `DRAFT_SESSIONS_DIR` exported: nothing was written. Every non-manual criterion met; the browser check is pending for the Orchestrator.
  1. **MEDIUM:** `save` didn't `fsync` the temp file before `os.replace`. A power loss or battery death could leave a truncated `<CODE>.json`, and the started draft would be skipped on restore. **Fixed by the Orchestrator:** `temp.flush(); os.fsync(temp.fileno())` before the rename. Round 2 is required because the Orchestrator wrote code.
  2. **LOW:** `_load_all` doesn't catch `RecursionError`. A hand-crafted, deeply nested `.json` would stop the server from starting instead of being skipped. The app never writes such a file. **No action** (LOW never blocks).
