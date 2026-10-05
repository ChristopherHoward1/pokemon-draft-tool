# Profile: machine-learning

For projects where model/data quality — not just code correctness — defines done.

## Declarations required at /init (recorded in ARCHI.md → Verification)

- **EVAL_METRIC** — the metric that defines "better", or `NONE` if evaluation is criterion-based.
- **GROUND_TRUTH_SOURCE** — where labels/truth come from, and their known limits.
- **EVAL_COMMAND** — the command that produces the metric. This goes in `scripts/gate.d/eval.sh` when cheap enough to run per-change; otherwise it runs at /3-review.
- **DATA_REGIME** — offline vs. online; what data the system sees in production vs. training.
- **NOTEBOOK_STRATEGY** — notebooks are exploratory-only by default: they do not gate correctness and are not reviewed as product artifacts. Shared or correctness-critical logic moves to a `.py` module covered by the normal gate. Notebooks are single-author scratch files under an owner namespace such as `notebooks/<initials>/...`; two people do not co-edit the same notebook. To keep JSON diffs mergeable, copy `scripts/gate.d/examples/nb-clean.sh` to `scripts/gate.d/nb-clean.sh` in ML/CV repos that track notebooks; it fails on tracked `*.ipynb` files with non-empty `outputs` or `execution_count`. Fix notebooks with `nbstripout --install` or `jupyter nbconvert --clear-output --inplace <notebook.ipynb>`.
- **REPO_HYGIENE** — decide whether to copy `scripts/gate.d/examples/ds-hygiene.sh` to `scripts/gate.d/ds-hygiene.sh`. When enabled, it fails on oversized tracked data/model artifacts and hardcoded local paths in tracked Python/notebook files. Decide the hook's local policy knobs: `DS_DATA_MAX_BYTES`, `DS_DATA_ALLOW_DIRS`, and `DS_PATH_SCAN`; `DS_DATA_ALLOW_DIRS` is a colon-separated list of literal path prefixes, so include a separator boundary when needed. `gate.d/` hooks run on every gate regardless of `profile:`. This is a gate-time guard over working-tree size, run before the commit lands; it can prevent newly tracked blobs before commit, but it does not recover repo history and goes quiet after an already-committed blob is removed from the working tree.

## Adds to the loop

- **/1-plan:** a plan changing model, features, or data must state its expected effect on EVAL_METRIC and how that will be measured. "Should improve things" is not a criterion.
- **/3-review:** the reviewer receives the eval result (metric before/after, data version) alongside the diff. Code-green with metric-red is REQUEST CHANGES.
- **Correlated-validator warning:** an LLM judging LLM output shares blind spots with it. Where the reviewer and the system-under-test are the same model family, deterministic evals and held-out data carry the weight — agent agreement is corroboration, never validation.

## Gate

Add `scripts/gate.d/eval.sh` when EVAL_COMMAND is cheap; keep expensive evals at review-time and say so in ARCHI.md.
