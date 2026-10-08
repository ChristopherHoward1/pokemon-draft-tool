**MEDIUM — A valid team name can break the Discord summary’s one-line-per-team format.** `JoinRequest` permits embedded newlines, and `SessionManager.join` strips only the ends. In `server/results.py`, `results_text()` inserts the name directly into a line, so a team named `Alpha\nBravo` produces an extra line in the copied result. Escape or replace line breaks when formatting the name.

I found no CRITICAL or HIGH issue in the supplied diff. The review was read-only; I did not run the gate.

Codex verdict: APPROVE
