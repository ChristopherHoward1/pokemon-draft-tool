# Accepted deferrals — sprite-delivery

- **Tunnel log copies made in the same second collide on macOS.** Raised in review round 1 by Claude (MEDIUM). BSD `mktemp` only randomises trailing X's, so `tunnel-<ts>-XXXXXX.log` (`host.sh:53`) keeps a literal `XXXXXX`, and a second copy in the same second is silently lost.
  - **Why deferred:** it needs a Ctrl-C within a second of a tunnel restart, restart attempts are at least 30 s apart, and only a diagnostic log is lost. No draft behaviour is affected.
  - **Where it lands:** the next unit that touches `host.sh`: put the random part at the end of the template and rename to `.log`, or add a counter to the name.
