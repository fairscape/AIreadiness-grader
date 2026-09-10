# AI-Readiness Human Questionnaire — Section 5: Sustainability

> **⚠ Written against rubric v1.0.** The rubric is now v1.8 (2026-09-10) — apply the changes in [V1.5-DELTA.md](V1.5-DELTA.md) (gates, N/A policy, dependency caps, and per-criterion rule changes) on top of this packet.
*Will this data still be reachable, cared for, and connected years from now?*

For Q5.1 and Q5.2 you are **given the relevant metadata, already extracted,
sorted, and labeled** — raw values straight from the dataset's metadata;
missing fields show `— (absent)`. For **Q5.3 you also have the interactive
evidence graph** (the same `provenance-graph.html` you used in Section 1).
You never need to open the raw RO-Crate.

**Scoring:** `0` = Absent · `1` = Partial · `2` = Substantive.
Mark **N/A** (and exclude from the denominator — do not score 0) if a question
genuinely can't apply to this dataset; the packet flags likely N/A cases.
Merged questions `[x + y]`: **0** = neither half, **1** = one half met or both
weak, **2** = both substantive. For any score below 2, note in one phrase what
was missing.

---

### Q5.1 — Persistent, domain-appropriate home `[5.a + 5.b]`
**Is the data deposited in a recognized, supported research-data repository — specialist or generalist — under a persistent identifier?**

*You are given:*
- **Identifier** — the root identifier, flagged if it resolves as a PID
  (doi.org / hdl.handle.net / n2t.net/ark) or accession implying managed
  deposit.
- **Publisher / host** — the raw publisher value plus recognized archive names
  detected: a domain specialist (a sequence archive for sequencing, a
  proteomics repository for mass-spec, an imaging archive for imaging) **or**
  a well-known generalist (any of the 7 NIH GREI: Figshare, Dataverse, Zenodo,
  Dryad, Vivli, OSF, Mendeley Data); ideally a TRUST / CoreTrustSeal note.
- **Download hosts** — the host of each distribution URL, so you can recognize
  a repository without a fixed allow-list.
- **Domain hint** — keywords / data-collection type, to sanity-check specialist
  fit when one is clearly expected.

**Be accepting** — a generalist alone qualifies, and an
unfamiliar-but-well-formed institutional/community repository with a good PID
should be accepted.

- **0** — No PID *and* no recognizable repository — only a personal/lab site or a transient link.
- **1** — In a recognized repository but coverage is partial, **or** a PID or archive is present but not both / no retention or certification context.
- **2** — PID resolves *and* the data is in a recognized supported repository (specialist or generalist).

### Q5.2 — Well-governed `[5.c]`
**Is there an identified governance structure, an actionable contact, and a maintenance plan?**

*You are given:*
- **Governance committee / steward** — the named Data Governance Committee or
  steward.
- **Principal investigator** — for PI-led projects, the PI can anchor
  governance.
- **Maintenance plan** — raw text of the release/maintenance plan: what's
  maintained, on what cadence, by whom; policy/versioning/deprecation process.
- **Contact** — a contact/chairperson a user could actually write to.

- **0** — No governance structure, no maintenance plan, no contact.
- **1** — Some governance signal (a PI or committee named) but missing maintenance plan, terms-change process, or actionable contact.
- **2** — Governance structure identified *and* actionable contact *and* a maintenance plan describing ongoing stewardship.

### Q5.3 — Associated `[5.d]`
**Are the connections among datasets, software, computations, samples, and sub-crates modeled in the graph — beyond a bare file list?**

*Use the **interactive evidence graph** for this question* (green = Dataset/
Sample, red = Computation, yellow = Software; click a node's **ℹ** for
details):
- **Walk it** — start at the final output datasets and follow the arrows back.
  Can you get from the root to the raw inputs without dead ends? Do datasets
  connect to the computations that made them, and computations to their
  software?
- **Orphans** — are there nodes floating with no edges at all (entities listed
  but never connected)?

*Alongside the graph you are given rollups* so you don't have to count nodes
by hand: total entity count, root `hasPart` count, the fraction of entities
with at least one provenance link (`wasGeneratedBy` / `wasDerivedFrom` /
`isPartOf` / `usedSoftware` / `usedSample` / `usedInstrument`), and the
sub-crate count (release-of-crates, tied back to the parent or not).

- **0** — No machine-readable connections beyond the root's bare hasPart — a flat file list.
- **1** — Some provenance edges but thin coverage / many orphaned entities, or sub-crates not tied back to the parent.
- **2** — Components are densely connected; a tool can walk from root to raw inputs without dead ends.

---

**Section 5 score:** Q5.1 __ + Q5.2 __ + Q5.3 __ = **__ / 6**  (÷ 2 × questions answered)
