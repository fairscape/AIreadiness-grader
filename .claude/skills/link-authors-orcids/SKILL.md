---
name: link-authors-orcids
description: Post-grade improvement skill for rubric 1.d (Key Actors Identified). Walk the @graph for distinct author/publisher/principalInvestigator strings, interview the user for ORCID and (optionally) ROR URIs, append Person/Organization entities to @graph, rewrite references to use {"@id": "<uri>"} stubs. Validates against fairscape_models.rocrate.ROCrateV1_2 before writing.
---

# Link authors to ORCIDs — rubric 1.d

Rubric 1.d (Key Actors Identified) is scored Partial when authors are present as plain strings but no ORCID URIs are attached. The grader counts `authors_with_orcid_count` — any author whose `@id` or `identifier` is an ORCID URI counts. Partial coverage is fine; the rubric explicitly says missing ORCIDs on people who don't have one don't count against the score.

This skill turns the existing plain-string authors into linked Person entities with ORCIDs (and the publisher into an Organization with ROR where applicable). It does not invent identifiers — every ORCID/ROR comes from the user.

## What to tell the user

> *"Rubric 1.d wants ORCID URIs on authors so attribution is machine-resolvable. Right now most authors on this crate are plain strings. I'll show you the list of distinct people and organizations I found, ask for an ORCID per person (skip is fine — not every researcher has one), and for the publisher I'll ask for a ROR if it's an institution rather than a data archive. Then I'll add Person/Organization entities to the `@graph` and rewrite every reference to use `{\"@id\": \"<uri>\"}` stubs. Before I write, I validate the result against the fairscape_models schema — if anything won't parse I'll tell you and not save."*


> `<crate>` is the `ro-crate-metadata.json` to edit and `<crate_dir>` its directory. Resolve them from the path the user gave, else `ro-crate-metadata.json` in the working directory, else `state.crate_path` if a `.fairscape-state.json` wizard state file is present. Ask if none resolve.

## 1. Read the crate, dedupe actors

`Read` `<crate>` into `crate`. Walk `crate["@graph"]` collecting:

- **Authors**: every distinct string value (or `name` value inside an inline dict) appearing in any `author` field. Track which entity ids reference each author.
- **Publisher**: the root entity's `publisher`. String or dict; capture name + existing identifier if any.
- **principalInvestigator**: root, same shape as author.
- **contributors / contactPoint**: capture for display, but don't push for ORCIDs unless the user wants — these are often role-based and the rubric notes ORCIDs aren't required for them.

Don't include `author` values that are already `{"@id": "<orcid-or-other-uri>"}` reference stubs — those are already linked. Don't include `author` values that are already inline `Person` objects with an `identifier` that contains `orcid.org`.

Show the user the deduped list:

```
Found 8 distinct authors and 1 publisher:

  Authors (referenced by N entities each):
    1. Richa Tiwari            (root + 4 datasets)
    2. Trey Ideker             (root)
    3. Lab Member 3            (root + 12 datasets)
    ...

  Publisher: "University of Virginia Dataverse"   (looks like a data archive — ROR not expected)

  Skipping: 2 author strings already have ORCID @id stubs.
```

## 2. Interview one actor at a time

For each person, ask:

> *"ORCID URI for `<name>`? Paste `https://orcid.org/0000-...`, or say `skip` to leave as a plain string, or `unknown` if they don't have one."*

Accept either the bare digits form (`0000-0002-8534-6407`) or the full URI. Normalize to `https://orcid.org/<digits>`. Validate the digits form matches `^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$` — if not, tell the user the shape isn't an ORCID and ask again.

Optionally collect:
- **affiliation** — free text or a ROR URI. Skip is fine.
- **email** — skip is fine.

Don't push affiliation/email — ask once per person, accept skip immediately.

For the publisher, if the publisher string doesn't look like a recognized data archive (Dataverse, Zenodo, PhysioNet, Figshare, Dryad, OSF), ask:

> *"ROR URI for `<publisher name>`? `https://ror.org/...`, or `skip`."*

If it does look like an archive, mention the rubric's `not_required` clause and don't ask.

For principalInvestigator, same flow as authors.

## 3. Build proposed mutations

For each (name, orcid) pair the user supplied:

1. Append a new entity to `crate["@graph"]`:
   ```json
   {
     "@id": "https://orcid.org/0000-...",
     "@type": "Person",
     "name": "<name>",
     "identifier": "https://orcid.org/0000-..."
   }
   ```
   Plus `affiliation` and `email` if the user filled them. Affiliation may be a plain string OR a `{"@id": "<ror-uri>"}` stub OR an inline Organization. All three shapes are accepted by `fairscape_models.person.Person`.

2. Walk every entity in `@graph`. For each `author` field:
   - If it's a string equal to `<name>`: replace with `{"@id": "<orcid>"}`.
   - If it's a list: replace any matching string element with the same stub. Preserve list order. Dedupe.
   - If it's an inline dict with `name == <name>` and no `@id`: replace the whole dict with the stub.
   - Untouched otherwise.

3. Same for root `principalInvestigator` field (single-valued or list).

For ROR on the publisher, append an Organization entity and rewrite root `publisher` to a reference stub. If publisher was an inline string and the user gave no ROR, leave it alone.

## 4. Show the user the proposed diff

Render concisely:

```
Proposed changes:

  +6 new Person entities in @graph (ORCID @ids)
  +1 new Organization entity in @graph (ROR @id) for the publisher
  ~8 author references rewritten to {"@id": "https://orcid.org/..."} stubs
  ~12 child Dataset author fields updated
  publisher rewritten to {"@id": "https://ror.org/..."}

Skipped: 2 authors said 'unknown' (no ORCID), 1 said 'skip' (won't change).
```

Ask: *"Apply these and save, or adjust first?"*

## 5. Validate before writing

This is the cross-cutting validation contract (matches `fairscape-cli/.../utils/build_utils.py:306`). Build the mutated crate dict in memory, then in a single `Bash` call:

```bash
python -c '
import json, sys
from fairscape_models.rocrate import ROCrateV1_2
crate = json.load(open(sys.argv[1]))
ROCrateV1_2.model_validate(crate)
print("OK")
' <(cat <<JSON
<the proposed crate, pretty-printed>
JSON
)
```

In practice the easier shape is: write the proposed dict to `<crate_path>.proposed` (NOT over the original), validate that file with the same one-liner, then if the validate passes, `os.replace` the proposed file over the original. If it fails, surface stderr to the user, delete the proposed file, and ask whether to retry or skip.

Never overwrite the original until `ROCrateV1_2.model_validate` succeeds. The user's stated concern is that broken edits would silently corrupt the crate — this is the gate.

## 6. Atomic write + state update

On successful validation, `os.replace(proposed_path, crate_path)` — atomic on POSIX.

Append to state:
```json
{
  "improvements": {
    "ran": [..., "link-authors-orcids"],
    "validation_failures": []
  },
  "history": [..., {"ts": "...", "skill": "link-authors-orcids",
                    "summary": "added N Person entities (ORCID); rewrote M author refs"}]
}
```

Tell the user: *"Done. Added `<N>` Person entities with ORCIDs and rewrote `<M>` author references. Crate validated against ROCrateV1_2 before write."*

## Don't

- Don't invent ORCIDs. If the user says `skip` or `unknown`, leave the string. The rubric explicitly says partial coverage is fine.
- Don't push ROR on data-archive publishers. The rubric's `not_required` clause covers this.
- Don't write to `ro-crate-metadata.json` until validation succeeds. The proposed file lives at `<path>.proposed` until then.
- Don't add `Person` entities with the same `@id` twice. If a Person with that ORCID already exists in `@graph`, just reuse the stub.
- Don't touch entries that are already linked (already an `@id` reference stub to an ORCID, or an inline Person with an `identifier` containing `orcid.org`).
