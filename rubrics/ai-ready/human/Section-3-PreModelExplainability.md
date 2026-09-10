# AI-Readiness Human Questionnaire — Section 3: Pre-model Explainability

> **⚠ Written against rubric v1.0.** The rubric is now v1.8 (2026-09-10) — apply the changes in [V1.5-DELTA.md](V1.5-DELTA.md) (gates, N/A policy, dependency caps, and per-criterion rule changes) on top of this packet.
*Is there a Datasheet-style account of the data, and can its integrity be verified?*

For this section:
- **Q3.1** — you are given the dataset's **rendered HTML datasheet** to read
  directly, plus the raw labeled fields behind it as a cross-check. You do
  **not** need to judge whether a datasheet exists or is linked — that's a
  given (it's what you've been handed). Your job is to judge the *content*.
- **Q3.2** — you are given a small labeled packet of hash-coverage figures.

Metadata is served **sorted and labeled with raw values**, e.g.
`Use cases: "<raw text from the document>"`; missing fields show `— (absent)`.

**Scoring:** `0` = Absent · `1` = Partial · `2` = Substantive.
Mark **N/A** (and exclude from the denominator — do not score 0) if a question
genuinely can't apply to this dataset; the packet flags likely N/A cases.
Merged questions `[x + y]`: **0** = neither half, **1** = one half met or both
weak, **2** = both substantive. For any score below 2, note in one phrase what
was missing.

---

### Q3.1 — Intended use & limitations (from the datasheet) `[3.b; 3.a existence given]`
**Reading the provided datasheet, does it state concrete intended/appropriate use cases *and* concrete data limitations (inappropriate or out-of-scope uses), with links to prior analyses?**

*You are given* the rendered datasheet, plus these raw fields as a cross-check
if the datasheet doesn't foreground them:
- **Use cases** — raw text of the declared intended-use narrative. Concrete,
  specific applications the data was prepared for (not "for biomedical
  research").
- **Limitations** — raw text of the declared data-limitations narrative. What
  the data will *not* support: populations not represented, where inferences
  would over-reach.
- **Prohibited uses** — raw text of explicitly out-of-scope uses, if declared.
- **Prior work** — links to the originating publication or analyses that have
  already used this dataset.

*Don't score whether the datasheet exists; score what it says.*

- **0** — Neither intended use cases nor limitations are stated in the datasheet.
- **1** — Use cases **or** limitations present but not both; or both are generic rather than concrete; or no linked prior work.
- **2** — Concrete intended use cases **and** concrete limitations/inappropriate uses, with at least one linked prior analysis or originating publication.

### Q3.2 — Verifiable `[3.c]`
**Can a consumer verify data integrity via cryptographic hashes on the datasets and software?**

*You are given:*
- **Hash coverage** — how many of the Dataset + Software entities carry a
  cryptographic hash (`sha256` / `md5` / `contentChecksum`), as a count and
  ratio. Per-file hashes are stronger than one archive-level hash.
- **Access-mode note** — embargoed / controlled-access entities are flagged;
  they may legitimately lack a published hash — don't penalize those.

- **0** — No checksums on any dataset or software entity.
- **1** — Some entities hashed but coverage is incomplete (e.g. data hashed, software not; only a single archive-level hash).
- **2** — Substantively all dataset + software entities carry a cryptographic hash (per-entity integrity).

---

**Section 3 score:** Q3.1 __ + Q3.2 __ = **__ / 4**  (÷ 2 × questions answered)
