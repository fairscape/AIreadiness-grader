# What works and what breaks on outside JSON-LD

Run: `fairscape-evidence <dir> --no-network`, 23 upstream documents, 2026-08-20.
Grader commit: `aaa12f8` on `evidence-presentation`.

Numbers below come from `results/summary.tsv` (grader output) and
`analyze_shape.py` (a census of the raw JSON-LD, independent of the grader).

## Headline

**Nothing crashes. Most things score zero.** All 23 examples exit 0 and emit a
complete 28-criterion presentation. No criterion raised an exception on any
input (`err` column is 0 across the board), and no criterion came back with an
empty evidence list. The tool is robust and it is confidently wrong: 15 of 23
documents produce a presentation over **zero entities**, and the mechanical
estimator still assigns them a score — a Dryad DataCite record and a Croissant
MNIST descriptor both come out at 2–3 points out of 46 with basis strings like
"no PID detected" and "no checksums found".

For a grader whose output feeds a human reviewer or an LLM, a wrong zero is
worse than a crash. Every break below manifests as a false negative.

| | Examples | Entities the grader sees | Estimate |
| --- | --- | --- | --- |
| FAIRSCAPE crates (`examples/ai-readi` etc.) | — | all | works |
| RO-Crate / Workflow Run Crate | 8 | root + 3–17% of the graph | 7–13 / 46 |
| Croissant, schema.org, Bioschemas, PROV, CEDAR | 15 | **0** | 0–3 / 46 |

## Breaks, in leverage order

### 0. The filename is load-bearing

`cli.py:35` and `crate.py:207` hard-code `ro-crate-metadata.json`. A Croissant
`metadata.json`, a DataCite `.jsonld`, a `croissant.json` from the HF API —
none of them can be handed to the CLI at all. Every non-RO-Crate directory in
this corpus needed a symlink before it would even start.

### 1. No `@graph`, no data

`crate.py:209` does `doc.get("@graph", [])`. Fifteen of the 23 documents are
*not* flattened JSON-LD — they are a single tree with a top-level `@type`.
For all of them the graph is `[]`, root detection falls through to `{}`, and
`bundle.root.get(...)` returns `None` for every field the criteria ask for.

That is the entire non-RO-Crate half of the corpus: all 4 Croissant files,
DataCite, Dataverse, Zenodo, both ESIP docs, both Bioschemas docs, PhysioNet,
CEDAR, both PROV docs.

`probe_wrap.py` measures the cost. It wraps each flat document in a minimal
`{descriptor, @graph:[root, …hoisted typed objects]}` envelope — no grader
changes — and re-runs:

| | as fetched | wrapped |
| --- | --- | --- |
| `datacite-dryad` | 0 ents, 2/46 | 15 ents, 11/46 |
| `dataverse-harvard` | 0 ents, 2/46 | 9 ents, 12/44 |
| `zenodo-record-3541888` | 0 ents, 2/46 | 26 ents, 11/44 |
| `croissant-bigcode-the-stack` | 0 ents, 3/46 | 32 ents, 11/38 |
| `esip-sos-full` | 0 ents, 3/46 | 34 ents, 10/46 |
| `physionet-mimic3-demo` | 0 ents, 2/46 | 6 ents, 8/44 |
| `bioschemas-nanocommons` | 0 ents, 2/46 | 2 ents, 9/46 |

Accepting a non-flattened document — treat the top-level object as the root,
walk nested typed objects into the graph — is the single highest-leverage
change in this list. It is also what a real JSON-LD flattening step would give
for free.

### 2. `File` is not a known type

`_TYPE_TOKENS` (`crate.py:46`) knows the EVI vocabulary — `Dataset`,
`Computation`, `Software`, `Schema`, `Sample`, `Instrument`, `Experiment` —
and nothing else. `File` is the single most common `@type` in the corpus: 978
occurrences, more than twice the next. Every one of them lands in `Other` and
is dropped from `dataset_total`, so all the per-dataset percentages divide by
a denominator that excludes the actual files.

```
wrroc-compss               623 entities → Other:617, Dataset:1
wrroc-wfexs-nfcore-rnaseq  852 entities → Other:834, Dataset:17
wrroc-autosubmit           126 entities → Other:117, Dataset:7
```

In RO-Crate, `Dataset` means *directory* and `File` means *file*. The grader
reads it as the reverse of what the data says.

The knock-on is concrete. `wrroc-wfexs-nfcore-rnaseq` carries **279 `File`
entities with a `sha256`** — `sha256` is already in `HASH_FIELDS`. Criterion
3.c reports `Hash coverage = 0.0` / `no checksums found` / estimate **0**,
purely because those entities were typed `Other` before the hash check ran.

Same story for the rest of the `Other` bucket:

| Token | Count | Should read as |
| --- | --- | --- |
| `File` | 978 | data entity |
| `PropertyValue` | 438 | parameter value / variable |
| `FormalParameter` | 150 | schema-ish (Workflow RO-Crate) |
| `SoftwareSourceCode` | 148 | Software |
| `SoftwareApplication` | 92 | Software |
| `cr:Field` | 71 | Schema field (Croissant) |
| `ContainerImage` | 66 | Container |
| `cr:FileObject` / `cr:FileSet` | 14 | data entity (Croissant) |
| `CreateAction` | 11 | Computation |
| `cr:RecordSet` | 10 | Schema (Croissant) |
| `ComputationalWorkflow` | 8 | Software |
| `DataDownload` | 5 | distribution (schema.org) |

`Software` count is 0 on every single example in this corpus, including
`wrroc-compss` which has 55 `SoftwareSourceCode` entities.

### 3. The Action provenance model is invisible

`PROV_LINK_FIELDS` covers EVI spellings (`generatedBy`, `usedByComputation`,
`usedSoftware`, …) and a few `prov:` ones. Workflow Run RO-Crate — the
dominant real-world provenance profile — does not use any of them. It uses
schema.org Actions:

```json
{ "@id": "#654421a2-…", "@type": "CreateAction",
  "instrument": {"@id": "packed.cwl"},
  "object":  [{"@id": "327fc7ae…"}, {"@id": "#pv-main/reverse_sort"}],
  "result":  [{"@id": "b9214658…"}] }
```

`object` / `result` / `instrument` / `agent` appear in every WRROC crate here
and in `rocrate-paper-2021`. None are in `PROV_LINK_FIELDS`,
`ACTIVITY_INPUT_FIELDS`, or `ACTIVITY_OUTPUT_FIELDS`. Result: `Computation`
and `Experiment` counts are 0 for all eight RO-Crates, and criterion 1.a
reports `Datasets carrying provenance links (EVI/PROV terms) = 0.0` on crates
that exist *specifically* to record provenance.

Across the whole corpus the EVI field names score:
`generatedBy` 0, `usedByComputation` 0, `usedSoftware` 0, `usedDataset` 0,
`EVI:Schema` 0, `hasSummaryStatistics` 0. The only PROV hit anywhere is one
`prov:wasGeneratedBy` in `esip-sos-full`.

### 4. Field-name mismatches

The loader reads a set of names that mostly do not appear outside FAIRSCAPE.
Counts across the corpus:

Counts are occurrences as *data*; `@context` alias definitions are excluded
(all four `format` and `md5` "hits" in a naive scan are Croissant context
aliases, not values).

| Grader reads | Hits | What upstream uses instead | Hits |
| --- | --- | --- | --- |
| `format` | **0** | `encodingFormat` | 422 |
| `contentUrl` | 17 | relative `@id` (RO-Crate) / `distribution` → `DataDownload` | 7 + 978 `File` |
| — | — | `contentSize` | 963 |
| `md5` | **0** | `sha256` (already read) | 284 |
| — | — | `spdx:checksum` (ESIP) | 1 |
| `EVI:Schema` | **0** | `FormalParameter` (150), `cr:Field` (71), `cr:RecordSet` (10), `variableMeasured` (2) | 233 |
| `hasSummaryStatistics` | **0** | — | — |

The `format` miss cascades: criterion 2.b decides tabular-vs-not from
`stats.formats`, so `croissant-titanic` — a CSV table with 19 declared fields
— is estimated **N/A, "no tabular formats in the crate"**. Same for every
Croissant and Dataverse example.

`contentUrl` deserves its own note: in RO-Crate a local file's location *is*
its `@id`, and remote files use `contentUrl` only sometimes. Reading
`contentUrl` alone means `dataset_with_contenturl = 0` for all eight
RO-Crates, which drives criterion 6.b (computationally accessible) to 0.

### 5. Criterion 2.a reads only `DefinedTerm` entities

This one is narrower than it looks, because the *other* vocabulary check works
fine. `crate.py:296` scans the raw metadata text against `ONTOLOGY_HOSTS`, and
that scan runs even when the graph is empty — `esip-sos-astromaterials` (0
entities) still reports `Standard vocabulary references found in metadata =
True` off its `purl.obolibrary.org` URIs, and 0.c estimates 2.

Criterion 2.a does not use that. It reads `bundle.defined_terms`, which is
populated only by walking `@graph` for `DefinedTerm` entities. So 2.a reports
`Controlled-vocabulary terms present = False` for 22 of 23 examples — the sole
hit being `rocrate-paper-2021` and its SPAR/pso terms. `esip-sos-astromaterials`
carries 7 `DefinedTerm` entities with ODM2 and QUDT URIs and still reports
False, because break #1 means they are never loaded.

`ONTOLOGY_HOSTS` itself is also narrow for this corpus. It covers
`purl.obolibrary.org` (82 occurrences here) and `identifiers.org` (29), but has
no entry for hosts that appear repeatedly in these files: `orcid.org` (350),
`w3id.org` (156), `spdx.org` (28), `ror.org` (26), `purl.org/spar` (18),
`qudt.org` (6). Author and licence identifiers in particular go unrecognised
everywhere.

## What already works

Not everything is broken, and the parts that work are the parts that read the
document as text or read `@context` rather than walking the entity graph.

- **No exceptions, ever.** `pipeline.py:48` catches per-criterion, and no
  criterion needed it. Malformed-ish input (`ogc-prov-llm` has no `@context`
  at all; `cedar-instance` has no `@type` on the instance) is handled.
- **Criterion 6.a (Standardized)** is the best-behaved check in the tool. It
  reads `conformsTo` and the context, and correctly identified Croissant on
  `croissant-titanic` — *"declared standards: Croissant, Dublin Core,
  schema.org; deterministic validator known: Croissant"*, estimate 2 — with
  zero entities loaded. It also got RO-Crate right on `wrroc-wfexs-nfcore-rnaseq`.
- **Criterion 0.c (Interoperable)** reads `@context` plus a raw-text ontology
  scan, so it works with zero entities loaded. It enumerated QUDT / Dublin Core
  / XSD out of `esip-sos-astromaterials`, PROV and ProvONE out of
  `esip-sos-full`, and found Ensembl in `wrroc-wfexs-nfcore-rnaseq`.
- **Root detection via the descriptor** (`descriptor.about` → root) works on
  all 8 RO-Crates including the 1.1/1.2/1.3 context variants and the `@base`
  form in `rocrate-paper-2021`. Sub-crate discovery is not exercised here —
  none of these crates nest.
- **`@context` shape tolerance**: string, list, and dict contexts all load.
- **Root-field extraction** (description, licence, `datePublished`,
  `conformsTo`) works on all 5 RO-Crates that populate those fields;
  `rocrate-paper-2021` is the only example in the corpus whose keywords were
  read, and it is also the only one that puts them on the root as a string.

## Ranked fix list

1. Accept a document with no `@graph`: top-level object becomes the root,
   nested typed objects get hoisted. Recovers 15 of 23 examples from literally
   nothing to 8–12 points. (break #1)
2. Extend `_TYPE_TOKENS` with `File`, `SoftwareSourceCode`,
   `SoftwareApplication`, `ComputationalWorkflow`, `CreateAction`,
   `ContainerImage`, and the `cr:` tokens. (break #2)
3. Add `object` / `result` / `instrument` / `agent` to the provenance field
   lists. (break #3)
4. Add `encodingFormat` beside `format`, `contentSize`, `spdx:checksum`, and
   treat a relative `@id` as a location when `contentUrl` is absent. (break #4)
5. Drop the hard-coded filename: accept a file path, or glob `*.json` /
   `*.jsonld` in the directory. (break #0)
6. Point criterion 2.a at the raw-text vocab scan that 0.c already uses, and
   widen `ONTOLOGY_HOSTS` (orcid, ror, spdx, w3id, spar, qudt). (break #5)
7. Suppress the mechanical estimate when the crate loaded zero entities,
   rather than emitting a confident 2/46.

Items 1–4 are the ones this corpus actually measures. 5–7 are judgement.

## Not yet covered by this corpus

- No nested/sub-crate examples from outside FAIRSCAPE — sub-crate discovery
  (`_discover_subcrates`) is untested against anyone else's layout.
- No RO-Crate that ships `ro-crate-preview.html` or a datasheet, so the
  artifact-discovery globs are untested here.
- Nothing with `d4d:` fields, and nothing using LinkML.
- The medical slice is thin: `physionet-mimic3-demo` and the two Bioschemas
  docs. No FHIR (FHIR's RDF serialisation is Turtle, not JSON-LD), no CDISC,
  no dbGaP.
- Network checks were disabled (`--no-network`) for every run.
