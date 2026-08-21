---
name: register-software
description: LEGACY (used only by `fairscape-rocrate-wizard-legacy`). Capture a script (.py, .R, .sh, .ipynb, etc.) that the user ran as a Software entity in entity-centric wizard state. For new projects use the unified `fairscape-rocrate-wizard` — Phase 4 (`provenance-tracking`) handles software entries against the imported crate's @graph, source-kind-agnostic.
---

# Register software

A Software entity is a script the user ran. Use this when the user says "I ran process.py", "the cleaning was done by clean.R", etc.

## When to invoke

- The user names a `.py / .R / .sh / .bash / .ipynb / .jl` file as the thing that did a step.
- A new computation needs to point at a script you haven't registered yet.

If the script is already in `state.software`, **do not re-register** — reuse its GUID.

## Inputs you need

1. **Path.** "Where is `process.py`?" Look in `scan.files_by_category.scripts` first.
2. **What it does.** One sentence — feeds into `description`.
3. **Author.** Default crate-level author.
4. **Version.** Optional; default `"1.0"`.

Don't ask about format (infer from extension), date (use today as `dateModified`), or GUID (generate).

## Inferring fields

- `format`: `.py` → `text/x-python`; `.r .R` → `text/x-r`; `.sh .bash` → `application/x-sh`; `.ipynb` → `application/x-ipynb+json`; `.jl` → `text/x-julia`.
- `contentUrl`: `file:///<relative path>` if inside the project. If the script lives outside (e.g. cluster path), record the path as a `file://` URL anyway and flag it for the user ("note: this script isn't inside the project folder — it'll be referenced but not bundled").

## GUID

`ark:59853/software-<slug(name)>-<squid>` via `aireadiness_wizard.generate_guid("software", name)`.

## Write to state

Append to `state.software`:
```json
{
  "guid": "ark:59853/software-process-py-...",
  "name": "process.py",
  "author": "Justin",
  "description": "Cleans raw measurements and emits processed.csv",
  "dateModified": "2026-05-04",
  "version": "1.0",
  "format": "text/x-python",
  "contentUrl": "file:///scripts/process.py"
}
```

Tell the user one line: `added script "process.py"`. Append `history`.
