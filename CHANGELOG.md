# Changelog

All notable changes to this project are documented in this file.
## [2026.10.5] - 2026-10-08

- Finished multiplayer drafts can be exported: every player can copy a Discord-ready roster summary or download the picks as CSV.
- Confirm-delta: Owner confirmed in session 2026-10-08: 'good to go' (merge retro PR, rebase, release, push, open release PR)

## [2026.10.4] - 2026-10-07

- Started drafts hosted with `./host.sh` survive a restart. Re-running it restores each room's pool, picks and turn, and players rejoin with the "Rejoin as…" picker.
- Confirm-delta: Owner approved release, push and PR in session (2026-10-07: "go ahead")

## [2026.10.3] - 2026-10-07

- `host.sh` explains a bad `PORT` or missing curl instead of claiming the port is busy, re-checks the port after the build, never leaves a stray tunnel behind, notices a dead server during a tunnel restart, and shuts down quietly; sprites, client files and `/health` answer HEAD requests.
- Confirm-delta: Owner confirmed release, push and PR in-session (2026-10-07)

## [2026.10.2] - 2026-10-06

- Draft night is sturdier — missing sprites and `%00` URLs return 404 instead of crashing, `host.sh` refuses a busy port and restarts a dropped tunnel with a fresh link, and players see "can't reach server" with Retry instead of a false "room not found".
- Confirm-delta: Owner 2026-10-06: 'go ahead' + 'yes, do all of it' (release, push, PR, merge, tag)

## [2026.10.1] - 2026-10-05

- Host a live draft from your own machine with `./host.sh` (one shareable link via a cloudflared quick tunnel), and players who lose their tab can rejoin their team.
- Confirm-delta: Owner confirms push + PR in-session (TRIP not granted in this repo)

