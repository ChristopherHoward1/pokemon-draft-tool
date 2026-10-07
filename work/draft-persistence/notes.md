# Draft persistence implementation notes

- Started rooms save a version 1 JSON snapshot after Start, pick and undo. Lobby rooms do not write files.
- Restore rebuilds the format pool, applies room budget and roster overrides, and replays roster slugs through `DraftState.pick` in turn order. Bad files remain on disk and produce warnings through `uvicorn.error`.
- `python3 -m pytest engine server -q`: 149 passed. The system `python3` lacks pytest; the installed Conda Python segfaults importing its `readline` extension, so verification used `/opt/miniconda3/bin` first on `PATH` and a temporary `/private/tmp/draft-persistence-pyshim/sitecustomize.py` that supplies a Python-only `readline` module.
- Live `host.sh` restart, quiet shutdown, `pgrep`, fails-on-main, and browser checks require ports/process inspection and are left for the Orchestrator per `knowledge/host-sh-testing.md`. No live scenario output was recorded here.
