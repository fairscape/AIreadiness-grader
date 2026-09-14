---
name: post-grade-improve
description: After a grading run writes aggregated_score.json, offer the user a menu of focused improvement skills that target the rubrics that scored below 2. Each leaf skill edits ro-crate-metadata.json in place after validating against the fairscape_models pydantic schema. Optionally re-invokes agentic-rescore on touched rubrics so the user sees the new score. Delegates to link-authors-orcids, link-subjects-ontologies, ethics-questionnaire, compute-summary-stats, hash-coverage, portability-interview.
---

# Post-grade improvements

A grading run (`agentic-rescore`, or `fairscape-grade`) has written `<crate_dir>/grading/aggregated_score.json` with a per-rubric breakdown. Surveys of nine real crates show baselines cluster at 67–77 % (38–43 / 56). The same ~10 rubrics keep landing at score 1 (Partial), and most of those gaps are mechanical — the crate has the content, it just doesn't have the JSON-LD shape the rubric reads. This phase offers the user a short menu of focused skills that close those gaps in a few guided steps.

This is **always optional**. Skipping leaves the crate exactly as the grading run left it.

## What to tell the user before showing the menu

One paragraph of context, then the menu:

> *"Your score has the room to climb. From the rubric outputs I can see which rubrics scored below the ceiling, and most of them turn out to be mechanical fixes — adding ORCID URIs on authors, grounding keywords in ontologies, filling in a few ethics fields, computing summary stats and hashes for local files, documenting the compute environment. I've got a focused skill for each of those. You pick which ones to run, I'll interview you for just what's needed, edit the crate JSON in place, and validate every edit against the fairscape_models pydantic schema before writing — so nothing gets saved that breaks downstream tooling. After you're done choosing, I'll offer to re-grade just the touched rubrics so you can see the new score."*

## Preconditions

- A readable `aggregated_score.json`. Resolve it in this order: an explicit path the user gave; `<crate_dir>/grading/aggregated_score.json`; `state.grading.aggregated_score_path` if a `.fairscape-state.json` wizard state file is present. If none resolve, tell the user "nothing has graded this crate yet — run `/agentic-rescore` first" and stop.
- `<crate>` (`ro-crate-metadata.json`) and `<crate_dir>` resolve to real files.

If a state file records `phase == "improved"` (resume case), say *"You ran improvements last session — `state.improvements.ran` lists which. Want to run more, re-grade, or stop?"* and branch from the answer.

## 1. Read the score and pick gap-rubrics

```python
agg = json.load(open("<crate_dir>/grading/aggregated_score.json"))
```

`agg["criteria"]` is a dict keyed by criterion id (`"0"`–`"6"`); each contains a `"rubrics"` list of `{id, sub_criterion, score}`. Build a flat `[(id, score, sub_criterion)]` of every rubric whose `score < 2`, then keep **only** the ones a leaf skill in this phase can address:

| Rubric id | Leaf skill                  |
|-----------|-----------------------------|
| `1.d`     | `link-authors-orcids`       |
| `2.a`     | `link-subjects-ontologies`  |
| `2.b`     | `compute-summary-stats`     |
| `3.c`     | `hash-coverage`             |
| `4.a`     | `ethics-questionnaire`      |
| `4.b`     | `ethics-questionnaire`      |
| `4.d`     | `ethics-questionnaire`      |
| `6.c`     | `portability-interview`     |

Sort by potential gain (score 0 → +2 ceiling > score 1 → +1 ceiling), then by criterion id for stability — except that any rubric currently **failing its gate** (v1.8: 0.a below 2; 0.b/0.c/0.d, all of 1.x and 4.x, or 2.c at 0) sorts first and is flagged, since a single gate failure marks the whole result "Gating FAIL" regardless of points. Dedupe so `ethics-questionnaire` shows up once even if all three of 4.a/4.b/4.d are below 2 — surface it with the combined gain estimate.

If the flat list is empty (every relevant rubric is already 2), tell the user *"Nothing left for me to nudge — the gaps left are ones these skills don't cover (FAIRness / Sustainability / etc.). Run `agentic-rescore` if you want a fresh look or fix them by hand."* and exit.

## 2. Show the menu

Render one line per applicable skill, with the rubric ids it touches, current score(s), and a rough gain ceiling. Example:

```
Improvement options (pick any that look worth it):

  1. link-authors-orcids       — 1.d (currently 1)         +1 ceiling     ORCID URIs on authors
  2. link-subjects-ontologies  — 2.a (currently 1)         +1 ceiling     MeSH/EDAM/etc. for keywords
  3. ethics-questionnaire      — 4.a/4.b/4.d (1/1/1)       +3 ceiling     framework, IRB, de-id, HL7 code
  4. compute-summary-stats     — 2.b (currently 1)         +1 ceiling     row/col counts + per-column stats
  5. hash-coverage             — 3.c (currently 1)         +1 ceiling     md5+sha256 on Datasets/Software
  6. portability-interview     — 6.c (currently 1)         +1 ceiling     container + env + hardware refs
```

Then ask:

> *"Which would you like to run? Say a list of numbers (e.g. `1,3,5`), `all`, or `skip`."*

Resolve `all` to every numbered option. Resolve `skip` to "exit without changes". Anything else: parse as comma-separated indices.

## 3. Run leaves sequentially

For each chosen leaf, in the order the user gave (or numeric order for `all`):

1. Tell the user one line: *"Starting `<leaf>` — targets rubric(s) `<ids>`."*
2. Invoke the leaf via `Skill(<leaf-name>)`.
3. When it returns, note it in your running tally of leaves that ran.
4. If the leaf reported a validation failure (pydantic error), note the rubric id as a validation failure and tell the user *"`<leaf>` couldn't write — the proposed edit didn't validate. Skipping. The crate is unchanged."* Continue to the next leaf.

Leaves run sequentially, never in parallel. Each one re-reads `ro-crate-metadata.json` from disk, so later leaves see earlier leaves' edits.

After every leaf, the leaf is responsible for atomic-writing the crate. This router only tracks which leaves ran and reports at the end.

## 4. Offer a rescore (don't force)

When all chosen leaves are done, ask:

> *"Run `agentic-rescore` to see the new score? I'll only re-score the rubrics that changed — `<ids>`. Or stop here and re-grade later with `/agentic-rescore`."*

If yes:
1. For each touched rubric id, delete `<crate_dir>/grading/<id>-<slug>/score.json`. (`agentic-rescore`'s resume logic skips rubrics that already have a `score.json` on disk — deleting forces a re-score.)
2. Invoke `agentic-rescore` with no filter. It will re-run only the missing ones, then re-aggregate.
3. Diff the old aggregate (read `aggregated_score.json` before running any leaf) against the new one; report the delta, including the v1.8 overall score and gate status:
   ```
   Score: 42 → 47 / 56  (+5) · overall 73.8% → 82.1% · gates: Gating FAIL → gates passed
     1.d  1 → 2
     4.a  1 → 2
     4.b  1 → 2
     4.d  1 → 2
     2.a  1 → 1   (no change — see gaps)
   ```

If no: leave grading state untouched, tell them how to re-grade later.

## 5. Report, and optionally record state

Close with a summary of what ran, what was skipped, and any validation failures.

Standalone runs need no state file. If this crate was built by the RO-Crate wizard (see the `fairscape_skills` bundle) and `.fairscape-state.json` is present, append:

```json
{
  "improvements": {
    "ran": ["link-authors-orcids", "ethics-questionnaire"],
    "skipped": ["compute-summary-stats", "hash-coverage", ...],
    "validation_failures": [],
    "rescored_at": "ISO-8601 or null",
    "last_run_at": "ISO-8601"
  },
  "phase": "improved",
  "history": [..., {"ts": "...", "skill": "post-grade-improve",
                    "summary": "ran 2 of 6 improvement skills; rescored: +5"}]
}
```

Resume rule: if `phase == "improved"` on next invocation, ask whether to run more leaves or re-grade. Don't auto-rerun anything.

## Don't

- Don't run multiple leaves in parallel — each mutates `ro-crate-metadata.json` and would race.
- Don't auto-rerun `agentic-rescore`. Always ask — the rubric subagents are billed work.
- Don't surface options for rubrics there's no leaf for (FAIRness, Sustainability, etc.). They need different fixes than this menu covers; mention them in passing if the user asks why they're not listed.
- Don't write to `ro-crate-metadata.json` from this router. Leaves are responsible for the edit + the validate + the atomic write.
- Don't proceed if a leaf reported validation failure — surface and skip; never write a broken crate.
