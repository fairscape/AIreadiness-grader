# AI-Readiness Human Questionnaire — Section 4: Ethics

> **⚠ Written against rubric v1.0.** The rubric is now v1.5 (2026-08-29) — apply the changes in [V1.5-DELTA.md](V1.5-DELTA.md) (gates, N/A policy, dependency caps, and per-criterion rule changes) on top of this packet.
*Was the data acquired, managed, shared, and secured responsibly — and can a reviewer tell?*

For each question you are **given the relevant metadata, already extracted,
sorted, and labeled** — raw values straight from the dataset's metadata, e.g.
`Informed consent: "Broad consent for secondary research use, signed at
enrollment"`. A missing field is shown as `— (absent)`. You never need to open
the raw RO-Crate: judge what is in front of you.

**Scoring:** `0` = Absent · `1` = Partial · `2` = Substantive.
Mark **N/A** (and exclude from the denominator — do not score 0) if a question
genuinely can't apply to this dataset; the packet flags likely N/A cases.
Merged questions `[x + y]`: **0** = neither half, **1** = one half met or both
weak, **2** = both substantive. For any score below 2, note in one phrase what
was missing.

---

### Q4.1 — Ethically acquired & managed `[4.a + 4.b]`
**Is data acquisition described well enough to evaluate ethics (framework, IRB/consent), and are privacy-protection processing and oversight documented?**

*You are given (acquisition):*
- **Collection** — raw text of how the data was obtained.
- **Ethical review** — raw text: governing framework (Belmont, Menlo, CARE,
  HIPAA, GDPR), review body/process.
- **Human subjects** — the declared flag; drives whether the consent/IRB half
  applies. *For clearly non-human-subjects data that half is **N/A** — score on
  the management half.*
- **Informed consent** — raw text of the consent scope.
- **At-risk populations** — the declared list, or an explicit "none".
- **IRB / protocol references** — IRB numbers, protocol IDs, consent doc links.

*You are given (management):*
- **Management plan** — raw text of the lifecycle/management plan.
- **Governance committee** — the named oversight body or ethical-review
  process.
- **Privacy protection** — raw text of the processing applied
  (de-identification Safe Harbor/Expert Determination, k-anonymity,
  differential privacy, aggregation).
- **Confidentiality level** — the declared code; higher sensitivity demands
  stricter privacy processing.

- **0** — No acquisition description *and* no management/privacy/governance info.
- **1** — Acquisition described generally but missing framework/IRB/consent or management plan; **or** management named (e.g. a committee) but privacy processing unspecified.
- **2** — Acquisition is sufficient to evaluate ethical fit (framework + authorization + plan) *and* privacy-protection processing + oversight are described concretely.

### Q4.2 — Disseminated & secure `[4.c + 4.d]`
**Are the terms of use and the security/access classification explicit and machine-readable — license/DUA, prohibited uses, sensitivity, confidentiality level, and an access contact?**

*You are given:*
- **License** — the raw `license` value, flagged if resolvable and if CC0
  (**CC0 flagged** for biomedical data).
- **Conditions of access** — raw DUA narrative, if any.
- **Prohibited uses** — raw text, if declared.
- **Sensitive information** — the declared kinds of personal/sensitive content
  present.
- **Confidentiality level** — the declared HL7 code (normal / restricted /
  very restricted).
- **De-identified** — the declared flag.
- **Contact** — the access / data-access-committee contact email.

*Cross-check what you're shown:* "restricted" data with no DUA, or "normal" on
sensitive un-deidentified data, is a gap.

- **0** — No license/DUA, no access classification, no contact.
- **1** — License **or** classification present but key items missing (no prohibited-uses/sensitivity where warranted, no contact, free-text-only license, CC0 without rationale, or classification-vs-sensitivity mismatch).
- **2** — Resolvable license or DUA *and* a recognized categorical confidentiality classification, with prohibited uses / sensitivity stated where applicable and a clear access contact.

---

**Section 4 score:** Q4.1 __ + Q4.2 __ = **__ / 4**  (÷ 2 × questions answered)
