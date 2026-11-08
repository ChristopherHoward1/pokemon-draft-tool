# Review round 1 — sprite-delivery

The Codex review's first attempt exited 2 because local `main` predated `config.yaml`. That was a tooling error, not a verdict; the Owner fast-forwarded `main` and it was re-run from the `fix/stratified-clamp` checkout.

- **Claude code-reviewer:** APPROVE. It ran the gate (PASS, 308 passed, 4 skipped) and re-measured the real-set size ratio (0.1334). Host and browser criteria were taken from `notes.md`, and only `work/` files changed after those runs.
  1. **MEDIUM:** same-second tunnel log copies collide because BSD `mktemp` only randomises trailing X's. **Deferred:** see [deferrals.md](deferrals.md).
  2. **LOW:** with sprites present and Pillow missing, a raw traceback prints before `host.sh`'s warning. Hosting continues, and Pillow is in `requirements.txt`. **No action.**
  3. **LOW:** thumbnails get mode 0600 from `NamedTemporaryFile`. Harmless when the same user generates and serves them, as `host.sh` does. **No action.**
  4. **LOW:** `README.md:278` reads as if `./host.sh` users don't need to fetch sprites; `host.sh`'s missing-sprites warning still gives the right command. **No action.**
- **Codex:** APPROVE, no findings. It didn't run the gate; the Orchestrator's and the Claude reviewer's gate runs passed.
