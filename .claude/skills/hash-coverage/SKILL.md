---
name: hash-coverage
description: Post-grade improvement skill for rubric 3.c (Verifiable). Walk Dataset and Software entities, compute md5 and sha256 for any whose contentUrl resolves to a local file and which lack a hash, set the entity's top-level md5/sha256 fields. Validates against fairscape_models.rocrate.ROCrateV1_2 before writing.
---

# Hash coverage — rubric 3.c

Rubric 3.c (Verifiable) is scored Partial when some Dataset/Software entities carry checksums but most don't, or when only Datasets are hashed and Software isn't. The grader computes `hash_coverage = entities_with_hash / total_hashable_entities` over Dataset + Software entities; > 0.5 maps to Substantive. The extractor reads any of `md5`, `sha256`, `contentChecksum`, or `hash` properties.

`DigitalObject` (the parent class of Dataset, Software, MLModel) already declares typed `md5`, `sha256`, `hash` fields, so we set those directly — no extra namespace needed.

This skill is pure mechanical — no user content input beyond "yes / what size cap".

## What to tell the user

> *"Rubric 3.c wants cryptographic hashes on Datasets and Software so a downstream consumer can verify the bytes they received are the bytes you shipped. I'll walk every Dataset and Software entity, find the ones whose `contentUrl` resolves to a local file, stream-hash them with md5 and sha256, and set the entity's `md5` and `sha256` fields directly. Files over a size cap I'll skip unless you raise the cap. Remote-only files get skipped — those would need to be downloaded first. Validated against the fairscape_models schema before write."*


> `<crate>` is the `ro-crate-metadata.json` to edit and `<crate_dir>` its directory. Resolve them from the path the user gave, else `ro-crate-metadata.json` in the working directory, else `state.crate_path` if a `.fairscape-state.json` wizard state file is present. Ask if none resolve.

## 1. Enumerate hashable entities

`Read` `<crate>`. Walk `@graph` for entities whose `@type` (string or list) contains `Dataset`, `Software`, `MLModel`, or `https://w3id.org/EVI#Dataset`/`#Software`. Exclude the root crate entity.

For each candidate, bucket:

- **Already hashed** — entity has any of `md5`, `sha256`, `contentChecksum`, `hash` set non-null. Skip.
- **`contentUrl` resolves to a local file that exists** (apply memory `project_rocrate_content_url.md`: strip `file:///` if present, join against crate root). Candidate.
- **`contentUrl` is `http(s)://`** or unset or `"Embargoed"` → remote/unhashable. Skip; report count.

Apply a size cap. Default `500 MB`. If `Dataset.contentSize` is set, parse it (handle units `KB`/`MB`/`GB`); otherwise `os.stat` the local file.

Show:

```
Hashable entities:
  total Dataset + Software: 1064
  - 761  already hashed → skipping
  - 0    Software with hash → ⚠ uneven coverage (rubric flags this)
  - 8    remote contentUrl → skipping
  - 295  local, eligible, ≤500 MB → will hash
  - 0    local, oversized        → will skip unless cap raised
```

Highlight the "Software with hash" line specifically — the rubric calls out per-type coverage and Software-without-hashes is a common gap (see thingslee evidence: 71.5 % overall but 0 % on Software).

## 2. Confirm

> *"Hash `<N>` files now? Estimated total bytes: `<S>` GB. Size cap is `<500>` MB per file — change it (`--cap 2G`) or `skip`."*

If the user changes the cap, re-bucket and reconfirm.

## 3. Hash, streaming

For each eligible entity, in sequence (don't parallelize — IO-bound and we don't need a thread pool for this scale):

```python
import hashlib
def hash_file(path):
    md5 = hashlib.md5(); sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):  # 1 MiB
            md5.update(chunk); sha256.update(chunk)
    return md5.hexdigest(), sha256.hexdigest()
```

Progress: emit one line per N files (`N = max(1, total // 20)`) so the user sees motion: `"hashed 60/295 (20%) — sha256 of <ark>: a3f1..."`. Stream output, don't buffer for thousands of files.

On each entity, set the typed fields directly:

```python
entity["md5"] = md5_hex
entity["sha256"] = sha256_hex
```

The `DigitalObject` model declares both as `Optional[Union[str, List[str]]]` (root `ROCrateMetadataElem` declares `md5: Optional[str]` and `sha256: Optional[Union[str, List[str]]]`). String form is canonical for a single file.

If a hash computation fails (file vanished mid-run, permissions denied), collect the error, don't touch the entity, continue to the next.

## 4. Validate before writing

Build the mutated crate, write to `<crate_path>.proposed`, run:

```bash
python -c '
import json, sys
from fairscape_models.rocrate import ROCrateV1_2
ROCrateV1_2.model_validate(json.load(open(sys.argv[1])))
print("OK")
' <crate_path>.proposed
```

On success: `os.replace`. On failure: surface stderr, delete the proposed file, ask retry or skip.

## 5. State write

```json
{
  "improvements": {"ran": [..., "hash-coverage"]},
  "history": [..., {"ts": "...", "skill": "hash-coverage",
                    "summary": "hashed N files; coverage 71.5% → 99.3%"}]
}
```

Report the new coverage to the user with the old coverage in parentheses (`entities_with_hash / total_hashable_entities`), one line:

> *"Done. Hashed `<N>` files. Coverage `<old>` → `<new>`. Crate validated."*

## Don't

- Don't recompute hashes for entities that already have one. The user can ask for `--overwrite`-style behavior if they really want; the default is conservative.
- Don't hash files over the size cap silently — surface the count and let the user raise it.
- Don't use `contentChecksum`. The model already has typed `md5` and `sha256` fields on every DigitalObject; use them.
- Don't parallelize. Sequential is fine at this scale and keeps progress reporting clean.
- Don't write to `ro-crate-metadata.json` until validation succeeds.
- Don't follow symlinks pointing outside the crate root. Stat first, refuse if the resolved real path escapes.
