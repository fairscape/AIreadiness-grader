---
name: link-subjects-ontologies
description: Post-grade improvement skill for rubric 2.a (Semantics). Read the root crate's keywords, propose ontology IRIs (MeSH, EDAM, NCIt, GO, Cellosaurus, OBO Foundry) for each, let the user accept/edit/skip per term, then append DefinedTerm entities to @graph and link them via the root `about` field. Validates against fairscape_models.rocrate.ROCrateV1_2 before writing.
---

# Link subjects to ontology IRIs — rubric 2.a

Rubric 2.a (Semantics) is scored Partial when the root crate has topical keywords but no subject terms grounded in a standard ontology. The grader counts `ontology_term_count` — entries in `about` / `subjectOf` / `keyword` (across root and Datasets) whose IRI hostname matches `meshb.nlm.nih.gov`, `purl.obolibrary.org`, `edamontology.org`, etc. Going from 1 → 2 needs at least a handful of grounded terms on the root, ideally with per-Dataset coverage on the major datasets.

This skill enriches root `about` first (easier, higher impact). Per-Dataset enrichment is an optional follow-up the skill offers but does not push.

## What to tell the user

> *"Rubric 2.a wants subject terms grounded in standard biomedical / scientific ontologies — MeSH, EDAM, NCIt, GO, Cellosaurus — not just free-text keywords. The free-text keywords stay; we add a parallel structured layer in `about`. I'll go through your keywords one at a time, propose an ontology IRI when I'm reasonably confident, and you accept it, edit it, or skip. I won't fabricate — if I don't know a good match I'll say so. Then I'll add `DefinedTerm` entities to the `@graph` and link them from the root `about` field. Validated against the fairscape_models schema before write."*


> `<crate>` is the `ro-crate-metadata.json` to edit and `<crate_dir>` its directory. Resolve them from the path the user gave, else `ro-crate-metadata.json` in the working directory, else `state.crate_path` if a `.fairscape-state.json` wizard state file is present. Ask if none resolve.

## 1. Read the crate

`Read` `<crate>`. Find the root Dataset entity (the one whose `@id` matches the `about["@id"]` of the `ro-crate-metadata.json` descriptor entity).

Collect:
- `root["keywords"]` — the list to enrich.
- `root.get("about", [])` — existing `about` entries. Skip any keyword that already maps to an existing DefinedTerm with a known ontology IRI.
- Existing DefinedTerm entities anywhere in `@graph` (to dedupe).

## 2. Propose IRIs per keyword

For each keyword, propose one ontology IRI based on what you know. Pick the most authoritative source for the domain:

- **Biomedical / clinical** → MeSH (`https://meshb.nlm.nih.gov/record/ui?ui=<id>`).
- **Bioinformatics tooling, formats, ops** → EDAM (`http://edamontology.org/<id>`).
- **Genes, proteins, processes** → GO / Uniprot / OBO Foundry (`http://purl.obolibrary.org/obo/<id>`).
- **Cell lines** → Cellosaurus (`https://web.expasy.org/cellosaurus/<id>`).
- **Diseases** → MONDO via OBO, or NCIt.
- **Imaging / measurement** → NCIt or OBI.

When uncertain, propose the closest reasonable match AND say so. When you genuinely don't know, output `unknown` rather than guess.

Render the proposals as a batch the user can scan and edit:

```
Proposals — accept (y), edit (paste a different IRI), or skip (n) per row:

  keyword                  proposed IRI                                                   source
  proteomics               http://edamontology.org/topic_0121                             EDAM
  mass spectrometry        http://purl.obolibrary.org/obo/MS_1000031                      OBO PSI-MS
  paclitaxel               https://meshb.nlm.nih.gov/record/ui?ui=D017239                 MeSH
  endotag                  unknown                                                        —
  MDA-MB-468               https://web.expasy.org/cellosaurus/CVCL_0418                   Cellosaurus
  ...
```

Then ask:

> *"Accept the proposals as shown, or walk through them one at a time?"*

If "one at a time", iterate: show the proposal, ask y/n/edit/skip per term. Accept the user's typed IRI as-is — they may know a better source than you do.

## 3. Build DefinedTerm entities + link from root.about

For each accepted (keyword, iri) pair:

1. Choose a `name` (the original keyword string) and infer `inDefinedTermSet` from the hostname:
   - `meshb.nlm.nih.gov` → `{"@id": "https://www.nlm.nih.gov/mesh/"}`
   - `purl.obolibrary.org/obo/GO_...` → `{"@id": "http://purl.obolibrary.org/obo/go.owl"}`
   - `edamontology.org` → `{"@id": "http://edamontology.org/"}`
   - `web.expasy.org/cellosaurus` → `{"@id": "https://www.cellosaurus.org/"}`
   - Anything else: `{"@id": "<scheme-base>"}` derived from the IRI hostname.

2. Try to extract a `termCode` — the local id within the scheme:
   - MeSH: the `ui=<id>` query param value (e.g. `D017239`).
   - OBO: the path tail (e.g. `GO_0008152`).
   - EDAM: the path tail (e.g. `topic_0121`).
   - Otherwise: omit.

3. Append the entity to `crate["@graph"]`:
   ```json
   {
     "@id": "<the ontology IRI>",
     "@type": "DefinedTerm",
     "name": "<keyword>",
     "termCode": "<local id, if extracted>",
     "inDefinedTermSet": {"@id": "<scheme>"}
   }
   ```

4. Append `{"@id": "<the ontology IRI>"}` to `root["about"]` (create the list if missing — the model declares it as `Optional[List[Union[IdentifierValue, DefinedTerm, str]]]`).

5. **Leave `root["keywords"]` alone.** The free-text keywords coexist with the structured about; the grader reads both.

If a DefinedTerm with that `@id` already exists in `@graph`, don't add a duplicate — just add the reference stub to `about`.

## 4. Optional: per-Dataset coverage

After the root list is built, ask once:

> *"Rubric 2.a goes from Partial to Substantive faster with per-Dataset coverage on the major Datasets. Want me to propagate the relevant DefinedTerms to the `about` field of every Dataset in the crate? I can map keyword-overlap heuristically and let you confirm per group."*

If yes: walk Datasets, propose subject terms based on each dataset's name + description overlap with the keyword list, show the user one batch confirmation, then add `about` stubs. If no: continue.

## 5. Validate before writing

Same contract as the other leaves. Build the mutated dict, write to `<crate_path>.proposed`, run:

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
  "improvements": {
    "ran": [..., "link-subjects-ontologies"]
  },
  "history": [..., {"ts": "...", "skill": "link-subjects-ontologies",
                    "summary": "added K DefinedTerm entities; linked from root about (+J per-Dataset)"}]
}
```

Tell the user: *"Done. Added `<K>` ontology-grounded subject terms and linked them from the root `about` field. Crate validated."*

## Don't

- Don't invent IRIs. When a keyword has no obvious ontology mapping, propose `unknown` and skip.
- Don't replace `keywords`. Free-text and structured terms coexist.
- Don't write to `ro-crate-metadata.json` until validation succeeds.
- Don't add a DefinedTerm whose `@id` already exists in `@graph`. Reuse the existing one.
- Don't push per-Dataset enrichment if the root pass added < 3 terms — the user gets diminishing returns on partial coverage and a noisier interview. Save it for when they have a real list.
