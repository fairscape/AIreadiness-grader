# AI-Readiness — Human Grader Metadata Spec

The packet a reviewer receives, so they never touch the raw RO-Crate. For each
questionnaire item it lists **exactly which fields to extract and display**, and
where they come from. Field names are the crate/EVI properties (and the LLM
grader's `extractor_inputs` keys) so the same extractor can feed both the human
packet and the LLM.

**Conventions**
- *Root* = the root Dataset entity of the crate. *Entities* = the `@graph` items.
- "TABULAR-scoped" = compute over datasets whose format is tabular
  (CSV/TSV/Parquet/H5AD/JSONL/XLSX/Arrow/…); exclude images, vendor binaries,
  BAM/FASTQ, audio. Show the reviewer both the tabular count and the
  non-tabular count so they apply the scope correctly.
- **Render each field as**: the value if present, or an explicit `— (absent)`
  so "missing" is visible rather than silently blank.
- Fields marked **⚠ N/A-flag** should carry a note when the dataset type makes
  them inapplicable (e.g. consent for non-human-subjects data, tabular stats for
  an all-imaging crate), so the reviewer marks N/A rather than 0.

---

## Packet — Section 0 · FAIRness

### Q0.1 Findable & accessible
| Field to serve | Source | Notes |
|---|---|---|
| `root_identifier` | root `identifier`/`@id` | the PID string; flag whether it looks like DOI/ARK/Handle/PURL/w3id/URN/RRID/SWHID |
| `publisher_info` | root `publisher` | object or string |
| `archive_indicators` | publisher / distribution / description | list of recognized repo names/hosts found (dataverse, zenodo, physionet, fairhub, biostudies, dbgap, geo…) |
| `context_namespaces` | `@context` | the vocab namespaces declared |
| `recognized_vocabularies` | derived from `@context` | schema.org / DCAT / EVI / PROV-O / Croissant detected, from `@context` or term prefixes (`prov:`, `EVI:`) even when undeclared |
| `confidentiality_level` | root `confidentialityLevel` | needed to judge metadata-open-vs-data-restricted |
| `conditions_of_access` | root `conditionsOfAccess` | |

### Q0.2 Interoperable & reusable
| Field to serve | Source | Notes |
|---|---|---|
| `tabular_dataset_count` / `non_tabular_dataset_count` | derived | scope denominator + excluded count |
| `datasets_with_schema_count` | derived | of tabular datasets, how many link a Schema (`evi:schema`/`conformsTo`/`schema`) |
| `formats_with_published_spec_count` | dataset `format`/`encodingFormat` | count in CSV/Parquet/JSON/HDF5/NIfTI/BAM/FASTQ/Zarr/std image/audio |
| `format_distribution` | dataset formats | counts by format, so the reviewer sees the mix |
| `license_value` | root `license` | URL / SPDX / text |
| `license_is_resolvable` | derived | URL or recognized SPDX vs free-text |
| `license_is_cc0` | derived | **⚠ flag** — CC0 discouraged for biomedical |
| `conditions_of_access` | root `conditionsOfAccess` | DUA narrative may substitute for a license |
| `prohibited_uses` | root `prohibitedUses` | |

---

## Packet — Section 1 · Provenance

**Section 1 is NOT served as a field table.** Provenance is inherently a graph,
so the reviewer gets **two deliverables** instead:

1. **Author / PI / contributors list** — a short table of the people and
   organizations credited on the dataset, with identifiers, for Q1.1's "actors"
   half.
2. **Interactive evidence graph** — the provenance visualization
   (`provenance-graph.html`, as produced by the nf-fairscape / FAIRSCAPE
   EvidenceGraph exporter; example:
   `NewMoniWork/nf/nf-fairscape/examples/letters-chain/results/provenance-graph.html`).
   The reviewer walks the graph and clicks each node's **ℹ** info button to read
   that entity's details.

> **⚠ Prerequisite — exported-HTML change required.** The **online** graph viewer
> shows a per-node **ℹ** info affordance; the **standalone exported
> `provenance-graph.html` does not yet**. The exported viewer must gain the same
> per-node info popover before this section can be graded from the HTML alone.
> The data it needs is already embedded — each node carries `_sourceData` (the
> full entity dict) plus `description`, `type`, and relations from
> `window.__EVIDENCE_GRAPH_DATA__["@graph"]`; the popover just needs to render
> them. Until then, fall back to the `computation_samples` / `software_samples`
> field tables below.

### Deliverable 1 — Author / PI / contributors list (for Q1.1)
| Field to serve | Source | Notes |
|---|---|---|
| `root_actors` | root `author`/`creator`/`contributor`/`publisher`/`principalInvestigator`/`contactPoint` | verbatim rows: name + role + identifier |
| `author_count` / `authors_with_orcid_count` | derived | ORCID coverage (judge by effort, not 100%) |
| `publisher_present` / `publisher_has_ror` | derived | **⚠ N/A-flag** — no ROR expected when publisher is a data archive |
| `principal_investigator_present` | derived | show the PI prominently — it anchors "who's responsible" |

### Deliverable 2 — Evidence graph + per-node ℹ popover (for Q1.1 sources & all of Q1.2)
The graph nodes and edges come straight from the EvidenceGraph
(`generatedBy` / `usedDataset` / `usedSoftware` / `usedSample` / `usedInstrument`).
Node fill by type: **green** = Dataset/Sample, **red** = Computation/Experiment,
**yellow** = Software/Instrument. Each node's **ℹ** popover must expose:

| Popover field | Source (per node `_sourceData`) | Supports |
|---|---|---|
| `name` | entity `name` | node identity |
| `@id` | entity `@id` (ARK/DOI) | resolvability |
| `@type` | entity `@type` (Dataset / Computation / Software…) | reading the chain |
| `description` | entity `description` | Q1.1 source specificity; Q1.2 step meaning |
| source / accession | Dataset `sourceOrganization` / `provider` / accession in name or description | **Q1.1** — origin of raw-input Datasets |
| `url` / `codeRepository` / `version` | Software entity | **Q1.2** — is the software identifiable & versioned |
| inputs / outputs | `usedDataset` / `usedSample` + `generatedBy` / `generated` | **Q1.2** — does the step declare I/O |

Supporting rollups to display alongside the graph (so the reviewer can gauge
coverage without counting nodes by hand — same values the LLM grader uses):

| Field | Source | Notes |
|---|---|---|
| `computation_count` | derived | number of processing steps (red nodes) |
| `computation_with_software_link_count` | derived | steps linking `usedSoftware` (red → yellow edges) |
| `computation_with_io_count` | derived | steps declaring both inputs and outputs |
| `software_count` / `software_with_link_count` / `software_with_version_count` | derived | identifiability + versioning coverage |
| `software_in_sustainable_archive_count` | derived | informational (Zenodo/Software Heritage) — a plus, not required |
| `computation_samples` / `software_samples` | up to 8 / 10 entities | text fallback if the ℹ popover is unavailable in the exported HTML |

---

## Packet — Section 2 · Characterization

### Q2.1 Semantic description
| Field to serve | Source | Notes |
|---|---|---|
| `root_description` + `root_description_length` | root | is it a real abstract? |
| `root_keywords` | root `keywords` | topical vs generic |
| `ontology_term_count` + `ontology_term_samples` | `about`/`subjectOf`/`keyword` across root + datasets | IRIs resolving to MeSH/EDAM/NCIt/OBO |
| `dataset_samples` | up to 10 Datasets | per-dataset `description` coverage |

### Q2.2 Statistics & schema
| Field to serve | Source | Notes |
|---|---|---|
| `tabular_dataset_count` / `non_tabular_dataset_count` | derived | **⚠ N/A-flag** scope; all-imaging crate → stats may be N/A |
| `datasets_with_size_count` | derived | tabular datasets carrying `rowCount`/`columnCount`/`contentSize`/`sampleSize` |
| `datasets_with_summary_stats_count` | derived | tabular datasets with `hasSummaryStatistics` |
| `summary_stats_samples` | up to 5 | illustrative — mix of lifted-fields and linked SummaryStats children |
| `missing_value_convention_text` | root description / additionalProperty / `rai:dataCollectionMissingData` | the encoding convention |
| `datasets_with_schema_count` / `dataset_count` (tabular) | derived | schema-link coverage numerator/denominator |
| `schemas_referencing_standards_count` | Schema entities | conformsTo/description mentioning LOINC/OMOP/GA4GH/Frictionless/JSON Schema |
| `schema_samples` | up to 5 Schemas | conformsTo, description, properties summary |

### Q2.3 Bias, assumptions & quality
| Field to serve | Source | Notes |
|---|---|---|
| `rai_dataBiases` | root `rai:dataBiases` | known biases + assumptions |
| `rai_dataCollectionMissingData` | root | reasons for missingness (2.d) *and* QC-driven exclusions (2.e) |
| `rai_dataCollection` | root `rai:dataCollection` | QC steps described as part of collection |

*(These three narrative fields are the whole basis for the score — show them in full, not truncated.)*

---

## Packet — Section 3 · Pre-model Explainability

### Q3.1 Intended use & limitations (served as the rendered datasheet)
**Primary deliverable is the rendered HTML datasheet itself, not a field table.**
Hand the grader the human-readable datasheet (the `datasheet_entity` /
`associatedDocumentation` HTML) and let them read the intended-use and
limitations sections directly. The grader does **not** judge whether the
datasheet exists — that's satisfied by serving it. Existence/linkage is
confirmed upstream (deterministic check / LLM grader), not by the human.

| Item to serve | Source | Notes |
|---|---|---|
| **Rendered HTML datasheet** | `datasheet_entity` (hasPart / associatedDocumentation, format html) | **the deliverable** — the grader reads this |
| `rai_dataUseCases` | root | fallback / cross-check if the datasheet doesn't foreground use cases |
| `rai_dataLimitations` | root | fallback / cross-check for limitations & out-of-scope uses |
| `prohibited_uses` | root `prohibitedUses` / additionalProperty | explicit out-of-bounds uses |
| `associated_publications` | `associatedPublication`/`citation`/`hasPart` | prior analyses / originating publication — surface as links |

*Not shown to the human anymore (used only by the upstream existence check):*
`has_human_readable_datasheet`, `populated_section_count`,
`healthsheet_fields_present`.

### Q3.2 Verifiable
| Field to serve | Source | Notes |
|---|---|---|
| `total_hashable_entities` | derived | Dataset + Software count |
| `entities_with_hash` | derived | those with `md5`/`sha256`/`contentChecksum` |
| `hash_coverage` | derived | ratio (null if 0 hashable) |
| access-mode note | derived | **⚠ N/A-flag** — embargoed/controlled entities may lack a published hash |

---

## Packet — Section 4 · Ethics

### Q4.1 Ethically acquired & managed
| Field to serve | Source | Notes |
|---|---|---|
| `rai_dataCollection` | root | how data was obtained |
| `ethical_review_text` | root `ethicalReview` | IRB body / review process / framework |
| `human_subject_research_value` | root `humanSubjectResearch` / additionalProperty | **⚠ N/A-flag** — drives whether consent half applies |
| `informed_consent` | root `informedConsent` | consent scope (required for human subjects) |
| `at_risk_populations` | root `atRiskPopulations` | list, or explicit "none" |
| `irb_or_consent_references` | narrative / additionalProperty | IRB #, protocol IDs, consent doc links |
| `management_plan_text` | `rai:dataReleaseMaintenancePlan` / labeled plan | lifecycle/management plan |
| `governance_committee` | `dataGovernanceCommittee` / additionalProperty | ethical oversight body |
| `privacy_protection_text` | narrative / additionalProperty | de-id method / k-anonymity / differential privacy / aggregation / HL7 tags |
| `confidentiality_level` | root `confidentialityLevel` | drives required strictness of privacy processing |

### Q4.2 Disseminated & secure
| Field to serve | Source | Notes |
|---|---|---|
| `license_value` / `license_is_resolvable` / `license_is_cc0` | root `license` | **⚠ flag** CC0 for biomedical |
| `conditions_of_access` | root `conditionsOfAccess` | DUA narrative |
| `prohibited_uses` | root `prohibitedUses` | |
| `rai_personalSensitiveInformation` | root | sensitive-content kinds present |
| `confidentiality_level` | root `confidentialityLevel` | HL7 code — normal / restricted / very restricted |
| `deidentified` | root `deidentified` | cross-check against sensitivity |
| `contact_email` | root `contactEmail` | access / data-access-committee contact |

---

## Packet — Section 5 · Sustainability

### Q5.1 Persistent, domain-appropriate home
| Field to serve | Source | Notes |
|---|---|---|
| `root_identifier` + `identifier_is_pid` | root `identifier` | does it resolve as a PID (doi.org / hdl.handle.net / n2t.net/ark)? |
| `publisher_info` | root `publisher` | |
| `archive_indicators` | publisher / distribution / description | recognized archive names/hosts |
| `distribution_links` | root + major Datasets `contentUrl`/`url`/`distribution` | include the **host** of each URL so a repo can be recognized without a fixed allow-list |
| `data_domain_hint` | root `keywords` + `rai:dataCollectionType` | to sanity-check specialist fit when one is clearly expected |

### Q5.2 Well-governed
| Field to serve | Source | Notes |
|---|---|---|
| `governance_committee` | `dataGovernanceCommittee` / additionalProperty | committee / steward |
| `maintenance_plan_text` | `rai:dataReleaseMaintenancePlan` / labeled plan | what/when/who |
| `principal_investigator` | root `principalInvestigator` | for PI-led projects |

### Q5.3 Associated
| Field to serve | Source | Notes |
|---|---|---|
| `total_entities` | derived | graph size |
| `root_haspart_count` | root `hasPart` | breadth of top-level linkage |
| `entities_with_provenance_link_count` + `provenance_link_density` | derived | fraction with `wasGeneratedBy`/`wasDerivedFrom`/`isPartOf`/`usedSoftware`/`usedSample`/`usedInstrument` |
| `subcrate_count` | derived | sub-crate references (release-of-crates) |

---

## Packet — Section 6 · Computability

### Q6.1 Standardized
| Field to serve | Source | Notes |
|---|---|---|
| `root_conformsTo` | root `conformsTo` | standard URLs / @id refs |
| `context_namespaces` | `@context` | |
| `recognized_standards` | derived | RO-Crate / Croissant / schema.org / EVI / PROV-O / Frictionless / JSON Schema detected |
| `schemas_referencing_standards_count` | Schema entities | |
| `validation_report_present` | derived | any conformance/validation claim |

### Q6.2 Computationally accessible
| Field to serve | Source | Notes |
|---|---|---|
| `distribution_link_count` | root + Datasets | |
| `distinct_protocols` | derived | https / ftp / s3 / gs schemes seen |
| `api_link` | any `/api` or OpenAPI/Swagger/GraphQL URL | |
| `access_instruction_text` | narrative / additionalProperty | registration / credentials / DUA workflow |

### Q6.3 Portable & contextualized
| Field to serve | Source | Notes |
|---|---|---|
| `format_distribution` | Datasets `format` | counts by format |
| `common_format_count` / `proprietary_format_count` | derived | readable vs proprietary split |
| `container_references` | Software/Computation | Dockerfile / image digest / Singularity / conda `environment.yml` / `requirements.txt` |
| `hardware_requirement_text` | narrative / additionalProperty | GPU / memory / OS / runtime |
| `split_text` + `split_dataset_count` | narrative + Datasets named train/val/test | **⚠ N/A-flag** — absence of splits is not a defect |
| `withheld_information_text` | narrative | excluded / blinded / embargoed info |
| `example_record_indicators` | `@id` refs of example/sample entities | names containing example/sample, small hasPart samples |
| `preprocessing_text` | `rai:dataPreprocessingProtocol` | |

---

## Field inventory — everything the extractor must be able to produce

Root-level: `identifier`/`@id`, `publisher`, `license`, `conditionsOfAccess`,
`prohibitedUses`, `confidentialityLevel`, `deidentified`, `contactEmail`,
`description`, `keywords`, `about`/`subjectOf`, `author`/`creator`/`contributor`,
`principalInvestigator`, `contactPoint`, `conformsTo`, `hasPart`,
`humanSubjectResearch`, `informedConsent`, `atRiskPopulations`, `ethicalReview`,
`dataGovernanceCommittee`, and the `rai:*` block (`dataCollection`,
`dataCollectionMissingData`, `dataBiases`, `dataUseCases`, `dataLimitations`,
`dataReleaseMaintenancePlan`, `personalSensitiveInformation`,
`dataPreprocessingProtocol`, `dataCollectionType`).

Per-entity: `@type`, `@id`, `name`, `description`, `format`/`encodingFormat`,
`contentUrl`/`url`/`distribution`, `rowCount`/`columnCount`/`contentSize`/`sampleSize`,
`hasSummaryStatistics`, `evi:schema`/`conformsTo`/`schema`, `md5`/`sha256`/`contentChecksum`,
`version`/`versionTag`/`codeRepository`, `usedSoftware`/`usedSample`/`usedInstrument`,
`wasGeneratedBy`/`wasDerivedFrom`/`isPartOf`, `associatedPublication`/`citation`.

Derived/computed: tabular vs non-tabular partition; all the `*_count`,
`*_coverage`, and `*_density` rollups; PID / SPDX / CC0 / resolvable-URL
detectors; recognized-vocab / recognized-standard / recognized-archive
detectors; URL host + protocol extraction.

> Everything here is already computed by the LLM grader's extractor
> (`extract.py` `extractor_inputs`). The human packet is a **re-rendering** of
> the same extraction, grouped by the 17 questions instead of the 28 rubrics —
> so one extractor run can produce both the machine grade and the human packet.

### Special case — Section 1 is served as a graph, not a table
Section 1 (Provenance) is delivered as an **author/PI list + the interactive
evidence-graph HTML** rather than a field table (see its packet section above).
Two build items follow from this:
1. **Author/PI list** — render `root_actors` + ORCID/ROR coverage as a small table.
2. **Evidence graph** — ship the EvidenceGraph export (`provenance-graph.html`).
   It needs a **per-node ℹ info popover** (present in the online viewer, **not yet
   in the standalone export**) surfacing each node's `name`, `@id`, `@type`,
   `description`, source/accession, software `url`/`version`, and inputs/outputs.
   The data is already embedded in `window.__EVIDENCE_GRAPH_DATA__["@graph"]`
   (each node carries `_sourceData`); only the popover UI is missing. Track this
   as a prerequisite for grading Section 1 from the HTML.
