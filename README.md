# AI-Readiness grader

Grades an RO-Crate against the *Rubric for Review of AI-readiness Evaluation
Criteria* v1.8: 28 criteria in seven domains, each graded 0 / 1 / 2.

## Install

```bash
pip install -e .
```

Requires Python 3.10+. Pulls in `pydantic-ai`, `jinja2` and `pyyaml`.

## Run

```bash
fairscape-evidence /path/to/crate -o review/
open review/ai-ready-review.html
```

The crate is any directory with a `ro-crate-metadata.json`
([RO-Crate 1.2 spec](https://www.researchobject.org/ro-crate/specification/1.2/)). A worked example
is in `examples/apms-paclitaxel/` (crate plus finished review).

Options:

| flag | |
| --- | --- |
| `-o DIR` | output directory (default `./ai-ready-review`) |
| `--no-network` | skip URL resolution and registry lookups |
| `--json-only` | write the evidence JSON only |
| `--zip FILE` | also write a shareable zip (see below) |

## Outputs

| file | |
| --- | --- |
| `ai-ready-review.html` | Review page for a human. Each criterion shows the rubric rules, the evidence found in the crate, an automated estimate where one is possible, and a score radio with notes. Scores roll up per domain with a radar chart. |
| `ai-ready-evidence.json` | The same evidence, typed, for grading by a model. |


## Grading with a model

**In an agent host** (Claude Code or similar) with this repo's `.claude/skills/`
visible, run `/agentic-rescore`. It dumps the evidence, grades each criterion
in an isolated subagent, and aggregates. No API key needed.

**From the command line:**

```bash
fairscape-grade <crate> <out-dir> --model anthropic:claude-opus-4-7 --api-key "$ANTHROPIC_API_KEY"
```

`--model` is a [pydantic-ai](https://ai.pydantic.dev/) model string.
Prefixes: `anthropic`, `openai`, `google`, `groq`, `uvarc`. Any OpenAI-compatible
server (Ollama, vLLM) works via `openai:` with `OPENAI_BASE_URL` set.

From Python:

```python
from aireadiness_grader import grade
result = grade.grade_crate("crate/", "grading/", model="anthropic:claude-opus-4-7", api_key="...")
```

Both paths write the same layout:

```
grading/
├── aggregated_score.json     totals, domain rollups, gate results
├── summary.json              crate header, inventory, criterion list
├── ai-ready-evidence.json
└── 0.a-findable/             one directory per criterion
    ├── rubric.json
    ├── evidence.json
    └── score.json            score, rationale, gaps
```

## The rubric

| Domain | ids | gate |
| --- | --- | --- |
| FAIRness | `0.a`–`0.d` | `0.a` must be 2, the rest above 0 |
| Provenance | `1.a`–`1.d` | all above 0 |
| Characterization | `2.a`–`2.e` | `2.c` above 0 |
| Pre-model Explainability | `3.a`–`3.c` | none |
| Ethics | `4.a`–`4.d` | all above 0 |
| Sustainability | `5.a`–`5.d` | none |
| Computability | `6.a`–`6.d` | none |

Overall score is the unweighted mean of the seven domain percentages. A failed
gate marks the result *Gating FAIL* but the score is still reported.
Non-gating criteria may be N/A and leave the denominator. Two caps apply:
`1.b ≤ 1.a` and `6.a ≤ 2.c`.

Long-form reviewer notes are in `rubrics/ai-ready/human/`.

## Improving a crate

```bash
fairscape-improve /path/to/crate     # -> <crate>/ai-ready-improve.html
```

An offline form listing every property the graders read, easiest first, with
live score estimates and schema validation. Download the improved
`ro-crate-metadata.json` when done. It only edits single properties on existing
entities; it does not create entities or links.

In an agent host, `/post-grade-improve` reads `aggregated_score.json` and
offers a skill per gap it can close: `link-authors-orcids`,
`link-subjects-ontologies`, `compute-summary-stats`, `hash-coverage`,
`ethics-questionnaire`, `portability-interview`. Each also runs on its own.
