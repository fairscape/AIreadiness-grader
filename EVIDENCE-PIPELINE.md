# Evidence presentation pipeline — status

Branch `evidence-presentation`, 2026-08-19. Migration complete: both grading
paths (agentic + `fairscape-grade`) run on this pipeline; the old
`rubrics/ai-ready` machinery is deleted.

## What was built

`src/fairscape_evidence/` — extraction → transformation → presentation from a
FAIRSCAPE RO-Crate, matching the per-criterion Extractor / Transformation /
Presented specs in *Rubric for Human Review of AI.docx* v1.0. No scoring.

| Piece | What it does |
| --- | --- |
| `rubric_defs.yaml` | docx transcription: practice / questions / 0-1-2 rules / gating per criterion. Single source of rubric text. |
| `crate.py` | one-pass load of root + sub-crates into counters + bounded samples; discovers datasheet / prov-graph / evidence-graph HTML on disk |
| `sections/*.py` | 7 modules, one `extract_` / `transform_` / `present_` trio per criterion; evidence items typed (text/bool/count/percent/link/list/entity) and tiered primary vs `sub` (derived checks) |
| `known.py` | PID schemes, repo hosts (specialist/generalist/software archives), ontology hosts, HL7 v3-Confidentiality codes, vendor formats, validator map |
| `network.py` | optional checks: URL resolution, re3data search, DOI content negotiation; timeouts and transient statuses (429/502/503/504) report inconclusive; `--no-network` skips |
| `render.py` + `templates/review.html.j2` | human-review HTML: scoring defs, grouped evidence, linkified URLs/DOIs, score radios + copy-as-JSON export, inventory table |
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

- `fairscape_wizard/rubric_eval.py` — `extract-evidence` builds the
  presentation and splits it into `<out>/<id>-<slug>/{rubric.json,
  evidence.json}` (same folder names as before; slugs derive from the docx
  criterion names and match the retired filenames exactly). `rubric.json` =
  practice / questions / scoring rules + the shared `output_schema` (the one
  block carried over from the old YAMLs, now the `OUTPUT_SCHEMA` constant);
  `evidence.json` = the criterion's typed items + an `evidence_kinds` legend.
  `aggregate` unchanged. New `--no-network` flag.
- `fairscape_wizard/grade.py` — prompt built from one presentation criterion;
  pydantic-ai / UVARC agent machinery unchanged. Accepts a crate dir or its
  `ro-crate-metadata.json`. Note: a criterion may define no rule for a level
  (0.d has only 0 and 2), so the prompt's rules block is built dynamically.
- Deleted: `rubrics/ai-ready/extract.py`, the 28 YAMLs (`1.c-interpretable.yaml`
  was YAML-invalid — the old `fairscape-grade` path crashed on it),
  `rubrics/ai-ready/grade.py`, `dump_prompts.py`, and the pyproject
  `force-include` bundling. `rubric_defs.yaml` + the HTML template ship inside
  the `fairscape_evidence` package, so the wheel needs no extra bundling.
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
