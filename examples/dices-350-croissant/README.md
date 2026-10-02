# DICES-350 (Croissant with RAI fields)

Two versions of the same dataset's metadata, graded with `fairscape-evidence`:

| file | |
| --- | --- |
| `metadata.json` | the MLCommons reference Croissant for DICES-350, unmodified ([source](https://github.com/mlcommons/croissant/blob/main/datasets/1.0/dices-350/metadata.json), fetched 2026-10-02) |
| `metadata-improved.json` | the same file with what a research group would fill in by hand, built by `build_improved.py` |
| `review/`, `review-improved/` | `ai-ready-review.html`, `ai-ready-evidence.json`, `automated-score.json` for each |

```bash
fairscape-evidence metadata.json -o review/
python ../score_estimates.py review/ai-ready-evidence.json review/automated-score.json
```

`automated-score.json` rolls the per-criterion automated estimates up with the
grader's v1.8 aggregator (`rubric_eval._aggregate`). Only criteria that have an
estimate are counted: 18 of 28 for the original and the improved file.

## What was added in `metadata-improved.json`

Every value comes from the DICES README, the CSV itself, the paper's author list
or a registry lookup. The original's eight `rai:` fields and its license
(`cc-by-sa-4.0`) are unchanged.

- **identifier**: `https://doi.org/10.5072/zenodo.dices-350.v1`, a
  **placeholder** under DataCite's test prefix, which never resolves. It stands
  in for the DOI a GitHub→Zenodo release would mint. `publisher` is Zenodo, and
  `sameAs` points to the GitHub folder.
- **creator**: the paper's eight authors as `Person`s, five of them with ORCIDs.
  The ORCID API returned several matches for Taylor, Diaz and Wang, so they have
  names only. `copyrightHolder` is Google LLC (ROR `00njsd438`).
- **keywords**: seven free-text terms plus five MeSH descriptor IRIs: Artificial
  Intelligence, Natural Language Processing, Safety, Crowdsourcing, Cultural
  Diversity. They are text, not `DefinedTerm` objects, because mlcroissant 1.1
  rejects non-text keywords.
- **datePublished / dateModified**: the first commit of the CSV and its last fix.
- **distribution**: the empty-pattern `FileSet` is replaced by a `FileObject` for
  the CSV. Its `contentUrl` is pinned to commit `9c0eca5`, and it carries the
  real `sha256` and `contentSize`.
- **recordSet**: `ratings`, with all 41 columns as typed `Field`s and their
  descriptions from the README schema list (`dataType` only, no vocabulary
  bindings).
- **New `rai:` fields**: `dataUseCases`, `dataLimitations`,
  `personalSensitiveInformation`, `dataCollectionMissingData` (from profiling the
  CSV: no blanks), `dataCollectionTimeframe` (the `answer_timestamp` range,
  2022-12-08 to 2023-01-09), `dataPreprocessingProtocol`, `annotationsPerItem`.

It validates with mlcroissant 1.1, and all 43,050 records load with the checksum
verified.

## Scores

| | original | improved |
| --- | --- | --- |
| overall (network checks on) | **22.0%** (10/36) | **58.3%** (21/36) |
| overall (`--no-network`) | 22.0% | 63.7% |
| gating | FAIL | FAIL |

| criterion | orig | impr | why |
| --- | --- | --- | --- |
| 0.a Findable | 0 | 1 | DOI present but does not resolve (placeholder); a real DOI → 2 |
| 0.b Accessible | – | 0 | the placeholder DOI returns no metadata |
| 0.c Interoperable | 1 | 2 | MeSH terms referenced |
| 0.d Reusable | 2 | 2 | SPDX id `cc-by-sa-4.0` |
| 2.a Semantics | – | 2 | abstract, keywords, MeSH terms |
| 2.c Standards | 0 | 1 | 41 typed fields, no vocabulary binding |
| 3.b Fit for purpose | 0 | 2 | use cases + limitations + citeAs paper |
| 4.d Secure | 0 | 1 | sensitivity stated in prose |
| 5.a Persistent | 1 | 2 | DOI + Zenodo (the placeholder, taken at face value) |
| 6.d Contextualized | 0 | 1 | missing-data and preprocessing described, no example data |

Both versions still fail the gates on 0.a (needs a resolving DOI) and 1.c (DICES
ships no processing software). 4.a–4.c and 2.d/2.e get no automated estimate, so
the gates there stay unscored.

Not added, because there is nothing factual to put in them:
`rai:dataReleaseMaintenancePlan` (5.c), software (1.c), ethics/IRB fields (4.a),
summary statistics (2.b).

## Notes

- The repo README says CC BY 4.0, while the Croissant says `cc-by-sa-4.0`. The
  license was left as the Croissant has it.
- 19 raters failed the authors' quality checks. The README lists their IDs and
  the file keeps them; `rai:dataLimitations` now says so.
