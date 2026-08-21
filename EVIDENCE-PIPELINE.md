# Evidence presentation pipeline — status

Branch `evidence-presentation`, 2026-08-19. Migration complete: both grading
paths (agentic + `fairscape-grade`) run on this pipeline; the old
`rubrics/ai-ready` machinery is deleted.

## What was built

`src/aireadiness_evidence/` — extraction → transformation → presentation from a
FAIRSCAPE RO-Crate, matching the per-criterion Extractor / Transformation /
Presented specs in *Rubric for Human Review of AI.docx* v1.0. No scoring.

| Piece | What it does |
| --- | --- |
| `rubric_defs.yaml` | docx transcription: practice / questions / 0-1-2 rules / gating per criterion. Single source of rubric text. |
| `crate.py` | one-pass load of root + sub-crates into counters + bounded samples; discovers datasheet / prov-graph / evidence-graph HTML on disk |
| `sections/*.py` | 7 modules, one `extract_` / `transform_` / `present_` trio per criterion; evidence items typed (text/bool/count/percent/link/list/entity) and tiered primary vs `sub` (derived checks). Optional `estimate_` per criterion: the scoring rule applied mechanically to the facts → `{"score", "basis"}` in the presentation JSON, or None where the call needs human judgment (substance of prose, domain adequacy, N/A determinations the metadata can't settle) |
| `known.py` | PID schemes, repo hosts (specialist/generalist/software archives), ontology hosts, HL7 v3-Confidentiality codes, vendor formats, validator map |
| `network.py` | optional checks: URL resolution, re3data search, DOI content negotiation; timeouts and transient statuses (429/502/503/504) report inconclusive; `--no-network` skips |
| `render.py` + `templates/review.html.j2` | human-review HTML: scoring defs, grouped evidence, linkified URLs/DOIs, score radios + copy-as-JSON export, inventory table. Sticky summary bar (graded n/28, points on graded criteria, live-updating) with a "By section" dropdown — per-section graded/points/left counts plus one colored chip per criterion (2/1/0/N/A/ungraded, each a jump link) — and a "Next ungraded" jump button. Per-criterion estimate chip — dashed amber box labeled "Automated estimate" with basis bullets and a warning that it may be wrong; "use as starting point" fills the radio but nothing is ever pre-filled. Each section ends with a free-text section-comments box (Manlik's per-section context request). Page ends with a Score summary: per-section table (graded, points, %, N/A, gating badge) and a live radar chart of section percentages with a dashed unverified-estimates reference polygon. Scores/notes autosave to localStorage keyed by crate `@id` (restored on reload; Reset button clears). Export JSON carries each criterion's estimate alongside the human score, plus `section_notes` and per-section rollups |
| `cli.py` | `fairscape-evidence <crate> -o out/` → `ai-ready-presentation.json` + `ai-ready-review.html` |

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

- `aireadiness_wizard/rubric_eval.py` — `extract-evidence` builds the
  presentation and splits it into `<out>/<id>-<slug>/{rubric.json,
  evidence.json}` (same folder names as before; slugs derive from the docx
  criterion names and match the retired filenames exactly). `rubric.json` =
  practice / questions / scoring rules + the shared `output_schema` (the one
  block carried over from the old YAMLs, now the `OUTPUT_SCHEMA` constant);
  `evidence.json` = the criterion's typed items + an `evidence_kinds` legend.
  `aggregate` unchanged. New `--no-network` flag.
- `aireadiness_wizard/grade.py` — prompt built from one presentation criterion;
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
