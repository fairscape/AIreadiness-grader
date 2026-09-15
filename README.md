# AI-Readiness grader

Scores an RO-Crate against *Rubric for Review of AI-readiness Evaluation
Criteria* v1.8 (2026-09-10): 28 criteria, seven domains, 0 / 1 / 2 each.

```bash
pip install -e .
fairscape-evidence /path/to/my-crate -o review/
open review/ai-ready-review.html
```

`ai-ready-review.html` is the review page: one self-contained HTML file that
walks the rubric criterion by criterion. For each criterion it shows the
rubric's practice statement and its 0 / 1 / 2 scoring rules, then the evidence
the tool found in the crate for that criterion (identifiers, license, schemas,
checksums, ethics fields, and so on), an automated estimate where the rules
can be applied mechanically to that evidence, and a *Your score* radio with a
notes box. Scores roll up per domain in a sticky bar and a radar chart; the page
autosaves to the browser, saves as HTML with your scores in place, and exports
as JSON. Nothing to install to open it.

The same evidence is also written as `ai-ready-evidence.json`, for scoring by
a model rather than a person. Both files come from one pass over the crate.

No crate yet? See [Getting an RO-Crate](#getting-an-ro-crate). A worked
example, crate and finished review, is in
[`examples/apms-paclitaxel/`](examples/apms-paclitaxel/).

## Three ways to score

### A human, in the review page

Open `ai-ready-review.html` and work down it. Scores roll up per domain as you
go; the page keeps your work in browser storage and exports it as JSON. One
file, nothing to install, emailable to a reviewer.

**Save review as HTML** downloads the page with every score, note and section
comment written into it. Send that file and the recipient opens it with your
scores in place; anything they add is kept apart from their own review of the
same crate, and the newer of the file's scores and the browser's wins on
reload. Saving again keeps the same file identity.

The page links to the crate's datasheet, previews and provenance graphs by
relative path, so on its own it only works next to the crate.
`fairscape-review-bundle out/ai-ready-review.html -o out.zip` (or
`fairscape-evidence ... --zip out.zip`) writes a zip with the page, its
evidence JSON and every locally linked page — following the links those
pages make to sub-crate previews and graphs — under `crate/`, with the links
rewritten so they work wherever the zip is unpacked. Bundle a saved copy and
the scores travel with it.

Long-form notes for human reviewers are in `rubrics/ai-ready/human/`, one file
per domain plus `HUMAN-GRADER-METADATA-SPEC.md`.

### An agent you're already talking to

In Claude Code or another agent host with this repo's `.claude/skills/`
visible:

```
/agentic-rescore
```

It dumps the evidence, then fans out one subagent per criterion. Each subagent
sees only its `rubric.json` and its `evidence.json`, writes a `score.json` with
a rationale and a `gaps` list, and returns. A Python pass then aggregates.

Subagents are isolated so a score depends on the prompt plus one criterion's
evidence, and nothing else in the conversation. Re-running reproduces the
verdict. No API key: it uses whatever model runs the host.

### A specific model, from the command line

`fairscape-grade` runs the same evidence through a model you name. Use it for
batch runs or outside an agent host.

```bash
fairscape-grade <crate-dir-or-metadata.json> <output-dir> \
    --model anthropic:claude-opus-4-7 \
    --api-key "$ANTHROPIC_API_KEY"
```

`--model` is a [pydantic-ai](https://ai.pydantic.dev/) model string. The prefix
picks the provider.

| prefix | env var set from `--api-key` | example |
| --- | --- | --- |
| `anthropic` | `ANTHROPIC_API_KEY` | `anthropic:claude-opus-4-7` |
| `openai` | `OPENAI_API_KEY` | `openai:gpt-4o` |
| `google` / `google-gla` | `GOOGLE_API_KEY` | `google:gemini-1.5-pro` |
| `groq` | `GROQ_API_KEY` | `groq:llama-3.3-70b-versatile` |
| `uvarc` | *(used directly)* | `uvarc:Kimi K2.5` — UVA RC GenAI endpoint |

Anything speaking the OpenAI API (Ollama, LM Studio, vLLM, llama.cpp) works
through the `openai:` prefix. Point `OPENAI_BASE_URL` at your server:

```bash
export OPENAI_BASE_URL=http://localhost:11434/v1   # e.g. Ollama
fairscape-grade <crate> <out-dir> --model openai:llama3.1 --api-key local
```

From Python, to get the aggregate back as a dict:

```python
from aireadiness_grader import grade

result = grade.grade_crate("path/to/crate", "grading-out/",
                           model="anthropic:claude-opus-4-7", api_key="...")
print(result["percentage"], result["total_score"], "/", result["max_score"])
```

### What a run leaves on disk

The agentic path and `fairscape-grade` write the same layout, so downstream
tools can read either.

```
grading/
├── aggregated_score.json          totals, domain rollups, gate results
├── summary.json                   crate header, inventory, criterion list
├── ai-ready-evidence.json         the full evidence
└── 0.a-findable/
    ├── rubric.json                practice, questions, 0/1/2 rules
    ├── evidence.json              what the crate says about this criterion
    └── score.json                 score, rationale, gaps
```

## Two halves

Whichever way you score, grading splits in two, and the code keeps them apart.

**Finding evidence** is deterministic Python. For each criterion it collects
the facts that criterion asks about: identifiers, license, schemas, checksums,
ethics fields.

**Applying the rules** is judgment. A human or a model reads the 0/1/2
definitions against the evidence and picks a score.

The upshot: `ai-ready-evidence.json` records exactly what a scorer was looking
at, so any score can be checked, and two reviewers who disagree can point at
the same file.

## Outputs

```bash
fairscape-evidence /path/to/crate -o out/
```

| File | For |
| --- | --- |
| `out/ai-ready-review.html` | A human. Rubric text, scoring rules, evidence. Score radios, per-domain rollups, radar chart, comment boxes, browser autosave, save-as-HTML, copy-as-JSON. |
| `out/ai-ready-evidence.json` | A machine. The same evidence, typed. |

Datasheets (`ro-crate-datasheet.html`) and provenance graphs
(`ro-crate-prov-graph.html`, `*-evidence-graph.html`) found on disk are linked
from both outputs.

Network lookups (URL resolution, re3data, DOI dereference) run by default and
are time-bounded. A timeout or a transient response (HTTP 429, 502, 503, 504)
is reported as inconclusive, with the status, not as a failure.

Options:

| flag | |
| --- | --- |
| `-o DIR` | output directory (default `./ai-ready-review`) |
| `--no-network` | skip URL resolution and registry lookups; offline, faster |
| `--json-only` | write the evidence JSON and skip the review page |
| `--zip FILE` | also write a shareable zip of the review page and every local page it links to |

`fairscape-review-bundle out/ai-ready-review.html -o out.zip` zips an existing
review the same way.

## Getting an RO-Crate

The grader reads a directory with a `ro-crate-metadata.json` in it.

**Try the example.** `examples/apms-paclitaxel/` holds a CM4AI crate (EndoTag
AP-MS profiling of MDA-MB-468 cells under paclitaxel, September 2026 release:
`crate/ro-crate-metadata.json` plus its two data schemas) and the review the
tool produced from it, `review/ai-ready-review.html` and
`review/ai-ready-evidence.json`. Open the review page to see what a finished
run looks like, or regenerate it:

```bash
fairscape-evidence examples/apms-paclitaxel/crate -o examples/apms-paclitaxel/review
```

**Build one with fairscape-cli.**
[fairscape-cli](https://github.com/fairscape/fairscape-cli) creates and
validates crates from the command line: `fairscape-cli rocrate init` starts a
crate in the current directory (`create` takes a path), `add` copies a file in
and registers it, `register` adds metadata for a dataset, software or
computation, and `validate` checks the result against the RO-Crate 1.2 and
`fairscape_models` schemas.

**Or use the wizard.** The interview wizard, the Dataverse / PhysioNet /
Figshare importers and the manifest builders live in the sibling
`fairscape_skills` bundle; none of that is in this repo.

## How the rubric scores

28 criteria, seven domains, 0 (Absent) / 1 (Partial) / 2 (Substantive). Max 56
points.

| Domain | ids | gated |
| --- | --- | --- |
| FAIRness | `0.a`–`0.d` | yes — `0.a` must be 2, the rest above 0 |
| Provenance | `1.a`–`1.d` | yes — all above 0 |
| Characterization | `2.a`–`2.e` | `2.c` gates (Standards) |
| Pre-model Explainability | `3.a`–`3.c` | no |
| Ethics | `4.a`–`4.d` | yes — all above 0 |
| Sustainability | `5.a`–`5.d` | no |
| Computability | `6.a`–`6.d` | no |

A non-gating criterion can be N/A when every element is inapplicable; N/A
leaves the denominator.

The overall score is the unweighted average of the seven domain percentages,
not the raw point total, so a small domain isn't drowned out by a large one.

Gates are evaluated independently. A failed gate marks the result *Gating
FAIL*; the score is still reported.

Two dependency caps apply at aggregation: `1.b ≤ 1.a` and `6.a ≤ 2.c`. A capped
criterion keeps the grader's original verdict in `uncapped_score`.

## Improving a crate

### `fairscape-improve`, an offline form

```bash
fairscape-improve /path/to/crate       # -> <crate>/ai-ready-improve.html
fairscape-improve -o generic.html      # no crate embedded; load one in the page
```

One HTML page, two views of the same fields. **Checklist** lists every property
the graders read, easiest first: values you can paste, then a sentence or two,
then narrative fields, then the Software table. It has a *hide filled* filter, a
progress count and a *next empty* button. **By criterion** mirrors the review
page, one card per criterion with its rules, its evidence, and the fields
feeding it. Fill what you know, skip the rest, download the improved
`ro-crate-metadata.json` whenever.

- **Live scores.** The mechanical estimates (`estimate_*`, no network) re-run on
  every edit. Human-judgment criteria are marked `?`.
- **Validation.** Edits are checked against JSON schemas generated from the
  `fairscape_models` pydantic classes, the same ones `fairscape-cli rocrate
  validate` uses. Download is never blocked; issues get a jump link and a
  one-click fix for string-vs-list shape.
- **Prior scores.** `grading/aggregated_score.json` in the crate directory is
  embedded automatically and shown per criterion.
- **Scope.** The page only sets or edits single properties on entities that
  already exist. No new entities, no new graph links. Checksums, schemas,
  summary statistics and Sample/Instrument/Person entities are marked out of
  scope on the cards that need them.

Edits persist in the browser (localStorage, keyed by crate `@id`). "Download
edits only" writes just the patch. Built for crates that come out of a workflow
recorder with provenance but little description.

### Guided improvement skills

In an agent host, `/post-grade-improve` reads `aggregated_score.json`, shows
which criteria scored below 2, and offers a skill for each gap it can close.
Each one interviews you for what's needed, validates against the
`fairscape_models` schema, and writes the crate in place.

| Criterion | Skill | What it does |
| --- | --- | --- |
| `1.d` Key Actors | `link-authors-orcids` | resolve authors to ORCID URIs |
| `2.a` Semantics | `link-subjects-ontologies` | ground keywords in MeSH / EDAM / NCIt / GO |
| `2.b` Statistics | `compute-summary-stats` | summary stats for local tabular files |
| `3.c` Verifiable | `hash-coverage` | md5 + sha256 across Datasets and Software |
| `4.a` `4.b` `4.d` Ethics | `ethics-questionnaire` | ethics fields, one question at a time |
| `6.c` Portable | `portability-interview` | container image, requirements, runtime |

Each also runs on its own (`/hash-coverage`) against any crate.

## Install

```bash
pip install -e .
```

| module | script | role |
| --- | --- | --- |
| `aireadiness_evidence` | `fairscape-evidence` | evidence extraction, review page |
| `aireadiness_grader` | `fairscape-grade` | LLM scoring, agentic-path helpers |
| `aireadiness_improve` | `fairscape-improve` | the improvement form |

Pulls in `fairscape-models`, `fairscape-cli`, and `pydantic-ai`. Rubric text and
HTML templates ship inside the packages, so a source checkout and a built wheel
behave the same.

## Layout

```
src/aireadiness_evidence/
├── rubric_defs.yaml      the rubric, transcribed from the docx; edit wording here
├── crate.py              extraction: one pass over root + sub-crates, bounded
│                         samples (50k-entity crates stay cheap)
├── sections/*.py         one module per domain; each criterion is an
│                         extract_ / transform_ / present_ trio
├── known.py              PID schemes, repository hosts, ontology hosts,
│                         HL7 confidentiality codes, vendor formats
├── network.py            optional lookups; timeouts report as inconclusive
└── pipeline.py, render.py, templates/review.html.j2

src/aireadiness_grader/
├── rubric_eval.py        evidence dump, score aggregation (agentic path)
└── grade.py              the LLM round-trips (fairscape-grade)

src/aireadiness_improve/
├── fields.py             the field catalogue; add a field here
├── schemas.py            pydantic -> JSON schema
└── templates/            improve.js (crate model, estimators, validator),
                          improve.html.j2, cli.py

rubrics/ai-ready/human/   long-form notes for human reviewers
.claude/skills/           agentic grading and improvement skills
```

`EVIDENCE-PIPELINE.md` is the working log: what changed in each rubric
migration, known gaps, old-vs-new comparisons.
