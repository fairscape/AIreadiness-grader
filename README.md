# fairscape-grader

This repo is the **FAIRSCAPE wizard**: a suite of skills that walks a non-expert
user through documenting a research pipeline as a
[FAIRSCAPE](https://fairscape.github.io/) RO-Crate, plus a **grader** that scores
that crate against the 28 AI-Ready rubrics.

- **Wizard** — the `.claude/skills/` bundle. The interview + build-script
  emission flow (`/fairscape-rocrate-wizard`) and everything around it.
- **Grader** — `rubrics/ai-ready/` (the 28 rubric YAMLs + the deterministic
  `extract.py` evidence extractors) plus the `fairscape_wizard` Python helper
  module that drives them.
- **Evidence presentation** (this branch) — `src/fairscape_evidence/`, a fresh
  extraction → transformation → presentation pipeline that builds the evidence
  document requested by *Rubric for Human Review of AI.docx*. See
  [Evidence presentation](#evidence-presentation) below.

## Evidence presentation

```
fairscape-evidence /path/to/crate -o out/          # or: PYTHONPATH=src python3 -m fairscape_evidence.cli
fairscape-evidence /path/to/crate --no-network     # skip URL / registry lookups
```

Writes two files built from the same presentation dict — no scoring in either:

| Output | Audience |
| --- | --- |
| `ai-ready-presentation.json` | evidence handed to an LLM grader |
| `ai-ready-review.html` | human reviewer: rubric text + scoring defs + evidence, score radios with a copy-as-JSON export |

Layout of `src/fairscape_evidence/`:

| File | Stage |
| --- | --- |
| `rubric_defs.yaml` | rubric text transcribed from the docx (practice / questions / 0-1-2 rules) — edit rubric wording here |
| `crate.py` | extraction: one pass over root + sub-crates, aggregates + bounded samples (50k-entity crates stay cheap) |
| `sections/*.py` | one module per rubric section; each criterion is an `extract_` / `transform_` / `present_` trio |
| `known.py` | reference tables: PID schemes, re3data-style repo hosts, ontology hosts, HL7 confidentiality codes, vendor formats |
| `network.py` | optional lookups: URL resolution, re3data search, DOI content negotiation; timeouts report as inconclusive |
| `pipeline.py` / `render.py` / `templates/review.html.j2` | assembly and the Jinja HTML |

Datasheet (`ro-crate-datasheet.html`) and every sub-crate evidence graph
(`ro-crate-prov-graph.html`, `*-evidence-graph.html`) are discovered on disk and
linked from both outputs. `examples/cm4ai-june-2026/` holds the output for the
CM4AI June 2026 release.

## Launching the wizard

The wizard is a skill bundle, so you launch it from inside an agent host — either
**Claude Code** or **opencode**. In the project directory you want to document,
invoke the top-level skill:

```
/fairscape-rocrate-wizard
```

It scans your folder, pre-fills crate metadata from a paper PDF or existing
`ro-crate-metadata.json` if present, interviews you one step at a time
(inputs → script → outputs), runs a plausibility check, then emits and runs
`build_rocrate.py` to produce `ro-crate-metadata.json`. State is checkpointed to
`.fairscape-wizard-state.json`, so you can quit and resume.

## Grading a crate

There are two ways to grade.

**1. Inside the wizard (host LLM as grader).** The `agentic-rescore` skill has the
agent driving the wizard (Claude, in Claude Code) read each rubric + extracted
evidence and score it directly. No API key needed — it uses whatever model is
already running the host.

**2. LLM-agnostic CLI: `fairscape-grade`.** A standalone command that runs the
full pipeline against the LLM of your choice. Use this when you want a specific
model, a non-interactive/batch run, or grading outside an agent host.

```bash
fairscape-grade <ro-crate-metadata.json> <output-dir> \
    --model anthropic:claude-opus-4-7 \
    --api-key "$ANTHROPIC_API_KEY"
```

`--model` is a `pydantic-ai` model string — the provider prefix picks the LLM:

| prefix | env var set from `--api-key` | example |
| --- | --- | --- |
| `anthropic` | `ANTHROPIC_API_KEY` | `anthropic:claude-opus-4-7` |
| `openai` | `OPENAI_API_KEY` | `openai:gpt-4o` |
| `google` / `google-gla` | `GOOGLE_API_KEY` | `google:gemini-1.5-pro` |
| `groq` | `GROQ_API_KEY` | `groq:llama-3.3-70b-versatile` |
| `uvarc` | *(used directly)* | `uvarc:Kimi K2.5` — UVA RC GenAI endpoint |

**Local models.** Anything that speaks the OpenAI API (Ollama, LM Studio, vLLM,
llama.cpp) works through the `openai:` prefix — point `OPENAI_BASE_URL` at your
server and pass a throwaway key:

```bash
export OPENAI_BASE_URL=http://localhost:11434/v1   # e.g. Ollama
fairscape-grade <crate.json> <out-dir> --model openai:llama3.1 --api-key local
```

It writes a per-rubric folder (`rubric.yaml` + `evidence.json` + `score.json`)
under `<output-dir>/rubrics/`, a `summary.json`, and a top-level
`aggregated_score.json` with totals grouped by criterion.

Equivalent invocations:

```bash
python -m fairscape_wizard.grade <crate.json> <out-dir> --model ... --api-key ...
python rubrics/ai-ready/grade.py  <crate.json> <out-dir> --model ... --api-key ...   # back-compat shim
```

Or call it from a script and get the aggregate back as a dict:

```python
from fairscape_wizard import grade

result = grade.grade_crate(
    "ro-crate-metadata.json",
    "grading-out/",
    model="anthropic:claude-opus-4-7",
    api_key="...",
)
print(result["percentage"], result["total_score"], "/", result["max_score"])
```

`grade_crate` writes the same files to the output dir and returns the aggregate.
Pass `verbose=False` to silence progress (it logs to stderr; the returned dict is
the only thing on stdout).

## Install

```bash
pip install -e .
```

This installs the `fairscape_wizard` module and the `fairscape-grade` console
script, and pulls in `fairscape-models`, `fairscape-cli`, and `pydantic-ai`. The
28 rubric YAMLs and `extract.py` are bundled into the wheel, so `fairscape-grade`
works the same whether you installed from a source checkout or a built wheel.

## Sandboxed run (Docker)

Run the wizard in a container that can only see one folder, where
`--dangerously-skip-permissions` is safe because the container has
no filesystem access outside the bind mount.

```bash
./sandbox.sh --build           # one-time: build the image
./sandbox.sh ~/crates/my-paper # launch against any folder
```

First launch drops you into `claude` with no credentials — run `/login` inside to
OAuth with your Claude subscription. The token is saved to a named Docker volume
(`fairscape-claude-auth`) and reused on every later launch. The folder you pass is
mounted as `/workspace`; outputs land back in that folder on the host. Other
commands: `--shell <folder>`, `--logout`, `--help`.
