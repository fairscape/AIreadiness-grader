---
name: remote-schema-infer
description: Phase 2 of the remote-source wizard. Group `state.tabular_files` by extension + name template, sample ONE representative per group (full download for parquet/hdf5; range-GET for CSV/TSV), run `fairscape-cli schema infer`, then back-link the resulting schema entity to every Dataset in the group via `evi:Schema`. Avoids 3,840-file storms when a dataset is partitioned by patient/sample/etc.
---

# Remote schema infer — Phase 2

Most published datasets follow a partitioning pattern: 50 patient files, 200 sample CSVs, 3,800 per-subject parquets. They all share **one schema**. Querying each file individually is expensive (download + LLM turns) and wasteful (you get the same answer 3,840 times). This skill groups by name template and infers each group once.

## What to tell the user before any commands run

Before showing the proposed grouping, set context with one paragraph:

> *"Right now the crate knows your files **exist** but not what's inside them. A 'schema' here means: the column names of a tabular file plus a type for each column (integer, number, string, boolean, …). The schema tool can read CSV, TSV, Parquet, and HDF5 — anything else gets skipped.*
>
> *Two strategies depending on format:*
> *• **CSV / TSV** — text, row-oriented. I can Range-GET the first ~5 MB of the file from the repository, which is enough rows to detect types without downloading the whole thing.*
> *• **Parquet / HDF5** — binary, with the schema stored in a file **footer**. Range-truncating breaks the footer, so for these I do a full download of one representative per group.*
>
> *Either way, I sample once per group and apply the schema to every member of the group, so a 3,840-file dataset costs 1 schema-infer call instead of 3,840."*

The grouping proposal that follows then makes sense — the user understands why grouping matters.

## Preconditions

- `.fairscape-remote-state.json` exists with `state.crate_path` valid.
- `state.tabular_files` is non-empty. If empty, set `state.phase = "schemas_done"` and tell the user "No tabular files to infer schemas for — skipping."

## 1. Propose a grouping, then negotiate it with the user

A name-template heuristic is a useful first guess but it'll get edge cases wrong. The user knows their data — make this collaborative.

### 1a. Auto-propose

For each entry in `state.tabular_files`, compute a **template** from its `name`:
- Strip the extension(s) — keep them in a separate field.
- Replace runs of digits with `#` (e.g. `1000600.parquet` → template `#######`, ext `parquet`).
- Replace UUID-shaped substrings (`[0-9a-f]{8}-...`) with `<uuid>`.
- Lowercase the rest.

Group by `(template, extension)`. For each group, record:
```json
{
  "id": "g1",                    // short id for the conversation: g1, g2, …
  "template": "#######",
  "extension": "parquet",
  "count": 3840,
  "representative": {"@id": "...", "name": "1000600.parquet", "contentUrl": "https://..."},
  "members": [list of @ids],
  "size_summary": {"min": 1200000, "median": 1430000, "max": 1900000},
  "skipped": "compressed"        // only when extension ends in .gz
}
```

Representative = smallest-by-`size_bytes` member (or the first when sizes are missing) — smaller is faster to sample and likelier to succeed.

### 1b. Show the proposal and ask

Render groups as a short table and **ask the user to confirm or revise**. Do not proceed silently.

```
Here's my best guess at how to group the 3863 tabular files. For each group I can
sample ONE representative and apply the schema to every member — or I can sample
every file individually if you think they really differ.

  g1 |  3840 × #######.parquet      | median 1.4 MB | repr: 1000600.parquet
  g2 |    12 × <prefix>_summary.csv | median 25 KB  | repr: site1_summary.csv
  g3 |     3 × <prefix>.tsv         | median 4 KB   | repr: README.tsv
  g4 |     8 × #######.csv.gz       | SKIPPED — gzip

For each group I'd like one decision:
  • SAMPLE-ONE — sample the rep, apply the schema to all (default for groups > 3).
  • SAMPLE-EACH — sample every file in this group separately (use when you suspect different schemas).
  • SPLIT g1 by <pattern> — break a group into smaller ones; tell me the splitting rule.
  • MERGE g2,g3 — combine groups you think share a schema even though the names differ.
  • SKIP g4 — don't infer for this group at all.

Defaults (you can just say "go"):
  g1 SAMPLE-ONE   g2 SAMPLE-ONE   g3 SAMPLE-EACH (n=3 is small)   g4 SKIP

Anything to change?
```

Walk the user through their answer one step at a time. Common collaboration patterns to handle:

- **"What's actually in g1?"** — list 5–10 example names (don't dump 3840). If they look heterogeneous to the user, suggest SAMPLE-EACH or ask them to name a splitting pattern.
- **"Split g1 — half are vitals, half are labs"** — ask what distinguishes them (a filename prefix? a folder path? a size band?). Apply the split, show the resulting subgroups, confirm.
- **"Merge g2 and g3 — they're both summary tables"** — combine into one group. Pick the smaller rep.
- **"Just sample everything individually"** — accept. Convert every entry into a size-1 group. Warn that this will run schema-infer N times.
- **"What's the size of group X?"** — show min/median/max from `size_summary`.

Persist the **final** grouping (after user revisions) to `state.schema_groups` before sampling anything. Each group keeps its `id` for the duration of the session — referring back to "g1" in resume should still work.

```json
"schema_groups": [
  {"id": "g1", "template": "#######", "extension": "parquet", "count": 3840,
   "policy": "SAMPLE-ONE", "representative_id": "ark:...", "members": [...], ...},
  ...
]
```

`policy` is one of `SAMPLE-ONE`, `SAMPLE-EACH`, `SKIP`. `SAMPLE-EACH` groups behave like multiple SAMPLE-ONE groups of size 1 in section 2.

## 2. For each group in `state.schema_groups`, sample per policy

Skip groups with `"policy": "SKIP"` or `"skipped": "compressed"`.

For `policy == "SAMPLE-EACH"`, iterate the members as if each were its own SAMPLE-ONE group of size 1 — every file gets its own sampling + schema-infer + back-link. Use the file's own name as the schema name default.

For `policy == "SAMPLE-ONE"` (the common case), ask the user once per group: "Sample `<rep.name>` (`<size>`) — name the schema?" Defaults: name = `<template>.<ext>` title-cased (e.g. `"Parquet files"`), description = `"Inferred from <rep.name>, sampled from <source.kind> on <date>. Applied to <count> files matching <template>.<ext>."`. Accept edits.

### Sampling strategy by extension

- **CSV / TSV**: range-GET first 5 MiB; the helper trims the trailing partial line.
  ```
  Bash python -m aireadiness_wizard.remote_fetch "<rep.contentUrl>" "<crate>/.cache/samples/<rep.name>" --max-bytes 5242880
  ```
- **Parquet / HDF5**: **full download** — schema lives in the footer, range-truncating breaks it. Pass `--max-bytes 0 --no-trim-tail`. Warn the user if the representative is > 50 MB; offer to swap to a smaller member or skip the group.
  ```
  Bash python -m aireadiness_wizard.remote_fetch "<rep.contentUrl>" "<crate>/.cache/samples/<rep.name>" --max-bytes 0 --no-trim-tail
  ```

The sample file path **must preserve the original extension** so `schema infer`'s file-type detector works (`.parquet`, `.csv`, etc.).

Ensure `.cache/` is in `<crate>/.gitignore` — add the line if missing.

### Run schema infer

```
Bash fairscape-cli schema infer \
  --rocrate-path "<crate>" \
  --name "<n>" \
  --description "<d>" \
  "<sample_path>" \
  "<crate>/schemas/<template>.<ext>.schema.json"
```

On failure, surface stderr and offer: retry with a different representative, skip the group, or stop. Don't auto-retry.

### Back-link the schema to every Dataset in the group

Tell the user what's about to happen and why:

> *"`schema infer` just added one Schema entry to the crate. But the 3,840 Dataset entries don't know about it yet — each Dataset needs an `evi:Schema` pointer back to the new Schema's `@id`. I'll walk the crate JSON and set that pointer on every file in this group. After this step, a downstream consumer reading any file can look up its schema in one hop."*

The CLI registers the new schema entity in `<crate>/ro-crate-metadata.json`. We still need to point each Dataset's `evi:Schema` field at it.

1. `Read` `<crate>/ro-crate-metadata.json`.
2. Find the new Schema entity (most recent entity with `@type` containing `EVI:Schema` or `Schema`, or — more reliably — the entity whose `@id` matches the GUID printed by `schema infer`'s stdout if it surfaces one; otherwise the schema with `name == <n>`).
3. For each `@id` in the group's `members`, find the matching `@graph` entry and set `"evi:Schema": {"@id": "<schema_id>"}`. Preserve any other fields. If the entry already has `evi:Schema`, leave it alone (don't clobber explicit user choices).
4. Atomic write: temp file + `os.replace`.

This is the second place we mutate `ro-crate-metadata.json` directly (the AI-Ready enrichment phase is the other). Keep it tight and don't touch unrelated entries.

## 3. State write

Append per processed group to `state.schemas`:
```json
{
  "group_id": "g1",
  "schema_id": "ark:.../schema-...",
  "schema_path": "<abs>/schemas/<template>.<ext>.schema.json",
  "name": "...",
  "description": "...",
  "representative_id": "ark:.../<rep>",
  "sample_path": "<abs>/.cache/samples/<rep.name>",
  "sampled_bytes": <int>,
  "full_download": true|false,
  "back_linked_member_ids": ["ark:...", "..."]
}
```

`state.schemas_done` lists **group ids** (`"g1"`, `"g2"`, …) — that's what resume should check.

Persist after each group succeeds.

## 4. Finish

- Set `state.phase = "schemas_done"`.
- Tell the user: `"Inferred <K> schemas across <K> groups, back-linked to <M> Dataset entries. <G> gzip groups skipped."`

## Resume behavior

If `state.schema_groups` already exists, **reuse it** — don't re-propose grouping on every run. Walk only the groups whose id is NOT in `state.schemas_done`. If the user wants to redo a group, ask them to remove its id from `schemas_done` first. If the user wants to re-grouping from scratch, clear both `state.schema_groups` and `state.schemas_done`.

## Don't

- Don't proceed with the auto-grouping silently. Always show it to the user and accept revisions before sampling. The user's domain knowledge beats the template heuristic.
- Don't default to SAMPLE-EACH on big groups. SAMPLE-ONE is the right default for groups of > 3 alike files; only escalate to SAMPLE-EACH on user request or when sampling clearly fails on the representative.
- Don't range-truncate parquet or hdf5 — the footer holds the schema. Full download (`--max-bytes 0 --no-trim-tail`) or skip.
- Don't write `evi:Schema` to any entity that already has one set — the user might have curated it.
- Don't run `schema infer` on `.gz` — the CLI won't read it.
