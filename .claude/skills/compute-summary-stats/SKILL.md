---
name: compute-summary-stats
description: Post-grade improvement skill for rubric 2.b (Statistics). For tabular Datasets whose contentUrl resolves to a local file, shells out to `fairscape-cli augment summary-stats` (which populates rowCount/columnCount/contentSize plus child SummaryStats Datasets linked via hasSummaryStatistics). Validates the resulting crate against fairscape_models.rocrate.ROCrateV1_2.
---

# Compute summary statistics — rubric 2.b

Rubric 2.b (Statistics) is scored Partial when tabular Datasets exist but few or none carry `hasSummaryStatistics` (or the lifted fields `rowCount` / `columnCount` / `contentSize`). The grader counts `datasets_with_summary_stats_count` and `datasets_with_size_count` against `tabular_dataset_count` — so coverage on the majority of tabular Datasets is what moves the score from 1 to 2.

The CLI already does the actual computation. This skill is a thin wrapper: it filters out the Datasets whose data isn't local (those can't be summarized without first downloading), interviews the user about which to process, runs the CLI, and re-validates.

## What to tell the user

> *"Rubric 2.b wants row/column counts and per-column statistics on tabular Datasets. fairscape-cli already has a `summary-stats` command that reads each file, computes the stats, and writes a child SummaryStats Dataset linked via `hasSummaryStatistics`. The catch is that this only works for Datasets whose `contentUrl` points at a local file or a URL the runtime can fetch. I'll show you the list of tabular Datasets, mark which are local-resolvable, and ask which to process. Remote-only Datasets get skipped (you can come back to those after downloading). After the CLI runs, I re-load the crate and validate it against the fairscape_models schema as a defense-in-depth check."*


> `<crate>` is the `ro-crate-metadata.json` to edit and `<crate_dir>` its directory. Resolve them from the path the user gave, else `ro-crate-metadata.json` in the working directory, else `state.crate_path` if a `.fairscape-state.json` wizard state file is present. Ask if none resolve.

## 1. Enumerate the work

`Read` `<crate>`. Walk `@graph` for `Dataset` entities (excluding the root crate). Bucket each:

- **Already has `hasSummaryStatistics`** → skip; report count.
- **Non-tabular format** (image/binary/sequencing/audio — anything other than csv/tsv/parquet/h5ad/jsonl/xlsx/xls) → skip; report count. Detected via `encodingFormat` or filename suffix.
- **Tabular, contentUrl resolves locally** → candidate.
- **Tabular, contentUrl is `http(s)://`, `file:///<path-not-in-crate>`, embargoed, or missing** → "remote-only", report separately.

For "resolves locally": apply the rule from memory `project_rocrate_content_url.md` — `contentUrl` of `file:///<crate-relative-path>` strips the `file:///` prefix and joins against the crate root. Confirm the resulting path exists.

Show the user one block:

```
Found tabular Datasets:
  506 total
  - 12  already have hasSummaryStatistics → skipping
  - 0   non-tabular (image / vendor binary) → skipping
  - 487 tabular, contentUrl is local → eligible
  - 7   tabular, contentUrl is remote (https://...) → cannot process without downloading
```

## 2. Ask which to process

If `eligible == 0`, tell the user *"No locally-resolvable tabular Datasets — nothing to do here. Remote stats are out of scope for v1."* and exit.

Otherwise:

> *"Process which? `all` (487), a range like `1-50`, comma-separated indices, or `skip`. Also a size cap: skip files over `<N>` MB? Default 500 MB."*

Apply the user's selection + size cap. Read `Dataset.contentSize` (if set) or stat the local file to decide. Surface a final count: *"Will process N Datasets, skipping K oversized."*

## 3. Run the CLI

The CLI command is per-Dataset, so iterate the IDs:

```bash
fairscape-cli augment summary-stats --rocrate-path <crate_dir> --id <ark> --http-timeout 60
```

Or, if processing all eligible: drop the `--id` flag and the CLI processes every tabular Dataset that doesn't already have stats. Pass `--overwrite` only if the user explicitly asked to re-compute existing.

Run sequentially. After each call, show the user the CLI's `✓ <ark> ← <rows> × <cols>, <size>` line. If a row fails (read error, format unsupported), the CLI prints to stderr and continues — collect those and report once at the end:

```
Processed 478 of 487 Datasets.
Skipped:
  - <ark1>: read failed — Parquet column 12 unsupported dtype 'fixed_size_binary'
  - <ark2>: read failed — file truncated (HTTP 206 partial)
  ...
```

## 4. Re-validate the crate

The CLI already mutates `ro-crate-metadata.json` directly (it's an `augment` command — that's its job). As a defense-in-depth check, re-read the crate and validate:

```bash
python -c '
import json, sys
from fairscape_models.rocrate import ROCrateV1_2
ROCrateV1_2.model_validate(json.load(open(sys.argv[1])))
print("OK")
' <crate>
```

If validation passes (it should — the CLI uses the same models): continue.

If validation fails: this is bad. The CLI shouldn't write an invalid crate. Tell the user *"The CLI wrote the crate but it doesn't validate against ROCrateV1_2 — surfacing the pydantic error for triage. The file at `<crate_path>` is in whatever state the CLI left it; consider running `git diff` if you have version control. This needs to be reported to the fairscape-cli maintainers."* and append the error to `state.improvements.validation_failures`.

Do not attempt to auto-revert — the CLI's mutation is the source-of-truth shape it intends; rolling back risks losing work. Surface and stop.

## 5. State write

```json
{
  "improvements": {"ran": [..., "compute-summary-stats"]},
  "history": [..., {"ts": "...", "skill": "compute-summary-stats",
                    "summary": "computed stats for N tabular Datasets via fairscape augment summary-stats; K skipped"}]
}
```

Tell the user: *"Done. Computed summary stats for `<N>` Datasets — each now has rowCount / columnCount / contentSize on the source plus a linked SummaryStats child. Crate re-validated."*

## Don't

- Don't try to compute stats for remote files yourself. The CLI handles `http(s)://` contentUrl when the runtime can reach it; if those fail, surface the skip — don't reinvent the read path.
- Don't pass `--overwrite` unless the user explicitly asked. Re-computing is cheap on small files and pricey on large ones.
- Don't trust the CLI to never break validation — always re-validate. Defense in depth.
- Don't run the CLI in parallel across Datasets. The `augment` command writes back to the same `ro-crate-metadata.json` and would race.
- Don't ask the user to install dependencies. If the CLI raises ImportError for pandas / pyarrow, surface the error and stop — env setup is out of scope.
