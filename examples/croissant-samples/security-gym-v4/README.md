# security-gym-v4: how far standard vocabularies go

Three versions of the same Croissant, graded with `fairscape-evidence` (network
checks on):

| file | what it is | automated estimate | full 28 criteria* |
| --- | --- | --- | --- |
| `metadata.json` | the authors' file ([j-klawson/security-gym](https://github.com/j-klawson/security-gym) `data/croissant.json`), unmodified | 63.7% (21/34), gate FAIL on 1.c | – |
| `metadata-standard-max.json` | built by `build_standard_max.py`; adds only verified facts | 92.9% (34/38) | **85.7%** (48/56), gates pass |
| `metadata-fabricated-max.json` | built by `build_fabricated_max.py`; **SCORING DEMO with invented values** | 100% (38/38) | **100%** (56/56), gates pass |

\* The judgment criteria were graded by an isolated LLM agent that saw only the
rubric and the evidence JSON, and took the metadata at face value. Its scores
are in `review-*/judgment-scores.json`, and the combined result in
`review-*/full-score.json` (`../../full_score.py`). The judgment criteria are
2.d, 2.e, 4.a–4.c, 5.b, 5.c, 6.b and 6.c, plus 0.d for the fabricated file.

Both built files use only **schema.org, Croissant RAI and W3C PROV-O**
properties on top of the Croissant 1.1 format. MeSH, Wikidata, DDI-CDI, HL7 and
ODRL appear only as values or term types. There are no FAIRSCAPE/EVI terms.
Both validate with mlcroissant 1.1.

## Does Croissant allow PROV?

Yes. The Croissant 1.1 spec ("Provenance Representation") recommends PROV-O.
`prov:wasDerivedFrom`, `prov:wasGeneratedBy` and `prov:wasAttributedTo` can sit
on the Dataset, a FileObject/FileSet, a RecordSet or a Field. Activities are
`prov:Activity`, with `prov:used` and `prov:wasAssociatedWith`. The spec also
standardizes two things the grader needed:

- **Statistics**: `annotation` entries with a `value` and a DDI-CDI
  SummaryStatisticType, Wikidata cardinality, or `sc:minValue`/`sc:maxValue`.
- **Usage conditions**: `usageInfo` holding DefinedTerms or an ODRL Offer.

The RAI vocabulary is all `sc:Text`, so it only ever supplies prose.

The authors already used PROV: five `prov:Activity` steps with software agents.
Two practical limits turned up:

- **Sources typed `sc:Dataset` break loading.** The authors typed their
  `prov:wasDerivedFrom` sources as `sc:Dataset`. mlcroissant then takes the
  first of those as the root and finds no record sets, which is true of the
  original file. Typing them `prov:Entity` fixes it.
- **Only one link direction.** mlcroissant fails on a link stated in both
  directions (`activity prov:generated file` plus `file prov:wasGeneratedBy
  activity`). State outputs from the file side only.

## standard-max: facts only

| criterion | standard term | value / source |
| --- | --- | --- |
| 0.b, 0.c, 2.a | `keywords` (MeSH IRIs) | Computer Security D016494, Machine Learning D000069550 |
| 0.a, 0.b, 5.a | `identifier`, `publisher` | the real v4.1 DOI 10.5281/zenodo.21763493; Zenodo |
| 1.a, 1.b, 5.d | `prov:wasGeneratedBy` / `wasDerivedFrom` / `used` on FileObjects and activities | stream ← composition ← benign_v4 + campaigns_v2, confirmed for the 30-day stream by its `composition_meta` table (seed 99) |
| 1.c | `codeRepository`, `downloadUrl`, `sha256` on software agents | composer: PyPI 0.4.2 wheel; the other modules: GitHub tag v0.4.2 |
| 1.d | creator `@id` | Keith Lawson's ORCID (from the Zenodo record); ROR for UM-Dearborn |
| 2.b | RecordSet / Field `annotation` | 21,511,208 rows; 609,520 malicious; is_malicious mean 0.0283; severity 1–3, mean 2.28 |
| 2.b, 2.d | `rai:dataCollectionMissingData` | NULL counts per column, measured on the 30-day stream |
| 2.c, 6.a | Field `dataType` | `src_ip` → wd:Q11135 (IP address); `is_malicious` → cr:Label |
| 3.a | `subjectOf` | DATASET_README.md on Zenodo; the HF dataset card |
| 4.d | `usageInfo` DefinedTerm | HL7 v3-Confidentiality `M`. **Illustrative**: only the authors can assign it. |
| 6.d | RecordSet `examples` | 4 real rows of the 30-day stream (none with third-party IPs) |

It loses points on:

- **1.a = 1:** no sample or instrument entities.
- **1.b:** capped at 1.a, per the rubric.
- **1.c = 1:** only `composer.py` is in the PyPI wheel. The orchestrator,
  labeler, scrubber and validator exist only on GitHub, and the only Zenodo
  software snapshot is v0.3.3.
- **1.d = 1:** Hafiz Malik has no identifiable ORCID.
- **4.a / 4.b / 4.c / 5.c = 1:** no ethics determination, privacy assessment,
  prohibited uses, contact or stewardship plan.

## fabricated-max: what got it to 100

Every item below is invented:

| criterion | fabricated value (standard property) |
| --- | --- |
| 1.a | instruments (eBPF agent, 4 servers) and samples (per-server log captures) as `prov:Entity` + `additionalType`, `prov:used` by the collection activity |
| 1.c | software DOI under DataCite's test prefix 10.5072 on every module agent |
| 1.d | ORCID's fictitious test iD (0000-0002-1825-0097) for the second author |
| 2.d / 2.e | class-imbalance and labeling-bias text in `rai:dataBiases`; a 2,000-event analyst audit and the validation-script link in `rai:dataAnnotationAnalysis` |
| 4.a | IRB exemption (protocol HUM-DEMO-0001) covering AI/ML release, in `rai:dataCollection` |
| 4.b | privacy impact assessment + annual reassessment, in `rai:personalSensitiveInformation` |
| 4.c, 0.d | CC BY 4.0; an ODRL Offer in `usageInfo` with permitted AI/ML use and three prohibitions; `contactPoint` access committee at example.org |
| 5.c | steward + successor, 20-year retention, deprecation and policy-change process, in `rai:dataReleaseMaintenancePlan` |
| 6.c | container image `ghcr.io/j-klawson/security-gym:0.4.2` in `softwareRequirements` |
| 6.d | "no split; evaluated online; seeds recorded" in `rai:dataPreprocessingProtocol` |

The judging agent flagged the example.org contact, the `HUM-DEMO` protocol and
the 10.5072 DOI as likely placeholders. A grader that checks resolvability
would drop 4.c, 5.c and possibly 4.a.

## Finding about the data

The authors' `rai:personalSensitiveInformation` says published source IPs are
only the synthetic target or lab-aliased subnets. In the 30-day stream,
**860,529 benign rows carry one of 11,413 distinct public IPv4 addresses**:
crawlers, scanners and other visitors, in both `src_ip` and `raw_line`. Both
built files state that instead.
