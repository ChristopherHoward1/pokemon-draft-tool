# Results export implementation

- `DraftState.pick_log()` walks existing engine turn order and supplies both CSV ordering and costs.
- The backend rejects lobby and unfinished rooms with `NotReady`; completed rooms, including restored rooms, export CSV and Discord text.
- The Draft sidebar loads Discord text when completion changes, guards against stale responses, and gives each player a copy button and CSV link.
- Browser checks remain with the Orchestrator as assigned in the handoff.
- Local test commands use Conda Python on `PATH` and a temporary `sitecustomize.py` that skips a crashing macOS `readline` import in pytest. No repo files are changed for this workaround.
