# AI-Readiness Human Questionnaire — Section 2: Characterization

> **⚠ Written against rubric v1.0.** The rubric is now v1.5 (2026-08-29) — apply the changes in [V1.5-DELTA.md](V1.5-DELTA.md) (gates, N/A policy, dependency caps, and per-criterion rule changes) on top of this packet.
*Can a modeler understand what this data is, its shape, and its caveats before downloading it?*

For each question you are **given the relevant metadata, already extracted,
sorted, and labeled** — raw values straight from the dataset's metadata, e.g.
`Keywords: ["proteomics", "chemotherapy response", …]`. A missing field is
shown as `— (absent)`. You never need to open the raw RO-Crate: judge what is
in front of you.

**Scoring:** `0` = Absent · `1` = Partial · `2` = Substantive.
Mark **N/A** (and exclude from the denominator — do not score 0) if a question
genuinely can't apply to this dataset; the packet flags likely N/A cases.
Merged questions `[x + y]`: **0** = neither half, **1** = one half met or both
weak, **2** = both substantive. For any score below 2, note in one phrase what
was missing.

> **Tabular scope:** statistics and schema coverage are judged over **tabular**
> datasets only. Images, vendor binaries, BAM/FASTQ, and audio are out of scope —
> the packet gives you both the tabular and non-tabular counts.

---

### Q2.1 — Semantic description `[2.a]`
**Is the dataset described richly enough to be understood and discovered — a real abstract, topical keywords, and ontology-grounded subject terms?**

*You are given:*
- **Description** — the raw root description text (with its length). Is it a
  multi-sentence, domain-specific abstract, or one generic line?
- **Keywords** — the raw keywords array. Topical, or filler like
  "data, biomedical, research"?
- **Ontology terms** — a count and samples of subject terms that resolve to an
  ontology IRI (MeSH, EDAM, NCIt, OBO…) rather than free text.
- **Dataset samples** — up to 10 member datasets with their own descriptions,
  so you can see whether description lives only on the root.

- **0** — One-line/generic description, no keywords, no ontology terms.
- **1** — Description and keywords are topical, but subject terms are free-text only (no ontology grounding), or grounding exists only on the root.
- **2** — Detailed abstract + topical keywords + ontology-grounded subject terms, with major datasets carrying their own descriptive metadata.

### Q2.2 — Statistics & schema `[2.b + 2.c]`
**Can a modeler see the shape of the data (sizes, distributions, missing-value convention) and find a machine-readable data dictionary for each structured dataset?**

*You are given:*
- **Scope** — the tabular vs. non-tabular dataset counts (an all-imaging crate
  may make this question N/A).
- **Size & stats coverage** — how many tabular datasets carry
  `rowCount`/`columnCount`/`contentSize`/`sampleSize`, how many link summary
  statistics (per-column dtypes, null counts, min/max/mean/SD), and up to 5
  illustrative samples.
- **Missing-value convention** — raw text of the documented encoding
  convention, if any.
- **Schema coverage** — how many tabular datasets link a machine-readable
  schema / data dictionary, plus up to 5 schema samples showing whether they
  reference domain standards (LOINC, OMOP, GA4GH) where those apply.

- **0** — No statistics beyond raw file size *and* no schemas on the structured datasets.
- **1** — Some statistics or some schemas, but not most; **or** distributions/missing-value convention absent; **or** schema coverage uneven.
- **2** — Most tabular datasets are characterized (sizes + distributions + missing-value convention) *and* linked to a machine-readable schema.

### Q2.3 — Bias, assumptions & quality `[2.d + 2.e]`
**Are known biases and assumptions described, and is quality control documented with enough specificity to evaluate fit?**

*You are given* three narratives, shown **in full** (they are the whole basis
for this score):
- **Biases** — raw text of the declared biases/assumptions narrative. Look for
  named biases with specifics (selection, measurement, demographic, temporal
  skew), processing/interpretation assumptions, case/control composition.
- **Missing data** — raw text on *reasons* for missingness (not just the
  encoding), mechanism if known (MCAR/MAR/MNAR), and QC-driven exclusions.
- **Collection & QC** — raw text of the collection narrative: QC procedures
  with concrete criteria or thresholds and named tools or a resolvable
  procedure document.

*This rewards transparency about biases, not their absence.*

- **0** — No bias/assumption discussion *and* no QC information.
- **1** — Some bias or QC content but generic/one-line ("selection bias possible", "standard QC applied") or covering only one facet.
- **2** — Major biases + assumptions described with specifics, missing-data reasons given, *and* QC procedures/criteria described concretely.

---

**Section 2 score:** Q2.1 __ + Q2.2 __ + Q2.3 __ = **__ / 6**  (÷ 2 × questions answered)
