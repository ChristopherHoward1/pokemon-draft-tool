# Profile: database

For schema-, migration-, or data-pipeline-centric work, where mistakes are stateful and rollback is the design constraint.

## Declarations required at /init (recorded in ARCHI.md)

- **MIGRATION_TOOL** — how schema changes apply (alembic, flyway, raw SQL, ...).
- **ROLLBACK_STORY** — what "undo" means here: down-migrations, snapshots, or "forward-only" (declare it explicitly if so).
- **SCRATCH_TARGET** — a database or schema copy where destructive changes can be rehearsed.

## Adds to the loop

- **/1-plan:** every migration plan states its rollback path, or explicitly declares forward-only and why that's acceptable. Destructive operations (DROP, irreversible type changes, data rewrites) are named in the plan, never discovered in review.
- **/2-implement:** migrations run against SCRATCH_TARGET before the gate passes — `scripts/gate.d/migrate-dry-run.sh` wires this.
- **/3-review:** the reviewer checks the migration against ROLLBACK_STORY and looks specifically for locks/table-rewrites on large tables.

## Gate

`scripts/gate.d/migrate-dry-run.sh`: apply the migration to SCRATCH_TARGET, run the app's smoke check, apply the down-migration if one exists. Non-zero on any step.
