# Changelog

All notable changes to this project are documented in this file.
## [2026.10.2] - 2026-10-06

- Draft night is sturdier — missing sprites and `%00` URLs return 404 instead of crashing, `host.sh` refuses a busy port and restarts a dropped tunnel with a fresh link, and players see "can't reach server" with Retry instead of a false "room not found".
- Confirm-delta: Owner 2026-10-06: 'go ahead' + 'yes, do all of it' (release, push, PR, merge, tag)

## [2026.10.1] - 2026-10-05

- Host a live draft from your own machine with `./host.sh` (one shareable link via a cloudflared quick tunnel), and players who lose their tab can rejoin their team.
- Confirm-delta: Owner confirms push + PR in-session (TRIP not granted in this repo)

