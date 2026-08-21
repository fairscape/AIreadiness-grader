---
name: register-embargoed-dataset
description: Add Dataset entities for raw inputs (or unreleased outputs) that aren't physically in the crate but need to exist so provenance is complete. Sets `contentUrl: "Embargoed"` on each entity and appends to the crate `@graph`. Supports single or bulk-by-template registration (e.g. one Dataset per participant). Invoked by provenance-tracking when the user describes a pipeline step whose inputs/outputs are sensitive, too large, temporary, restricted, or otherwise missing.
---

# Register embargoed Datasets

A crate often documents a derived data product whose raw inputs aren't included — PHI-bearing sensor streams, video that's too large to host, lab notebooks that never got digitized, intermediate files that were deleted. Without entries for those inputs, every downstream Computation has an empty `usedDataset` and the provenance chain dead-ends. This skill writes `Dataset` entries with `contentUrl: "Embargoed"` so the chain is complete — the crate honestly reports that the file existed, who/what produced it, and why it isn't here, even though nobody can download it.

The convention `contentUrl: "Embargoed"` is already wired through `fairscape_models` — `subcrate_utils._process_dataset` recognizes it and surfaces it as an access type; the LakeDB test crate uses it canonically. This skill is the user-facing front door.

## When to invoke this skill (and when NOT)

**Invoke when:**
- A pipeline step in `remote-provenance-tracking` consumes data the user can describe but isn't a file in the crate (raw sensor signal, raw imaging, biospecimen records, paper questionnaires).
- A step *produced* an output that was never released (deleted, restricted, superseded) but exists as a logical artifact the downstream world should know about.
- The user explicitly says the input data is "sensitive", "temporary", "too big to publish", "we couldn't include the raw", "embargoed", "the script doesn't run on shareable data", or similar.

**Do NOT invoke when:**
- The file exists in the crate and the user just hasn't given a `@id` yet (search the `@graph` for it).
- The file is on a public URL (Dataverse / PhysioNet / Zenodo) — that's a normal Dataset with the URL as `contentUrl`, not embargoed.
- The user is describing a step's *software* — software embargoes go through `register-software` (the same `"Embargoed"` value works there; not this skill's scope).
- The user is fully skipping provenance. If they aren't documenting steps, they don't need embargoed inputs either.

## Preconditions

- `.fairscape-remote-state.json` exists with `state.crate_path` valid.
- The crate `ro-crate-metadata.json` is readable and has a `@graph`.
- This skill is being invoked from inside `remote-provenance-tracking` (Phase 4) — the orchestrator that adds these Datasets is the one that links them into Computations.

## What to tell the user before any commands run

If invoked because a step's input isn't in the crate, frame the choice plainly:

> *"`<input name>` isn't in the crate — and that's expected when the raw data is sensitive, too large to publish, or was temporary. I can add a placeholder Dataset for it with `contentUrl: \"Embargoed\"`. The placeholder records what the data **was** (name, format, who produced it, why it isn't here) without claiming a download link. The Computation that consumes it will then have a real `usedDataset` to point at, and the provenance chain stays complete. Want to do that?"*

If the user says no, drop back to `remote-provenance-tracking` — it'll let them either pick from existing crate Datasets or skip the step.

## 1. Pick the granularity

The most important question. Get this right before generating any entities, because the granularity determines how the Computation will link inputs.

> *"At what level should I create placeholders? A few common choices:*
> *  • **per-participant** — one Dataset per subject (e.g. 253 entries, one per patient). Right when the pipeline ran per-subject and the paper reports N participants.*
> *  • **per-participant + per-modality** — separate placeholders for each signal stream a subject produced (e.g. PPG vs. accelerometer vs. EEG = 3 × N). Right when different signals had different acquisition hardware or different sensitivity classifications.*
> *  • **one bulk entry for the whole raw set** — a single Dataset that stands in for the entire missing corpus. Right when the pipeline treated it as one undifferentiated input.*
> *Which fits this dataset?"*

Take the answer literally — don't second-guess. The granularity of the placeholders should match the granularity at which the downstream step will list them as inputs. If a step's `usedDataset` ought to be a list of 253 IDs (one per subject), make 253 placeholders. If it should be a single ID, make one.

## 2. Gather the template (ask once, not per-entity)

Whether single or bulk, you collect one set of fields and either emit one Dataset or expand the template N times.

1. **name_template** — the name of one entity, with `{N}` or `{participant_id}` as the variable part if bulk.
   - Single: `"Raw PPG signal — full cohort"`.
   - Bulk: `"Raw PPG signal — participant {N}"` with `N` ranging over `1..253` (or a list of IDs the user pastes).
2. **description** — 1–3 sentences. **Must explain why this data isn't in the crate.** Acceptable reasons: "sensitive PHI removed before publication", "temporary recording deleted after labeling", "too large to host (raw 1 kHz PPG, ~50 GB total)", "restricted by IRB / DUA", "lost / never digitized". Be specific — `"embargoed"` alone is not informative.
3. **author** — who produced it (the recording device, the lab, the participant). Default to the crate root author when unknown.
4. **fileFormat** — best guess for what the file *would have been*. Common ones for missing raw:
   - PPG / ECG / waveform → `application/octet-stream` (or device-specific like `application/edf` if you know).
   - Imaging → `image/tiff` or `application/dicom`.
   - Text questionnaire → `text/plain`.
   - When genuinely unknown, `application/octet-stream` is fine.
5. **datePublished** — when the data was *acquired*, not today's date. Ask the user; if they don't know, use the dataset's publication year (`state.crate_metadata.datePublished` or root entity).
6. **keywords** — always include `"raw"` and `"embargoed"`. Add user-supplied terms.
7. **role** — is this a raw input (the pipeline started here) or an unreleased intermediate/output? Default: raw input. If output, the orchestrator will link the Computation that "generated" it.
8. **participant_ids** (bulk only) — accept a range (`1-253`), a comma list (`p001,p002,...`), or a glob the user pastes. Show the expansion ("this expands to 253 IDs — confirm?") before continuing.

## 3. Build the Datasets

Use `fairscape_models.dataset.Dataset` for validation. GUIDs use `generate_guid("dataset", <name>)` from `aireadiness_wizard.ids` — same convention every other registration skill uses.

```python
from fairscape_models.dataset import Dataset
from aireadiness_wizard.ids import generate_guid

def build_one(name: str, description: str, author, file_format: str,
              date_published: str, keywords: list[str]) -> Dataset:
    return Dataset.model_validate({
        "@id": generate_guid("dataset", name),
        "@type": ["prov:Entity", "https://w3id.org/EVI#Dataset"],
        "name": name,
        "author": author,
        "description": description,
        "datePublished": date_published,
        "keywords": keywords,
        "format": file_format,          # alias for fileFormat
        "version": "1.0",
        "contentUrl": "Embargoed",
        "generatedBy": [],
        "derivedFrom": [],
    })
```

For bulk, loop over the participant IDs and substitute `{N}` / `{participant_id}` in both the `name_template` and (if it has a placeholder) the `description`. Each entity gets its own GUID — collect them in a list.

**Critical**: do NOT set `contentUrl` to `"file:///..."` or a fabricated URL. The literal string `"Embargoed"` is the contract — downstream tooling (`subcrate_utils`, `plausibility-check`, the JS dataset model) all key off it.

## 4. Append to the crate @graph (atomic write)

Mirror the pattern from `remote-provenance-tracking` and `remote-schema-infer`:

```python
import json, os, tempfile
with open(crate_path) as f:
    crate = json.load(f)
graph = crate["@graph"]
for ds in datasets:
    graph.append(json.loads(ds.model_dump_json(by_alias=True, exclude_none=True)))

fd, tmp = tempfile.mkstemp(dir=os.path.dirname(crate_path), suffix=".json")
with os.fdopen(fd, "w") as f:
    json.dump(crate, f, indent=2)
os.replace(tmp, crate_path)
```

If the crate root entity (the one with `@id: "./"`) has a `hasPart` list, append each new GUID as `{"@id": guid}`. Many importer-generated crates omit `hasPart` and rely on `@graph` membership alone — if it's missing, don't synthesize one.

## 5. Persist to state

Append (or extend) `state.provenance.embargoed_datasets`:

```json
"provenance": {
  "embargoed_datasets": [
    {"guid": "ark:59853/dataset-raw-ppg-signal-participant-1-<squid>",
     "name": "Raw PPG signal — participant 1",
     "role": "raw_input",
     "reason": "PHI — raw 50 Hz PPG removed before publication",
     "group_template": "Raw PPG signal — participant {N}",
     "participant_id": "1"}
    // ... one entry per emitted Dataset
  ]
}
```

`group_template` lets a later re-entry recognize "you already created the PPG group, add ECG too?" without re-asking the granularity question. `role` distinguishes raw_input (most common) from unreleased_output.

Append a `history` entry:
```json
{"ts": "...", "skill": "register-embargoed-dataset",
 "summary": "Added <N> embargoed Datasets for <group_template>"}
```

## 6. Return control to the caller

Print **one line** for the user — don't dump the full graph:

```
Added 253 embargoed Datasets (Raw PPG signal — participant 1..253). contentUrl=Embargoed.
```

Then yield back. The Computation that consumes these is built by `remote-provenance-tracking` section 3 — that skill now has the GUIDs in `state.provenance.embargoed_datasets` to pull from when it asks about inputs.

## What you must NOT do

- **Don't invent a download URL.** Not a `file:///` to a path that doesn't exist, not a hypothetical S3 URL, nothing. The string is `"Embargoed"` verbatim.
- **Don't omit the reason** in `description`. "Embargoed" alone tells a reader nothing; "PHI raw PPG, removed before publication per IRB protocol 2019-441" tells them everything.
- **Don't create Computations or Software here.** Datasets only. The caller wires them up.
- **Don't register the same logical group twice.** Before emitting, check `state.provenance.embargoed_datasets` for a matching `group_template`. If found, ask whether to extend (different modality, more participants) or treat as done.
- **Don't use this for files that exist on a public URL.** Those are normal Datasets — go through the importer or `register-dataset` with the URL.
- **Don't backdate or fabricate `author`.** If the user genuinely doesn't know, default to the crate root author and note it in `description` ("authorship as recorded by the acquisition device").

## Resume behavior

On re-entry, `state.provenance.embargoed_datasets` lists everything already registered. If the caller asks for inputs again, surface those names first (so the user picks from existing placeholders rather than creating duplicates). If the user wants to add more — different modality, more participants — re-enter at section 1 with the granularity question.
