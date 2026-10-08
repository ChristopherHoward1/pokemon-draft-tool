# Accepted deferrals — results-export

- **Newlines in team names break the Discord text's one-line-per-team format.** Raised in review round 1 by Codex (MEDIUM) and Claude (LOW).
  - **Why deferred:** the Lobby join field is a single-line `<input>`, so a newline can only arrive through a hand-made API call, and the result is cosmetic (`@` is escaped, so it can't ping). The clean fix is to reject control characters in team names in `JoinRequest`, which is outside this unit's footprint (`server/models.py`), and fixing it here would also force a new review round.
  - **Where it lands:** a later unit that validates team names in `server/models.py`: reject or collapse `\r`, `\n` and other control characters.
