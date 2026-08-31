# AI-Readiness Human Questionnaire — Section 0: FAIRness

> **⚠ Written against rubric v1.0.** The rubric is now v1.5 (2026-08-29) — apply the changes in [V1.5-DELTA.md](V1.5-DELTA.md) (gates, N/A policy, dependency caps, and per-criterion rule changes) on top of this packet.
*Can a machine find, access, and legally reuse this dataset?*

For each question you are **given the relevant metadata, already extracted,
sorted, and labeled** — raw values straight from the dataset's metadata, e.g.
`License: "https://creativecommons.org/licenses/by/4.0/"`. A missing field is
shown as `— (absent)`. You never need to open the raw RO-Crate: judge what is
in front of you.

**Scoring:** `0` = Absent · `1` = Partial · `2` = Substantive.
Mark **N/A** (and exclude from the denominator — do not score 0) if a question
genuinely can't apply to this dataset; the packet flags likely N/A cases.
Merged questions `[x + y]`: **0** = neither half, **1** = one half met or both
weak, **2** = both substantive. For any score below 2, note in one phrase what
was missing.

---

### Q0.1 — Findable & accessible `[0.a + 0.b]`
**Does the dataset have a persistent identifier and live in a recognized, harvestable repository, with metadata in a standard vocabulary?**

*You are given:*
- **Identifier** — the root identifier string, flagged if it matches a PID
  scheme (DOI, ARK, Handle/HDL, PURL, w3id, URN, RRID, SWHID).
- **Publisher / host** — the raw publisher value, plus any recognized FAIR
  repositories detected (Dataverse, Zenodo, PhysioNet, FAIRhub, BioStudies,
  dbGaP, GEO…) vs. a lab web page.
- **Vocabularies** — the metadata namespaces declared (schema.org / DCAT / EVI).
- **Access** — the confidentiality level and conditions of access, so you can
  judge whether the *metadata* stays publicly readable even when the *data*
  itself is access-controlled.

- **0** — No persistent ID *and* no recognizable repository; not discoverable by a standard search.
- **1** — Either a persistent ID *or* a recognized repository, but not both; or metadata is standard but for controlled data it's unclear whether the metadata stays open.
- **2** — Persistent ID resolves *and* deposit is in a recognized FAIR repository, with standard-vocabulary metadata that remains publicly readable.

### Q0.2 — Interoperable & reusable `[0.c + 0.d]`
**Are the data in formally specified formats with declared schemas, and is reuse legally defined by a clear license or DUA?**

*You are given:*
- **Format mix** — each dataset's declared format, with counts of formats that
  have a published spec (CSV, Parquet, JSON, HDF5, NIfTI, BAM, FASTQ…) vs.
  ad-hoc/proprietary.
- **Schema coverage** — of the tabular datasets, how many link a schema / data
  dictionary (with the tabular vs. non-tabular counts).
- **License** — the raw `license` value (URL / SPDX code / free text), flagged
  if it is resolvable and if it is CC0. *The paper flags **CC0 as inappropriate
  for biomedical data** — treat CC0 with no rationale as a Partial.*
- **Conditions of access** — raw text; a Data Use Agreement narrative that
  concretely defines reuse terms can substitute for a license.
- **Prohibited uses** — raw text, if declared.

- **0** — Ad-hoc/proprietary formats with no spec *and* no license or DUA — reuse is undefined.
- **1** — Formats are specified but most tabular datasets lack schemas, **or** a license/DUA exists but is free-text only / CC0 without rationale / too vague to guide a reuser.
- **2** — Published formats with schemas on the tabular datasets *and* a resolvable license or a concrete DUA.

---

**Section 0 score:** Q0.1 __ + Q0.2 __ = **__ / 4**  (÷ 2 × questions answered)
