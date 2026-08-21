---
name: register-dataset
description: LEGACY (used only by `fairscape-rocrate-wizard-legacy`). Capture a single distinct file as a Dataset in entity-centric wizard state. For new projects use the unified `fairscape-rocrate-wizard` — its local-folder branch builds a manifest with one row per file (no per-file interview). For a folder of similar files use register-folder-of-alike instead.
---

# Register a single dataset

Use for one file the user wants to document on its own — a single CSV of results, a hand-curated reference, a one-off output. **Do not use for folders of similar files** (use `register-folder-of-alike`).

## Inputs you need from the user

Ask, one at a time, and infer when you can. The user may already have given you some of these in the surrounding wizard turn — don't re-ask if you have the answer.

1. **What is this file?** A one-line description in their words.
2. **Where is it?** A path. If they gave a label like "the cleaned data," look at `scan` for candidates and propose: "Is it `processed/cleaned.csv`?"
3. **Where did it come from?** Author / source. Default to the crate-level author if unspecified.
4. **Is it a starting input or something a step produced?** This sets `is_raw_input` (true if no computation generated it within the project).

You should NOT ask for: format (infer from extension), date (default today), version (default "1.0"), GUID (generate).

## Inferring fields

- **format**: extension → MIME type using the table in `emit-build-script` (e.g. `.csv` → `text/csv`). If unknown, `application/octet-stream`.
- **contentUrl**: if path is inside the project, `file:///<relative path>`. If it's a URL the user gave, use that. If the file is private/embargoed, `"Embargoed"`.
- **datePublished**: today, ISO format.
- **version**: `"1.0"` unless user said otherwise.

## GUID generation

Use `python -c 'from aireadiness_wizard import generate_guid; print(generate_guid("dataset", "<name>"))'` via `Bash`, or compute inline matching `aireadiness_wizard.ids.generate_guid`. Format: `ark:59853/dataset-<slug>-<squid>`.

## Write to state

Append to `state.datasets`:
```json
{
  "guid": "ark:59853/dataset-...",
  "name": "...",
  "author": "...",
  "description": "...",
  "datePublished": "YYYY-MM-DD",
  "keywords": [],
  "format": "text/csv",
  "version": "1.0",
  "contentUrl": "file:///processed/cleaned.csv",
  "is_raw_input": true,
  "user_label": "cleaned data"
}
```

`user_label` is what the user called it in conversation — useful for matching when they refer back ("link the cleaned data into this step"). Append a `history` entry.

After writing, tell the user **one line**: `added "<name>" as <input/output>`. Don't dump the full record.
