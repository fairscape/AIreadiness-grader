# Evidence presentation pipeline — status and remaining work

Branch `evidence-presentation`, 2026-08-19.

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
| `network.py` | optional checks: URL resolution, re3data search, DOI content negotiation; timeouts report inconclusive; `--no-network` skips |
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

## NOT done: the old grader rubrics

The 28 YAMLs in `rubrics/ai-ready/` were **not** updated. They predate the
docx: their scoring rules differ in wording and their `extractor_inputs`
schemas are shaped for the old `rubrics/ai-ready/extract.py`. The LLM-grader
path (`fairscape_wizard/grade.py` → `rubric_eval.py` → old YAMLs + extract.py)
still runs entirely on the old machinery.

## Migration plan (then delete the old code)

1. **Point the LLM grader at the new pipeline.** Each criterion entry in
   `ai-ready-presentation.json` already carries practice, questions, the
   docx scoring rules, and typed evidence — exactly what a grading prompt
   needs. Rework `rubric_eval.py` to build its prompt from one presentation
   criterion instead of (old YAML + extractor_inputs). Keep the old YAMLs'
   `output_schema` block (score/rationale/evidence/gaps) — it is the one part
   worth carrying over, either into `rubric_defs.yaml` or a shared constant.
2. **Re-grade a known crate both ways** (CM4AIJuneRelease) and diff scores +
   rationales before switching.
3. **Delete once the new path grades:**
   - `rubrics/ai-ready/extract.py` (1,826 lines) and `__pycache__`
   - `rubrics/ai-ready/*.yaml` (28 files)
   - `rubrics/ai-ready/grade.py`, `dump_prompts.py`
   - the `[tool.hatch.build.targets.wheel.force-include]` bundling of
     `rubrics/ai-ready` in `pyproject.toml`
   - `rubrics/ai-ready/human/` if the review HTML replaces the Section-*.md
     walkthrough docs (owner call)

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
