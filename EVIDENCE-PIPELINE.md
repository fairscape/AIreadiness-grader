# Evidence presentation pipeline — status

Branch `evidence-presentation`, 2026-08-19. Migration complete: both grading
paths (agentic + `fairscape-grade`) run on this pipeline; the old
`rubrics/ai-ready` machinery is deleted.

## What was built

`src/aireadiness_evidence/` — extraction → transformation → presentation from a
FAIRSCAPE RO-Crate, matching the per-criterion Extractor / Transformation /
Presented specs in *Rubric for Human Review of AI.docx* v1.0. No scoring.
(Since updated to rubric v1.5 — see the migration section at the end.)

| Piece | What it does |
| --- | --- |
| `rubric_defs.yaml` | docx transcription: practice / questions / 0-1-2 rules / gating per criterion. Single source of rubric text. |
| `crate.py` | one-pass load of root + sub-crates into counters + bounded samples; discovers datasheet / prov-graph / evidence-graph HTML on disk |
| `sections/*.py` | 7 modules, one `extract_` / `transform_` / `present_` trio per criterion; evidence items typed (text/bool/count/percent/link/list/entity) and tiered primary vs `sub` (derived checks). Optional `estimate_` per criterion: the scoring rule applied mechanically to the facts → `{"score", "basis"}` in the presentation JSON, or None where the call needs human judgment (substance of prose, domain adequacy, N/A determinations the metadata can't settle) |
| `known.py` | PID schemes, repo hosts (specialist/generalist/software archives), ontology hosts, HL7 v3-Confidentiality codes, vendor formats, validator map |
| `network.py` | optional checks: URL resolution, re3data search, DOI content negotiation; timeouts and transient statuses (429/502/503/504) report inconclusive; `--no-network` skips |
| `render.py` + `templates/review.html.j2` | human-review HTML: scoring defs, grouped evidence, linkified URLs/DOIs, score radios + copy-as-JSON export, inventory table. Sticky summary bar (graded n/28, points on graded criteria, live-updating) with a "By section" dropdown — per-section graded/points/left counts plus one colored chip per criterion (2/1/0/N/A/ungraded, each a jump link) — and a "Next ungraded" jump button. Per-criterion estimate chip — dashed amber box labeled "Automated estimate" with basis bullets and a warning that it may be wrong; "use as starting point" fills the radio but nothing is ever pre-filled. Each section ends with a free-text section-comments box (Manlik's per-section context request). Page ends with a Score summary: per-section table (graded, points, %, N/A, gating badge) and a live radar chart of section percentages with a dashed unverified-estimates reference polygon. Scores/notes autosave to localStorage keyed by crate `@id` (restored on reload; Reset button clears). "Save review as HTML" serialises the page with the state written into a `<script type=application/json id=review-state>` block and a random `review_id`; on load the embedded state and the browser copy (keyed by crate `@id` + `review_id` so a received file never collides with your own review) are compared by `saved_at` and the newer wins. Export JSON carries each criterion's estimate alongside the human score, plus `section_notes` and per-section rollups |
| `cli.py` | `fairscape-evidence <crate> -o out/` → `ai-ready-evidence.json` + `ai-ready-review.html` |
| `bundle.py` | `fairscape-review-bundle out/ai-ready-review.html -o out.zip` (also `fairscape-evidence --zip`): zips the page, its JSON and every locally linked datasheet/preview/graph — followed transitively through the linked pages, data files excluded — under `crate/` with the page's links rewritten |

Verified on CM4AIJuneRelease (57k entities, 9 sub-crates): output committed at
`examples/cm4ai-june-2026/`. Cross-checks: dataset count matches the crate's
`evi:datasetCount` rollup exactly; protocol counts sum to the dataset total;
the 283 "Embargoed" placeholders match the embargo counter.

Decisions baked in (change in code if wrong):

- 1.b software-link % counts Computations only, not Experiments.
- 2.c schema-coverage denominator excludes image-format datasets.
- 3.c hash denominator excludes embargoed datasets.
- ARK ids are not hyperlinked (no reliable public resolver for NAAN 59853);
  http(s)/DOI references are.

## Grader migration (done 2026-08-19)

Both graders now consume the presentation instead of the old 28 YAMLs +
`extract.py`:

- `aireadiness_grader/rubric_eval.py` — `extract-evidence` builds the
  presentation and splits it into `<out>/<id>-<slug>/{rubric.json,
  evidence.json}` (same folder names as before; slugs derive from the docx
  criterion names and match the retired filenames exactly). `rubric.json` =
  practice / questions / scoring rules + the shared `output_schema` (the one
  block carried over from the old YAMLs, now the `OUTPUT_SCHEMA` constant);
  `evidence.json` = the criterion's typed items + an `evidence_kinds` legend.
  `aggregate` unchanged. New `--no-network` flag.
- `aireadiness_grader/grade.py` — prompt built from one presentation criterion;
  pydantic-ai / UVARC agent machinery unchanged. Accepts a crate dir or its
  `ro-crate-metadata.json`. Note: a criterion may define no rule for a level
  (0.d has only 0 and 2), so the prompt's rules block is built dynamically.
- Deleted: `rubrics/ai-ready/extract.py`, the 28 YAMLs (`1.c-interpretable.yaml`
  was YAML-invalid — the old `fairscape-grade` path crashed on it),
  `rubrics/ai-ready/grade.py`, `dump_prompts.py`, and the pyproject
  `force-include` bundling. `rubric_defs.yaml` + the HTML template ship inside
  the `aireadiness_evidence` package, so the wheel needs no extra bundling.
- `rubrics/ai-ready/human/` kept for now (owner call whether the review HTML
  replaces the Section-*.md walkthroughs).
- Skills updated: `agentic-rescore` (rubric.json layout, docx framing),
  `fairscape-rocrate-wizard` (5.5 datasheet note, Phase 5 framing). README
  updated.

### Old-vs-new re-grade of CM4AIJuneRelease (before deleting)

Both evidence dumps were graded criterion-by-criterion in isolation (Claude
subagents, rubric + evidence files only). Old path 48/56 (85.7%); new path
41/56 (73.2%). 20 of 28 criteria scored identically. The 8 diffs are rubric-text
differences, not extraction regressions — the docx rules are stricter or more
specific than the old YAML paraphrases:

| Criterion | old → new | Deciding difference |
| --- | --- | --- |
| 1.c Interpretable | 1 → 0 | docx requires archived software w/ PID (or code hosting for 1); all 4 Software entities have vendor pages only |
| 1.d Key actors | 2 → 1 | docx requires PIDs for people AND organizations; orgs have no ROR |
| 2.b Statistics | 1 → 0 | docx 0-rule: missing values not consistently encoded; no encoding convention documented |
| 2.e Data quality | 1 → 0 | docx requires evidence QC was applied; no QC language found |
| 4.b Ethically managed | 1 → 2 | docx asks for management appropriate to sensitivity ("Unrestricted" + plan), not a privacy-processing narrative |
| 5.d Associated | 2 → 0 | new evidence surfaces 9-of-19 linked sub-crates present on disk; docx requires all components accessible |
| 6.b Computationally accessible | 2 → 1 | docx 2-rule wants a documented API / standardized protocol; crate offers FTP + file:// links |
| 6.d Contextualized | 2 → 1 | docx 2-rule requires machine-readable example data; example/synthetic check is null |

(The 2.e grade also cited a bioRxiv HTTP 429 reported as a dead link; 429/5xx
now report inconclusive — fixed in `network.py` after the comparison run.)

## Agentic review document (2026-08-21)

`aireadiness_evidence/agentic_report.py` + `templates/agentic_review.html.j2`
render a **pre-scored, read-only** counterpart to the blank human-review page.
Input is a grading dir from `rubric_eval extract-evidence` in which every
`<id>-<slug>/` has gained a `score.json`; output is
`ai-ready-agentic-review.html` + `ai-ready-agentic-scores.json`:

```
python -m aireadiness_evidence.agentic_report <grading_dir> -o <out_dir> \
    [--link-base ..] [--label "who/what scored it"]
```

The page carries a total, per-section rollups, a static SVG radar (one axis per
section, no JS), a "where the points went" table of every sub-2 criterion with
the grader's first named gap, and one card per criterion holding the matched
rule, rationale, cited evidence, gaps, and the full extracted evidence in a
`<details>`. Where a criterion's mechanical `estimate` disagrees with the
grader's score, the card says so. `ai-ready-agentic-scores.json` is the whole
report — it is the audit trail, so the per-criterion grading folders do not
need to be kept.

Rendered for all four examples (scored by Claude Opus 5, one isolated agent per
rubric section, evidence taken from the committed presentations so the facts
match the human-review pages exactly):

| Crate | Total | Section 0 gate |
| --- | --- | --- |
| CM4AI June 2026 | 44 / 56 (78.6%) | passed |
| B2AI Voice | 38 / 56 (67.9%) | passed |
| AI-READI | 28 / 56 (50.0%) | not met (0.a) |
| CHoRUS | 26 / 56 (46.4%) | not met (0.a) |

Estimate-vs-grader disagreements clustered on 0.b and 0.c in three of the four
crates: the estimator's "standard vocabulary references found" check looks for
domain ontology hosts, while the docx questions for 0.b/0.c name metadata
vocabularies (DCAT, Datacite, schema.org, bioschemas) — which schema.org + EVI
satisfy. Worth reconciling in `sections/fairness.py`.

## Pipeline gaps worth closing

- 0.a question 2 (identifiers.org compact-ID prefix) is not checked.
- FAIRsharing is never queried (no public API); re3data query is
  publisher-host based and can miss (LibraData was found, but only because
  the host query matched).
- 6.a reports that a validator *exists*; it does not run one. Running
  `fairscape-cli rocrate validate` and reporting pass/fail was the original
  note in `rubric_extractor_notes.md`.
- 3.c detects per-entity md5/sha fields only — a hash manifest file would
  read as 0% coverage.
- Embargo detection is a string match on contentUrl/description.
- 6.d split detection is a name regex over dataset names only.
- Link checks cap at 3 hosts, http(s) only (ftp links not probed).
- No hermetic test: add a tiny in-repo example crate + golden presentation
  JSON (same pattern as fairscape_conversion plugins).
- The rubric docx itself is untracked — commit it next to rubric_defs.yaml.
- `d4d:samplingStrategies` (6.d) has no live example in CM4AI; untested
  against real data.

## Rubric v1.5 migration (2026-08-31)

The rubric doc moved from v1.0 (2026-08-14) to v1.5 (2026-08-29): "Rubric for
Human Review of AI-readiness Evaluation Criteria v1.5 2026-08-29.docx" (in the
repo root, next to the retired v1.0 "Rubric for Human Review of AI.docx").
Everything downstream of `rubric_defs.yaml` was updated:

**Rubric text** — `rubric_defs.yaml` retranscribed for all 28 criteria. The
substantive rule changes: 0.a drops the re3data/FAIRsharing question for the
glossary's "sustainable repository" definition (S3/GCS/Drive/Box excluded) and
demands version-specific PID resolution; 0.d gains a middle score (license
present but not machine-readable); 1.b adds provenance-gap/chain-of-custody
disclosure; 1.c accepts provider URIs for proprietary commercial software; 2.b
no longer blanket-N/As non-tabular data (missingness is scored in modality
terms); 2.c scores per format class; 2.d adds demographic-representativeness
and clinical site-selection questions ("state-vs-control" → "case-vs-control");
2.e wants a link to the specific QC protocol/software; 3.a must not re-score
2.d/3.b; 3.c hashes must live in the metadata; 4.a splits
retrospective-waiver vs prospective-consent-covering-AI/ML; 4.b adds PIA +
periodic re-identification reassessment; 4.c rewritten around
modality-specific prohibitions (voice/genomes/face/geolocation); 4.d's 0-rule
absorbs 6.b's old enforcement clause; 5.a narrows to raw data + retention
commitment; 5.b adds the multi-domain generalist branch; 5.c drops
terms-of-access and scores only DMP linkage/depth; 6.a is conditioned on 2.c.

**Scoring methodology (new in v1.5, implemented in `rubric_eval._aggregate`
and `agentic_report.build_report`)** —
- Domain score = points / max over applicable (non-N/A) criteria; graders may
  emit `"N/A"` (never on a gating criterion); the output schema, RubricScore
  model, and both HTML pages accept it.
- Overall score = **unweighted average of domain percentages**
  (`overall_score`), reported alongside the raw point percentage.
- Gates: FAIRness 0.a = 2 + rest > 0, Provenance all > 0, Standards 2.c > 0,
  Ethics all > 0. Encoded as `gate_min` per criterion in the yaml, evaluated
  independently, and a failure marks domain + overall "Gating FAIL" (score
  still computed).
- Dependency caps 1.b ≤ 1.a and 6.a ≤ 2.c (`depends_on` in the yaml), applied
  at aggregation; capped rubrics keep `uncapped_score` + `capped_by`. The
  human-review page warns live when a reviewer violates a cap.

**Extractors** — new evidence: machine-readable-license flag (0.d),
gap-disclosure regex (1.b), provider-site software bucket (1.c),
representativeness / case-control / clinical-site regexes (2.d), QC link list
(2.e), AI/ML-consent + waiver flags (4.a), PIA + reassessment flags (4.b),
high-risk-modality flags (4.c), unmanaged-storage detection (0.a, 5.a via
`known.NON_SUSTAINABLE_HOSTS`), stewardship-language flag (5.c), vocab-binding
flag (6.a). Estimates retuned to the v1.5 rules — notably 2.b no longer
auto-N/As, 4.c and 5.c became human calls above 0, and 1.c defers to the
reviewer when provider-site URIs would decide the score.

**Not yet done** —
- `rubrics/ai-ready/human/Section-*.md` (the merged-question human
  questionnaire) still reflects v1.0; it merges criteria in ways v1.5's gates
  and caps complicate. Owner call whether to regenerate it or retire it in
  favor of the review HTML.
- The v1.5 docx ("Rubric for Human Review of AI-readiness Evaluation Criteria
  v1.5 2026-08-29.docx") is untracked — commit it next to the tracked v1.0
  docx (or replace it).
- Any previously generated review/presentation outputs (they were dropped
  from the repo at the project rename) reflect v1.0 and should be re-run if
  resurrected.
- 0.a "resolves to a specific version of the dataset" is asserted, not
  verified (would need content-negotiation on the PID landing page).
- 4.d enforcement (controlled data actually blocked without auth) is not
  probed.

## Rubric v1.8 migration (2026-09-10)

The rubric doc moved from v1.5 (2026-08-29) to v1.8 (2026-09-10) and was
retitled: "Rubric for Review of AI-readiness Evaluation Criteria v1.8
2026-09-10.docx" (repo root, next to the v1.5 and v1.0 docx). No criteria,
gates, thresholds, or dependency caps changed; `rubric_defs.yaml` is
re-transcribed verbatim, the citable title (`rubric.rubric_title`) follows the
new name, and the presentation JSON's `glossary` / `methodology` carry the
expanded v1.8 glossary and the scoring-worksheet appendix (the v1.5 "score
record" bullet was dropped from the rubric and from the YAML).

Wording that reached code:
- 0.a / 5.a scoring now says *sustainable* repository, not
  *domain-appropriate* (5.a's evidence detail updated to match).
- 2.d's question is "state-vs-control" again (improve.js basis text updated).
- 0.d evidence: the "well-known open license" flag is gone (the rubric never
  asked for it), and the AI/ML scan is a plain-text line — "No specific
  mention of AI/ML detected" or "AI/ML language detected. Sample: …" — instead
  of a ✓/✗ flag, since a mention is not a pass or a fail until a human reads
  it.

See `rubrics/ai-ready/human/V1.5-DELTA.md` for the per-criterion wording
deltas. The human questionnaire packets there still reflect v1.0.
