# AI-Readiness Human Questionnaire — Section 1: Provenance

> **⚠ Written against rubric v1.0.** The rubric is now v1.8 (2026-09-10) — apply the changes in [V1.5-DELTA.md](V1.5-DELTA.md) (gates, N/A policy, dependency caps, and per-criterion rule changes) on top of this packet.
*Can a reader trace this data back to its origin and reconstruct how it was made?*

For this section you are given **two things** (not a field packet):

1. **An author / PI / contributors list** — the people and organizations
   credited on the dataset, with any ORCID (people) or ROR (organizations)
   identifiers.
2. **An interactive evidence graph** — a provenance diagram of how the dataset
   was derived (like `provenance-graph.html`). Node colors: **green** =
   Dataset/Sample, **red** = Computation (a processing step),
   **yellow** = Software; arrows show `generatedBy` / `usedDataset` /
   `usedSoftware`. **Click the ℹ button on any node** to read that entity's
   details — name, identifier (ARK/DOI), description, source/accession, software
   URL + version, and its inputs/outputs. **Read the graph by walking from the
   final outputs back to the raw inputs.**

> If the evidence graph you're given has no ℹ button on its nodes, you have an
> older export — ask for the updated one (or use the text fallback in the
> metadata packet). The two questions below depend on reading node details.

**Scoring:** `0` = Absent · `1` = Partial · `2` = Substantive.
Mark **N/A** (and exclude from the denominator — do not score 0) if a question
genuinely can't apply to this dataset.
Merged questions `[x + y]`: **0** = neither half, **1** = one half met or both
weak, **2** = both substantive. For any score below 2, note in one phrase what
was missing.

---

### Q1.1 — Sources & responsible actors `[1.a + 1.d]`
**Do the major datasets name a specific real-world origin, and are the responsible people/organizations identified (ideally with ORCID/ROR)?**

*How to check:*
- **Actors** — use the author/PI list. Are collection, processing, and
  governance covered (not just one author)? Do a meaningful fraction of people
  carry ORCID URIs and organizations carry ROR URIs? **Partial ID coverage is
  fine** — not everyone has an ORCID, and a repository publisher won't have a
  ROR.
- **Sources** — in the evidence graph, find the **raw-input Dataset nodes**
  (green nodes at the far upstream end, with no incoming `generatedBy` edge) and
  open each one's **ℹ**. Look for a specific origin — named institution, hospital,
  lab, cohort, registry, or a public accession (RRID, GEO/dbGaP/SRA, source DOI)
  — specific enough to resolve (*"T2D cohort recruited at UVA Health 2020–2022"*,
  not *"EHR data"*).

- **0** — Sources unidentifiable, *and/or* only bare name strings with no identifiers and no role coverage.
- **1** — Sources named only generically (*"public proteomics dataset"*), **or** actors named but with near-zero ORCID/ROR effort.
- **2** — Major datasets resolve to a specific origin *and* key actors (collection, processing, governance) are identified with a meaningful fraction carrying ORCID/ROR.

### Q1.2 — Transformation steps & software `[1.b + 1.c]`
**Are the key data-processing steps documented as a chain, each linked to identifiable, obtainable software?**

*How to check — walk the evidence graph from outputs back to inputs:*
- **Chain & granularity** — are the **red Computation nodes** a meaningful chain
  (alignment, QC, normalization, feature extraction — not one black-box
  "processing" step)? Following the arrows, can you get from a final output back
  to the raw inputs with no gaps?
- **Inputs/outputs** — open each red node's **ℹ**: does it declare what it *used*
  (incoming edges) and what it *generated* (outgoing edges)?
- **Software** — does each red node connect to a **yellow Software node**? Open
  the yellow node's **ℹ**: does it resolve to an artifact (Zenodo DOI, SWHID,
  GitHub URL, container ref) **or** name a widely recognized tool **with a
  version**? *Proprietary tools are fine if named + versioned.*

- **0** — No transformation steps documented, or only bare stubs; **and/or** no identifiable software.
- **1** — Steps exist but the chain is coarse or inputs/outputs/software links are inconsistent; **or** software is referenced but under-identified (no version, broken link, ambiguous name).
- **2** — Key transformations are each captured at meaningful granularity with inputs/outputs, *and* substantively all referenced software is identifiable and versioned.

---

**Section 1 score:** Q1.1 __ + Q1.2 __ = **__ / 4**  (÷ 2 × questions answered)
