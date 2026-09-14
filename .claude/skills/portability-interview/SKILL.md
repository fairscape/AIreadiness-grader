---
name: portability-interview
description: Post-grade improvement skill for rubric 6.c (Portable). Walk Software and Computation entities, interview the user for containerImage / softwareRequirements / hardwareRequirements (batched by template so we don't ask 50 times for the same answer), set the fields. Validates against fairscape_models.rocrate.ROCrateV1_2 before writing.
---

# Portability interview — rubric 6.c

Rubric 6.c (Portable) is scored Partial when most formats are common but compute-environment refs are missing on Software/Computation entities. The grader looks for `container_references` (Dockerfile / Docker image digests / Singularity recipes / conda environment files / requirements files attached to Software or Computation entities) and `hardware_requirement_text` (GPU, memory, OS, runtime).

This skill batches the interview by template — if many scripts share the same environment, ask once, apply many.

## What to tell the user

> *"Rubric 6.c wants compute-environment info on your Software and Computation entities so a downstream user can reproduce a working environment. The fields are `containerImage` (a Docker / Singularity reference), `softwareRequirements` (path to your `environment.yml` / `requirements.txt` / `Pipfile.lock`, or a list of name+version pairs), and `hardwareRequirements` (free text — GPU model, RAM floor, OS). I'll group entities that look like they share an environment and ask once per group, so we don't interview 50 times. Validated against the fairscape_models schema before write."*


> `<crate>` is the `ro-crate-metadata.json` to edit and `<crate_dir>` its directory. Resolve them from the path the user gave, else `ro-crate-metadata.json` in the working directory, else `state.crate_path` if a `.fairscape-state.json` wizard state file is present. Ask if none resolve.

## 1. Enumerate Software and Computation entities

`Read` `<crate>`. Collect every entity in `@graph` whose `@type` (string or list) contains `Software`, `https://w3id.org/EVI#Software`, `Computation`, or `https://w3id.org/EVI#Computation`.

For each, capture what's already there: `containerImage`, `softwareRequirements`, `hardwareRequirements`, `runtimeRequirements`, `softwareVersion`. Track which entities still lack each of those three fields.

## 2. Group by template

Cluster entities likely to share an environment. Heuristics:

- **By file extension** of the Software's `contentUrl` or filename (`.py` → likely shared Python env; `.R` → likely shared R env; `.sh` → shell, often shares OS env).
- **By name prefix / common substring** — `clean_data.py`, `clean_features.py`, `clean_signal.py` plausibly share an env.
- **By directory** — Software entities whose `contentUrl` is under the same crate sub-directory.

Don't be clever beyond that — show the user the proposed groups and let them confirm/merge/split:

```
Proposed environment groups (you can merge / split):

  Group A — 14 Python scripts under `scripts/sleep_eeg/`
    register_subject.py, preprocess.py, run_inference.py, ...

  Group B — 8 R scripts under `scripts/stats/`
    fit_models.R, summarize.R, ...

  Group C — 1 shell driver under `scripts/run_all.sh`

Sound right? Say `merge A,C` / `split A` / `ok`."
```

Accept their adjustments. Then iterate groups.

## 3. Interview per group

For each group, ask one set of questions; apply to every entity in the group.

> *"Group A — 14 Python scripts. Same compute environment for all of them?"*
> *"  containerImage (Docker / Singularity URI, or `skip`)?"*
> *"  softwareRequirements — paste a path to `environment.yml`/`requirements.txt`/etc., or paste a list like `numpy==1.26, pandas==2.1, scipy==1.11`, or `skip`?"*
> *"  hardwareRequirements — free text (`GPU: NVIDIA A100; RAM ≥ 32 GB; Linux x86_64`) or `skip`?"*

Field shapes when writing:

- `containerImage` — string (URI). The model has `extra="allow"` so it lands as an extra field; no schema penalty.
- `softwareRequirements` — accepts either a string (path to a requirements file, relative to crate root) or a list of objects `[{"name": "numpy", "version": "1.26"}, ...]`. If the user pasted a string with `,`-separated `name==version` pairs, parse to the list form. If the user pasted a path, store as a string.
- `hardwareRequirements` — string (free text).

If the user has additional groups with different envs, repeat. If the user says `same as Group A`, copy the values across.

## 4. Show proposed diff

```
Proposed changes:

  Group A — 14 Software entities
    + containerImage:        "docker://ghcr.io/yourorg/sleep-eeg:1.2"
    + softwareRequirements:  ["numpy==1.26", "pandas==2.1", "scipy==1.11", "mne==1.5"]
    + hardwareRequirements:  "GPU: NVIDIA A100; RAM ≥ 32 GB; Linux x86_64"

  Group B — 8 Software entities
    + containerImage:        "docker://rocker/r-ver:4.3.1"
    + hardwareRequirements:  "RAM ≥ 16 GB"

  Group C — 1 Software entity
    (skipped — user declined)
```

Ask: *"Apply, or adjust first?"*

## 5. Validate before writing

Build mutated crate, write `<crate_path>.proposed`, run the same one-liner used by the other leaves:

```bash
python -c '
import json, sys
from fairscape_models.rocrate import ROCrateV1_2
ROCrateV1_2.model_validate(json.load(open(sys.argv[1])))
print("OK")
' <crate_path>.proposed
```

On success: `os.replace`. On failure: surface stderr, delete the proposed file, ask retry or skip.

## 6. State write

```json
{
  "improvements": {"ran": [..., "portability-interview"]},
  "history": [..., {"ts": "...", "skill": "portability-interview",
                    "summary": "set container/env/hardware on N Software entities across K groups"}]
}
```

Tell the user: *"Done. Set containerImage / softwareRequirements / hardwareRequirements on `<N>` Software entities across `<K>` groups. Crate validated."*

## Don't

- Don't ask one-question-per-entity when 50 entities share an env. Always group first.
- Don't insist on a container if the user only has a `requirements.txt` — softwareRequirements alone is meaningful evidence.
- Don't fabricate hardware requirements ("probably needs 8 GB"). If the user says skip, leave it. The rubric doesn't require all three fields.
- Don't write to `ro-crate-metadata.json` until validation succeeds.
- Don't conflict-write with `compute-summary-stats` — these skills run sequentially via the router, so each one re-reads the file. Don't share in-memory state between leaves.
