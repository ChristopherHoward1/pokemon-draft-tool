# Profile: work

For workplace repositories that use Atlassian/Bitbucket review and CI conventions while keeping this template as the single source.

## Declarations required at /init

- **Implementer runtime** — when the workplace uses Claude Code for implementation, set `implementer.runtime: claude` and use:

```yaml
implementer:
  runtime: claude
  command: 'claude -p --dangerously-skip-permissions'
```

## Adds to the loop

- **Jira:** Jira keys may be recorded as read-only references in `work/<slug>/plan.md`. The loop never creates or mutates Jira issues.
- **Release:** use the base PR-merge release flow.

## Machine-learning hygiene

If a work repo is also an ML/data-science repo, copy the relevant `NOTEBOOK_STRATEGY` and `REPO_HYGIENE` declarations from `profiles/machine-learning.md` during /init. `config.yaml` selects exactly one `profile:` with no merging, and `scripts/gate.d/*.sh` hooks run on every gate regardless of `profile:`. The DS hygiene hook is a gate-time guard over working-tree size, run before the commit lands; it prevents new tracked blobs before commit but does not recover already-committed artifact history. Its allowed directories are literal path prefixes, so choose prefixes with separator boundaries where that distinction matters.

## S3 write discipline

Data lands under a fixed **pipeline-role** taxonomy, never ad-hoc paths. The role — *where in the workflow an artifact was produced* — is stable across project types; modality (tabular, vision, RAG) only changes the file format at the leaf. Root is `s3://<bucket>/<owner-scope>/{project}/`. The `<owner-scope>` segment names *who owns the write* within the bucket, so multiple people can share one bucket — and one framework checkout — without colliding. It takes one of two kinds of value:

- **A person** — resolve per-write from the environment (`$USER`, or the configured identity) rather than baking in one name: `ch/`, `sh/`.
- **A shared namespace** — `shared/` (or `team/`) for collaborative artifacts no single person owns.

Declare the real bucket at /init (it lives in the work-side copy of this profile, never in the public template). `<bucket>` is the ownership/access boundary and `<owner-scope>` is the writer within it, so the same scopes carry over unchanged when a personal bucket is later swapped for a real team bucket:

```
{project}/
  raw/         # immutable source pulls — Snowflake extracts, scraped images, source docs
  processed/   # cleaned / transformed / joined — derived from raw, reproducible
  features/    # model-ready inputs: feature matrices, embeddings, vector stores
  models/      # trained artifacts, checkpoints, fine-tunes
  outputs/     # predictions, eval reports, metrics, generated samples
```

**Classifier** (modality-independent — apply to every write):

> Source pull, untouched? → `raw/`. Cleaned/joined? → `processed/`. Model-ready input? → `features/`. A trained thing? → `models/`. A prediction/metric/generation? → `outputs/`.

**Rules:**

1. **`raw/` is immutable.** Never overwrite or mutate it — it's the reproducibility anchor; everything else regenerates from it.
2. **Partition by run** under each leaf so data traces to the model it produced: `raw/snowflake/dt=2026-08-26/`, `models/run=2026-08-26-xgb/`.
3. **Scratch stays out.** Local RAG tests and throwaway experiments stay local; if they must hit S3, use a disposable `scratch/` (or `experiments/{name}/`) sibling — never the five real buckets.
4. **`shared/` traces to a writer.** A shared owner-scope has no single owner, so partition every write under it by writer or run — `shared/{project}/models/run=2026-08-26-sh-xgb/` — never anonymous drops.

The plan for a work unit that writes data names its `{project}` root; writes never happen outside it.

## Snowflake

Queries run from a notebook using the company's custom SageMaker module — not documented here (company code). Spin up querying by pasting the standard skeleton notebook (SQL → local files) into the repo; treat query outputs as `raw/` per the S3 discipline above.

## Gate

Replace GitHub Actions with Bitbucket Pipelines during /init:

- Add `bitbucket-pipelines.yml`.
- Delete `.github/workflows/ci.yml`.
- Keep the deterministic commands equivalent: install `shellcheck`, set a git identity, run `bash tests/test-scripts.sh`, then run `bash scripts/gate.sh`.

Declare durable gate tool prerequisites under `gate.required_tools` in `config.yaml` as a colon-separated scalar, for example `shellcheck:ruff`. `GATE_REQUIRED_TOOLS` may override it for one command, but do not export it across a larger test or gate run.
