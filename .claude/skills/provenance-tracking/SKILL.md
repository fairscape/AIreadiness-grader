---
name: provenance-tracking
description: Phase 4 of the unified wizard. Capture what computational steps produced the derived files in the crate — software run, datasets consumed, datasets produced. Works against any source kind (local folder, Dataverse, PhysioNet, Figshare, generic manifest). Appends Software and Computation entities to ro-crate-metadata.json and runs `fairscape-cli augment link-inverses` to fill in inverse properties (generatedBy, usedByComputation, wasDerivedFrom).
---

# Provenance tracking — Phase 4

A freshly imported crate lists files but says nothing about how they came to exist. The Provenance criterion (rubrics 1.a–1.d) scores low because the graph has no `Computation` entities and no `generatedBy` / `wasDerivedFrom` / `usedByComputation` edges. This skill collects, from the user, one Computation per pipeline step and links inputs / software / outputs into the @graph, then calls `fairscape-cli augment link-inverses` to fill in inverse properties automatically.

Works the same for all source kinds — the crate shape after Phase 1 is identical whether the import came from Dataverse, PhysioNet, Figshare, generic remote manifest, or local folder. The interview model and state writes are unchanged.

The point is **documenting steps, not files**. One `Computation` can wrap many inputs and many outputs — if 50 raw CSVs were cleaned by the same script into 50 cleaned CSVs, that's one Computation, not 50.

## What to tell the user before any commands run

Set context with one paragraph:

> *"This step records what happened to the data — which software ran on which inputs to produce which outputs. Right now the crate lists your files but doesn't connect them, so anyone looking at it can't tell which file is a raw input and which is a downstream product. We'll go step by step: for each computational step in your pipeline, I'll ask what software ran (ideally a GitHub or Zenodo link so it stays reachable), which datasets it consumed, and which datasets it produced. A 'step' is one logical operation — if the same script ran over 50 files to produce 50 outputs, that's **one step** with 50 inputs and 50 outputs, not 50 steps. After we're done I'll run a tool that fills in the reverse links (so each output dataset gets a `generatedBy` pointer back at the step that made it), and the Provenance criterion in grading will actually have something to score against."*

Then flag the embargo path so the user knows it exists before they hit it:

> *"One more thing — datasets often come from raw inputs that aren't in the published crate (sensitive PHI, temporary recordings, files too large to host). That's fine. When you describe a step whose input isn't a file in the crate, I'll offer to add a placeholder Dataset with `contentUrl: \"Embargoed\"` so the provenance chain still has something to link. The placeholder records what the data was and why it isn't here — it doesn't pretend the file is downloadable. Most pipelines need at least one of these at the raw-acquisition layer."*

## Preconditions

- `.fairscape-remote-state.json` exists with `state.crate_path` valid.
- `state.phase` is `"rai_done"` (or `"provenance_tracked"` on re-entry to add more steps).
- The crate `@graph` is non-empty and has at least one Dataset.

## 1. Offer to register provenance — or skip

Ask once, plainly:

> *"Register provenance now, or skip to grading?"*

If the user skips, set:
```json
"provenance": { "skipped": true }
```
and `state.phase = "provenance_tracked"`. Append a `history` entry, then stop. The grading phase will run on whatever provenance the importer already captured.

If the user says yes, continue.

## 2. Identify the source datasets

Read `state.crate_path` and walk `@graph` for entities whose `@type` includes `Dataset` (or `EVI:Dataset` / `https://w3id.org/EVI#Dataset`). Build a list of `{guid, name, contentUrl}` for each.

**Source datasets** are the starting points before any computation took place — the raw inputs the pipeline began with. If the crate has hundreds of Datasets, summarize them by name template (reuse the `#######` / `<uuid>` collapsing from `remote-schema-infer` section 1a) so the user can pick groups rather than scrolling. Show no more than ~30 lines at a time.

Frame it:

> *"Of these N files, which are **source datasets** — the starting point before any computation? Anything *not* listed as a source I'll treat as something a computation produced. Pick by name or paste the names; use a name template like `vitals_*.csv` if there's a whole group."*

Persist to `state.provenance.source_dataset_ids` as a flat list of `@id` strings. If the user can't decide ("not sure — they all came together"), accept "all of them" and move on; computations can still link them as inputs without producing anything new yet.

## 3. The computation loop

Now repeat: for each computational step, gather the inputs below, build the entities, and append. Tell the user upfront they can stop at any time — every step persists before moving on.

> *"For each step in your pipeline I need: a short name, a one-sentence description, what software ran (a GitHub or Zenodo link is best), the inputs it used, and the outputs it produced. Remember: one **step** even if it ran 50 times in a loop. Stop me whenever you're done — what we have so far is saved."*

### 3a. Step name and description

- **name** — 1–8 words, e.g. "Clean raw measurements".
- **description** — 1 sentence; what the step did and why. Must be ≥ 10 chars (Computation pydantic constraint).

### 3b. Software

Ask, in this order:

1. *"Is there a GitHub or Zenodo (or other external) link for the software that ran this step?"*
   - If yes: capture URL. `source_kind` = `"github"` / `"zenodo"` / `"other"` from URL inspection.
2. *"If it's not external, is the script in the crate folder?"*
   - If yes: capture relative path inside the crate. `source_kind` = `"local"`. `contentUrl` = `file:///<crate-relative-path>` (mirroring `register-software`'s rule).
3. *"No software (manual step)?"*
   - Allowed. Record the step as a `Computation` with empty `usedSoftware` and put the manual description into `Computation.description`. Skip Software creation entirely.

If software *is* identified, before creating it: check `state.provenance.software` for an existing entry with the same `source_url` or the same `name`. If found, reuse its `guid` and do not register again. Tell the user: *"Reusing the same script as step `<earlier-step-name>`."*

Otherwise gather the remaining Software fields:

- **name** — default: the URL's last path segment or the local filename.
- **author** — default to the crate root author (`@graph[0].author` or `state.crate_metadata.authors[0]`).
- **version** — default `"1.0"`.
- **description** — 1 sentence ≥ 10 chars; what the software does.
- **format** — for local files infer from extension (`.py` → `text/x-python`, `.r/.R` → `text/x-r`, `.sh/.bash` → `application/x-sh`, `.ipynb` → `application/x-ipynb+json`, `.jl` → `text/x-julia`). For external URLs, ask the user; default `application/octet-stream`.
- **dateModified** — today's date, ISO (`datetime.utcnow().date().isoformat()`).
- **keywords** — accept a comma-separated list; default to `["software", <step name>]`.

GUID: `generate_guid("software", name)` from `aireadiness_wizard.ids`. Build via:

```python
from fairscape_models.software import Software
sw = Software.model_validate({
    "@id": guid,
    "@type": ["prov:Entity", "https://w3id.org/EVI#Software"],
    "name": name,
    "author": author,
    "version": version,
    "description": description,
    "format": fmt,                # alias for fileFormat
    "dateModified": date_iso,
    "contentUrl": url_or_file_uri,
    "keywords": keywords,
})
```

### 3c. Inputs

Multi-select from:
- `state.provenance.source_dataset_ids` (always available as inputs),
- the `generated` of every Computation registered so far in `state.provenance.computations` (later steps consume earlier outputs),
- any other Dataset in the crate the user names that isn't already in the lists above,
- placeholders the user has previously registered via `register-embargoed-dataset` (listed in `state.provenance.embargoed_datasets`).

Show them by `name` not `@id`. Resolve back to `@id` before building the Computation.

**If the user names an input that isn't in any of these lists** — and the reason is that the raw data is sensitive, too large, temporary, restricted, or otherwise not in the crate on purpose — invoke the `register-embargoed-dataset` skill. That skill asks the user about the right granularity (per-participant, per-modality, or one bulk entry), writes the placeholder Datasets with `contentUrl: "Embargoed"`, and persists them to `state.provenance.embargoed_datasets`. When it returns, the new GUIDs are available here as inputs — pick them up and continue building the Computation.

Symptoms that mean "invoke register-embargoed-dataset":

- *"The raw signal isn't in the crate, only the cleaned version is."*
- *"We can't release the source data — it's PHI / under DUA / under IRB."*
- *"The recordings were temporary, deleted after labeling."*
- *"There's no file — the device wrote directly into HealthKit and we only kept the export."*
- The paper describes a raw acquisition step but the crate has no corresponding Dataset entry.

What NOT to do in those cases: don't refuse the step, don't silently leave `usedDataset` empty, and don't fabricate a `file:///` path. Route through `register-embargoed-dataset` so the chain is honest and complete.

### 3d. Outputs

Multi-select Datasets that the step produced. The output `@id` must exist in the crate `@graph` (or in `state.provenance.embargoed_datasets`). If the user names something that isn't there, there are two paths:

1. **The output was produced but never published** (intermediate file the user deleted, restricted artifact, lost output). Invoke `register-embargoed-dataset` with `role: "unreleased_output"` so the step still has something to link via `generated`. The placeholder is honest: it records what the step produced and why it isn't in the crate.
2. **The output is a file the user forgot to register first.** Say so plainly and refuse: *"`<name>` isn't in the crate yet. If it's a file you have, add it to the crate first (it needs a real `contentUrl`). If it doesn't exist as a file anywhere, I can add an embargoed placeholder — but only do that if the output really was produced and just isn't shareable."*

Don't silently create a regular Dataset entry — that's outside this skill's responsibility. The user can run a separate registration flow if they have a real file to add.

Outputs can overlap with inputs only when the step modifies a Dataset in place (rare). Warn the user if they do this.

### 3e. runBy and dateCreated

- **runBy** — default to crate root author.
- **dateCreated** — default today, ISO.
- **command** — optional; ask only if the user volunteers one.

### 3f. Build the Computation and append

```python
from fairscape_models.computation import Computation
comp = Computation.model_validate({
    "@id": comp_guid,
    "@type": ["prov:Activity", "https://w3id.org/EVI#Computation"],
    "name": name,
    "description": description,
    "runBy": run_by,
    "dateCreated": date_iso,
    "usedSoftware": [{"@id": sw_guid}] if sw_guid else [],
    "usedDataset": [{"@id": x} for x in input_ids],
    "generated": [{"@id": x} for x in output_ids],
})
```

Append both entities (Software first, then Computation) to the crate `@graph` with an atomic write — same pattern as `remote-schema-infer` step 2:

```python
import json, os, tempfile
with open(crate_path) as f:
    crate = json.load(f)
graph = crate["@graph"]
if sw is not None:
    graph.append(json.loads(sw.model_dump_json(by_alias=True, exclude_none=True)))
graph.append(json.loads(comp.model_dump_json(by_alias=True, exclude_none=True)))
# Also add to root_dataset hasPart so the crate root references the new entities
root = next(e for e in graph if e.get("@id") == "ro-crate-metadata.json")  # or: the dataset with @id="./"
# (Match the crate's existing root convention — usually the entity with @id "./" )
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(crate_path), suffix=".json")
with os.fdopen(fd, "w") as f:
    json.dump(crate, f, indent=2)
os.replace(tmp, crate_path)
```

Persist to state after every successful append:

```json
"provenance": {
  "source_dataset_ids": [...],
  "software": [
    {"guid": "ark:59853/software-...", "name": "...",
     "source_kind": "github|zenodo|local|other", "source_url": "..."}
  ],
  "computations": [
    {"guid": "ark:59853/computation-...", "name": "...",
     "usedSoftware": ["..."], "usedDataset": ["..."], "generated": ["..."]}
  ],
  "embargoed_datasets": [
    {"guid": "ark:59853/dataset-...", "name": "...", "role": "raw_input|unreleased_output",
     "reason": "...", "group_template": "...", "participant_id": "..."}
  ]
}
```

`embargoed_datasets` is owned by `register-embargoed-dataset`; this skill only reads from it (to surface placeholder names in 3c/3d) and never writes to it directly.

Append `history`:
```json
{"ts": "...", "skill": "remote-provenance-tracking", "summary": "Recorded step '<name>' with N inputs and M outputs"}
```

Render a one-line graph so the user sees the step materialize:
```
Step "Clean raw measurements":
  raw_*.csv  →  clean.py  →  cleaned_*.csv
```

Ask: *"Another step, or done?"* Loop back to 3a if another. Otherwise continue to 4.

## 4. Run link-inverses

Before invoking, tell the user what it does:

> *"That's the user-facing half. The Computations now point at their inputs and outputs, but the inputs and outputs don't yet point back at the Computation. I'll run `fairscape-cli augment link-inverses`, which reads the EVI ontology, finds every `owl:inverseOf` property pair (like `usedDataset` ↔ `usedByComputation`, `generated` ↔ `generatedBy`), and fills in the reverse direction on every targeted entity. It's idempotent — safe to run again later."*

Then:

```bash
fairscape-cli augment link-inverses "<state.crate_dir>"
```

On success, record `state.provenance.link_inverses_run_at = <iso utc now>`. On failure, surface stderr; do not advance the phase. Offer the user the option to fix the issue (often a missing ontology file) and retry.

## 5. Finish

Set `state.phase = "provenance_tracked"`. Summarize for the user:

> *"Recorded N computations and M software entries across X distinct datasets. Inverse links applied. The Provenance criterion in grading will now have entities to score against."*

## Resume behavior

On re-entry with `state.phase == "provenance_tracked"`:
- If `state.provenance.skipped == true`, treat as done — the orchestrator should move past this phase. Don't re-ask.
- If `state.provenance.computations` is non-empty, the checkpoint surfaces *"You already recorded N computations. Add more steps, edit, or move on?"* "Add more" re-enters the loop at section 3a; "move on" no-ops. Editing is out of scope for v0.1 — direct the user to edit `ro-crate-metadata.json` by hand.

If `state.phase == "rai_done"` and `state.provenance` is missing, this is a first-run — proceed from section 1.

## What you must NOT do

- Don't create new Dataset entries *directly from this skill*. The only legal way to add a Dataset during Phase 4 is by delegating to `register-embargoed-dataset` — and only when the user is describing a real raw input or unreleased output that isn't in the crate for a stated reason (sensitive, large, temporary, restricted). Never silently invent a Dataset because a step needs one.
- Don't silently re-register Software the user already pointed at in a prior step. Match on `source_url` or `name` and reuse the GUID.
- Don't proceed to link-inverses if any Computation append failed mid-loop. Stop, surface the error, leave state inconsistent for the user to inspect.
- Don't invoke `register-software` or `create-computation` (the local-wizard skills). They write a different state file and assume a different graph shape.
- Don't ask the user to choose between `Computation` / `Activity` / `Experiment` / `Sample` types in v0.1. Use `Computation` even for manual steps (empty `usedSoftware`). Adding the other Activity subtypes is a future enhancement — see TODO below.

## TODO (future)

- Allow Activity / Experiment / Sample entity types from `fairscape_models/{activity,experiment,sample}.py` for non-computational steps (manual annotation, wet-lab experiments, sample acquisition). v0.1 collapses all of these into Computation-with-empty-software to keep the flow simple.
- In-place edit of an already-registered Computation (currently the user must edit `ro-crate-metadata.json` by hand).
- Auto-detection of common software from URLs (read the GitHub repo description / Zenodo metadata to pre-fill name + description).
