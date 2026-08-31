# AI-Readiness Human Questionnaire — Section 6: Computability

> **⚠ Written against rubric v1.0.** The rubric is now v1.5 (2026-08-29) — apply the changes in [V1.5-DELTA.md](V1.5-DELTA.md) (gates, N/A policy, dependency caps, and per-criterion rule changes) on top of this packet.
*Can a program validate, fetch, run, and understand this data without bespoke work?*

For each question you are **given the relevant metadata, already extracted,
sorted, and labeled** — raw values straight from the dataset's metadata, e.g.
`Conforms to: "https://w3id.org/ro/crate/1.2"`. A missing field is shown as
`— (absent)`. You never need to open the raw RO-Crate: judge what is in front
of you.

**Scoring:** `0` = Absent · `1` = Partial · `2` = Substantive.
Mark **N/A** (and exclude from the denominator — do not score 0) if a question
genuinely can't apply to this dataset; the packet flags likely N/A cases.
Merged questions `[x + y]`: **0** = neither half, **1** = one half met or both
weak, **2** = both substantive. For any score below 2, note in one phrase what
was missing.

---

### Q6.1 — Standardized `[6.a]`
**Does the crate declare the standards it conforms to, so conformance can be checked deterministically?**

*You are given:*
- **Declared standards** — the raw `conformsTo` values on the root/sub-crates
  (RO-Crate spec URL, Croissant…).
- **Vocabularies** — the metadata namespaces declared (schema.org, EVI,
  Croissant).
- **Recognized standards detected** — which of RO-Crate / Croissant /
  schema.org / EVI / Frictionless / JSON Schema were found.
- **Schemas citing validation standards** — how many Schema entities reference
  a validation standard (Frictionless, JSON Schema draft).
- **Validation report** — whether any conformance/validation claim is present.

- **0** — No conformsTo, no recognized vocabularies beyond boilerplate, no schema-standard references.
- **1** — RO-Crate conformsTo declared (the free baseline) but nothing further — no Croissant where it would apply, schemas cite no validation standard.
- **2** — Multiple standards declared (RO-Crate + Croissant and/or schema-validation standards), ideally with a validation claim — conformance is deterministically checkable.

### Q6.2 — Computationally accessible `[6.b]`
**Can a program fetch the data over a standard protocol or documented API, with the authentication procedure described where access is gated?**

*You are given:*
- **Distribution links** — how many datasets carry resolvable download links,
  and the protocol schemes seen (https / ftp / s3 / gs).
- **API** — any API endpoint detected (a path with `/api`, an
  OpenAPI/Swagger/GraphQL spec).
- **Access instructions** — raw text of the registration / credentials / DUA
  workflow for controlled data.

- **0** — No resolvable distribution links, no API, no access instructions.
- **1** — Links exist but single-mechanism and undocumented; **or** controlled-access data lacks request instructions; **or** non-standard schemes without explanation.
- **2** — Reachable via a standard protocol or documented API, with the auth/request procedure documented where access is gated.

### Q6.3 — Portable & contextualized `[6.c + 6.d]`
**Are the formats widely readable with compute environment documented where needed, and can a reader preview the data's structure (splits, withheld info, examples) before downloading?**

*You are given (portable):*
- **Format mix** — counts by format, split into widely-readable (CSV, Parquet,
  HDF5, NIfTI, BAM, FASTQ…) vs. proprietary; proprietary is fine if shipped
  with a spec/converter.
- **Environment** — container/env references found on software and
  computations (Dockerfile, image digest, conda `environment.yml`,
  `requirements.txt`).
- **Hardware requirements** — raw text (GPU, memory, OS, runtime), where
  needed.

*You are given (contextualized):*
- **Splits** — raw text describing train/val/test splits, plus a count of
  split-named datasets. **Their absence is *not* a defect** — only judge
  splits where they'd be meaningful.
- **Withheld information** — raw text documenting excluded / blinded /
  embargoed information.
- **Examples** — indicators of example records or sample files conveying
  structure.
- **Preprocessing** — raw text of the preprocessing protocol.

- **0** — Proprietary/unspecified formats with no environment docs *and* no structural context (no examples, no withheld-info notes).
- **1** — Formats mostly readable but compute environment undocumented where needed, **or** only thin context (examples in passing, splits implied by name without explanation).
- **2** — Widely-readable formats with environment/hardware documented where needed *and* a reader can preview structure (examples/withheld-info documented; splits described where they apply).

---

**Section 6 score:** Q6.1 __ + Q6.2 __ + Q6.3 __ = **__ / 6**  (÷ 2 × questions answered)
