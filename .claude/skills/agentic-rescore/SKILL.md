---
name: agentic-rescore
description: Score an RO-Crate against the 28 AI-Ready rubrics agentically, with the host agent as the grader — dump deterministic evidence via `python -m aireadiness_grader.rubric_eval extract-evidence`, then have Claude (this skill) read each rubric.json + evidence.json and emit a RubricScore JSON per rubric. Never invokes fairscape-grade.
---

# Agentic grading — the host agent as grader

The grader (`aireadiness_grader/grade.py`, the `fairscape-grade` CLI) normally drives a separate LLM via `pydantic-ai`. Here, **Claude is the grader** — we reuse the deterministic `aireadiness_evidence` presentation pipeline for evidence, then score each rubric inline. Output matches `fairscape-grade`'s file layout exactly so downstream tooling can consume either.

## What to tell the user before any commands run

Before invoking the evidence dump or asking about subset selection, give them one paragraph of context so the rest of the phase isn't opaque:

> *"This is the **AI-Ready scoring** phase. The 28 rubrics are transcribed from "Rubric for Review of AI-readiness Evaluation Criteria" v1.8 (2026-09-10) into `src/aireadiness_evidence/rubric_defs.yaml` and cover seven domains: FAIRness (`0.x`), Provenance (`1.x`), Characterization (`2.x`), Pre-model Explainability (`3.x`), Ethics (`4.x`), Sustainability (`5.x`), Computability (`6.x`). Each rubric scores 0 (Absent), 1 (Partial), or 2 (Substantive), with rules that say literally what evidence justifies each level; a non-gating rubric may also be N/A when every element is inapplicable (N/A leaves the denominator). Max total is 56 points (2 × 28) minus any N/A. The **overall score** is the unweighted average of the seven domain percentages. Four gates are evaluated independently — FAIRness (0.a must be 2, the rest above 0), Provenance (all above 0), Standards (2.c above 0), Ethics (all above 0) — and a failed gate marks the result "Gating FAIL" (the score is still computed). Two dependency rules cap scores at aggregation: 1.b ≤ 1.a and 6.a ≤ 2.c.*
>
> *The scoring is two-step. First a deterministic Python pass (`python -m aireadiness_grader.rubric_eval extract-evidence`) walks the crate and dumps the relevant facts per rubric as typed evidence items — identifiers, license, schemas, format coverage, etc. — into a `grading/` folder. No LLM involved; just structured reading (plus optional URL/registry checks — pass `--no-network` to skip them). Then I fan the rubrics out to parallel subagents — one per rubric, all dispatched in a single message — and each subagent sees **only** its rubric JSON and its evidence JSON, nothing else. It writes its `score.json` and returns. After all rubrics are scored, a small Python aggregator computes the total and a per-criterion breakdown.*
>
> *The isolation matters for reproducibility: the score for any rubric is determined by the fixed prompt + that rubric + its evidence, not by anything I've seen earlier in this conversation (the paper, prior decisions, your phrasing). Anyone can re-run the same subagent prompt against the same `evidence.json` and reproduce the verdict. The evidence dump is itself reproducible and inspectable — `grading/<id>/evidence.json` is a self-contained audit trail. Each score comes with a written rationale and a `gaps` list that tells you what would raise it."*

## Preconditions

- A crate to grade. Resolve it from what the user gave you, in this order:
  1. an explicit path argument — a crate directory or an `ro-crate-metadata.json`;
  2. `ro-crate-metadata.json` in the current working directory;
  3. if a `.fairscape-state.json` wizard state file is present, `state.crate_path`.

  Ask if none of those resolve. Set `<crate>` = the metadata file, `<crate_dir>` = its directory; everything below writes to `<crate_dir>/grading/`.
- Nothing else is required. Grading runs against whatever shape the crate is in — a sparse crate just scores lower.

## 0. Ask: full sweep, or one criterion?

Twenty-eight rubrics is many conversation turns. Offer up front:
- **"All 28"** — full sweep.
- **"One criterion (0–6)"** — narrow to a single criterion. The user picks one of:
  - 0 FAIRness, 1 Provenance, 2 Characterization, 3 Pre-model Explainability,
  - 4 Ethics, 5 Sustainability, 6 Computability.

If subset, only iterate the matching rubrics. Aggregated score still computes correctly because `_aggregate` only sees the ones with `score.json`.

## 1. Dump evidence (deterministic, one shot)

```
Bash python -m aireadiness_grader.rubric_eval extract-evidence "<crate>" "<crate_dir>/grading/"
```

This writes:
- `<crate_dir>/grading/summary.json` — crate header, inventory, artifact links, list of rubric ids.
- `<crate_dir>/grading/ai-ready-evidence.json` — the full presentation the folders were split from.
- `<crate_dir>/grading/<id>-<slug>/rubric.json` — the criterion's practice / questions / 0-1-2 scoring rules (from `rubric_defs.yaml`) plus the shared `output_schema`.
- `<crate_dir>/grading/<id>-<slug>/evidence.json` — the criterion's typed evidence items.

Tell the user one line: `"dumped evidence for 28 rubrics → <grading>/"`. Don't read the dump into context — read per rubric in the next step.

## 2. Score each rubric (parallel subagents, one fan-out)

**Do not score rubrics in the main conversation.** Dispatch one `Agent(subagent_type=general-purpose)` per rubric, all in a single message so they run in parallel. This is non-negotiable for two reasons:

1. **Reproducibility.** Each subagent runs in a fresh context with only the fixed prompt + the rubric JSON + the evidence JSON. Same inputs → same scoring inputs every time. Anyone with the same `evidence.json` and the prompt template below can reproduce the verdict.
2. **No context contamination.** The main conversation has read the paper, heard the user's framing, made earlier decisions. None of that may bias the score. Subagents see *only* the two file paths — they cannot read the crate, the PDF, the state file, or prior turns.

### Which rubrics to dispatch

The full sweep is all 28 rubric folders under `<grading>/`. If the user picked a single criterion in step 0, filter to that prefix (`0.*`, `1.*`, etc.).

Before dispatching, skip any rubric whose `score.json` already exists — that's how resume works.

### The subagent prompt (use verbatim, fill only the three paths)

This prompt is part of the reproducibility contract. Do not customize it per rubric. Do not add crate facts, summaries, or commentary. The only variables are the three absolute paths.

```
You are scoring one AI-Ready rubric for an RO-Crate. Read only the two files at the given paths and write one output file. Do not read or fetch anything else.

RUBRIC_JSON: <abs path to grading/<id>-<slug>/rubric.json>
EVIDENCE_JSON: <abs path to grading/<id>-<slug>/evidence.json>
OUTPUT: <abs path to grading/<id>-<slug>/score.json>

Procedure:
1. Read RUBRIC_JSON. Its `scoring` block lists a rule per achievable score. Restate each rule to yourself literally before deciding. If the rubric carries a `gate_min`, it is a gating criterion (N/A is not permitted on it). If it carries `depends_on`, score it on its own evidence anyway — the dependency cap is applied downstream at aggregation, not by you.
2. Read EVIDENCE_JSON. Treat it as the complete factual basis. Do not assume any field that is not present. Do not invent @ids or strings. Items are typed ({label, kind, value}; the `evidence_kinds` map explains the kinds; `sub: true` items are derived checks on the primary item above them; a bool value of null means the check was inconclusive or not performed).
3. Pick the single rule whose conditions match the evidence — no averaging, no halves. If the rule for score 0 says "Absent" and the required field is missing, choose 0. Score "N/A" only when the rubric's notes define an N/A condition and EVERY element of the criterion is inapplicable to this dataset — and never on a gating criterion (one with `gate_min`).
4. Compose a JSON object exactly matching the rubric's `output_schema`:
   {
     "score": 0 | 1 | 2 | "N/A",
     "rationale": "1-3 sentences. Cite the rule that applied and the specific evidence fields that decided it.",
     "evidence": ["...direct @id refs or short string fragments that appear verbatim in EVIDENCE_JSON..."],
     "gaps": ["...specific missing things that would raise the score; empty list if score is 2..."]
   }
5. Write that JSON to OUTPUT (pretty-printed, trailing newline).
6. Reply with one line: "<rubric id> → <score>".

Tone: neutral and audit-friendly. Cite verbatim ("identifier: doi:10.18130/V3/KCBTMS — both rule-2 conditions are met"). Avoid value judgments ("great", "weakly characterized") and avoid the word "unvalidated" — peer-reviewed work is not unvalidated.

Pitfalls:
- Treating a missing field as score 1 when the rule says "Absent". Read the 0 rule literally.
- Citing the rubric JSON in `evidence` instead of EVIDENCE_JSON. The `evidence` list is the crate's evidence, not the rubric's text.
- Skipping `gaps` when score < 2. Always populate them — they are the actionable feedback.
```

### After the fan-out returns

1. `ls <grading>/*/score.json` to verify every dispatched rubric wrote its file. Re-dispatch any that are missing (same prompt, same paths).
2. Print one consolidated status block to the user — the score lines the subagents returned, one per line.
3. If a wizard state file is in play, record the run there once (see "Optional: wizard state" at the end). Otherwise the `grading/` folder is the only record needed.

## 3. Aggregate

After the loop (full or filtered):

```
Bash python -m aireadiness_grader.rubric_eval aggregate "<crate_dir>/grading/"
```

This writes `<grading>/aggregated_score.json` matching `fairscape-grade`'s shape: `total_score`, `max_score`, `percentage`, `overall_score` (the v1.8 unweighted domain average), `gating` (pass/fail label + the specific failures), `counts` (now including `na`), and `criteria` grouped by `id[0]` (each with its own `percentage`, and `gating`/`gate_failed` on gated domains). The aggregator also applies the dependency caps (1.b ≤ 1.a, 6.a ≤ 2.c) — a capped rubric keeps the grader's verdict in `uncapped_score` with a `capped_by` note.

Report the rollup to the user — one paragraph:
```
Scored 28/28 rubrics. Overall score: 75.0% (unweighted domain average) — Gating FAIL.
Points: 42 / 56.
  FAIRness:                   6/8  (gate: FAIL — 0.a scored 1, needs 2)
  Provenance:                 5/8  (gate: pass)
  Characterization:           7/10 (2.c gate: pass)
  Pre-model Explainability:   3/6
  Ethics:                     6/8  (gate: pass)
  Sustainability:             8/8
  Computability:              7/8

Top gaps: ...   (pull 3 from the worst-scoring rubrics' `gaps`)

Full per-rubric output: <crate_dir>/grading/
```

## Optional: wizard state

Standalone grading needs no state file — `<crate_dir>/grading/` holds everything. If this crate *was* built by the RO-Crate wizard (see the `fairscape_skills` bundle) and a `.fairscape-state.json` is present, append the run to it so the wizard can resume:

```json
{
  ...,
  "grading": {
    "dir": "<crate_dir>/grading",
    "completed_rubrics": ["0.a", "0.b", ...],
    "aggregated_score_path": "<crate_dir>/grading/aggregated_score.json",
    "summary": {"total": 42, "max": 56, "percentage": 75.0,
                "overall_score": 74.2, "gating": "Gating FAIL",
                "counts": {"substantive": 14, "partial": 8, "absent": 6,
                           "na": 0, "error": 0}}
  },
  "phase": "graded",
  "history": [..., {"ts": "...", "skill": "agentic-rescore",
                    "summary": "scored 28 rubrics: 42/56 (75.0%)"}]
}
```

Only claim `phase: graded` when all 28 rubrics are done; a subset run just updates `completed_rubrics`.

## Resume behavior

On invocation, check the on-disk presence of `<grading>/<id>-<slug>/score.json`. The disk is the source of truth — a `score.json` that exists counts as done. Only dispatch subagents for rubrics with no `score.json`. If the user wants to rescore one, delete its `score.json` (and remove its id from `completed_rubrics`) before re-invoking.

## Don't

- **Don't score rubrics in the main conversation.** Always fan out to subagents. The main context has read the paper, heard the user's framing, and made earlier decisions — using it to score taints the verdict and breaks reproducibility.
- **Don't customize the subagent prompt per rubric.** The only variables are the three file paths. No crate facts, no summaries, no "for context, the dataset is…" preface — the subagent must score from rubric + evidence alone.
- **Don't pass crate paths, the PDF, or state to subagents.** They get the rubric JSON path, the evidence JSON path, and the output path. Nothing else.
- Don't shell out to `fairscape-grade`. The whole point of this phase is to use Claude directly — `rubric_eval.py` is the only Python helper this skill calls.
- Don't write a `score.json` that doesn't match the rubric JSON's `output_schema`. If `additionalProperties: false`, no extra keys.
- Don't invent evidence. If `evidence.json` is sparse, score Absent or Partial with a `gaps` list explaining what's missing — that's the honest signal.
- Don't run the aggregator before all selected rubrics have `score.json` files written.
