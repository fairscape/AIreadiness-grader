---
name: fairscape-rocrate-wizard
description: Unified FAIRSCAPE RO-Crate wizard. Builds a crate from any source — local project folder, Dataverse DOI, PhysioNet URL, Figshare article, or any other publicly-accessible remote source via a generic CSV manifest path. Drives a 6-phase flow — import → schema inference → AI-Ready enrichment from a paper → provenance tracking → agentic rubric grading → optional post-grade improvements. The manifest is the convergence point: every source kind reduces to `manifest.csv + crate.json` and feeds `fairscape-cli import manifest`. Runs preflight-check first; routes to env-setup if anything is missing. Delegates to preflight-check, env-setup, remote-import, build-manifest, build-local-manifest, extract-crate-metadata, scan-project-folder, remote-schema-infer, remote-ai-ready-enrich, provenance-tracking, register-embargoed-dataset, agentic-rescore, post-grade-improve, emit-build-shell, and remote-checkpoint.
---

# FAIRSCAPE RO-Crate Wizard (unified)

Builds an RO-Crate from any source — a local project folder OR a dataset that's *already published* on Dataverse, PhysioNet, Figshare, or anywhere else publicly accessible (NCBI, ProteomeXchange, cellxgene, OpenNeuro, AWS/GCP open-data buckets, lab portals, ...). The earlier `fairscape-rocrate-wizard-legacy` skill is preserved for one release as an escape hatch for users with entity-centric `.fairscape-wizard-state.json` files they don't want migrated.

**The convergence point is `fairscape-cli import manifest`.** All source kinds reduce to a `manifest.csv` + `crate.json` pair, get fed to the importer, and produce a normal `ro-crate-metadata.json`. From Phase 2 onward, every path runs the same skills.

**Source kinds**, picked at Phase 1:
- **Local project folder** — form for crate-level metadata, then folder walk via `scan-project-folder`, then manifest built locally with `build-local-manifest` (hashes singleton files, skips bulk groups), then import. Crate gets written into the project folder itself.
- **Dataverse / PhysioNet / Figshare** → existing dedicated importers (one API call, fully automatic).
- **Generic remote** → `build-manifest` skill researches the source's published file inventory, then `fairscape-cli import manifest` builds the crate. Slower but works against any openly-accessible source.

## User-facing rules

1. **Vocabulary**: never say "entity", "ARK", "@id", "extractor", "rubric inputs" — say "the crate", "the file list", "the score". Translate the model behind the scenes.
2. **One question at a time.** Don't interrogate.
3. **Explain before you do.** Before any non-trivial action — a shell command, a CLI invocation, a write to the crate — say in 1–2 sentences what's about to happen and *why*. Example: *"I'll call `fairscape-cli import dataverse` next. That CLI talks to the Dataverse API, pulls the dataset's metadata (title, authors, file list, DOI), and writes a starter `ro-crate-metadata.json` into the output folder. The actual data files stay on Dataverse — we just record where to find them."* The user should never see a command without knowing its goal.
4. **Show progress at phase boundaries.** When a phase finishes, summarize what the user now has on disk and what the next phase will do. Not "phase 1 done" — give them: *"Phase 1 done. You now have `./<slug>-rocrate/ro-crate-metadata.json` listing 3,855 files with their Dataverse URLs and the dataset-level metadata Dataverse provided. Next I'll sample a representative of each file group to figure out the column structure."*
5. **Persist after every phase** to `.fairscape-remote-state.json`. The user must be able to quit anywhere and resume — tell them this once, at the start.
6. **Public datasets only** in this version. If the user pastes a private DOI, tell them token support isn't here yet.

## Conversation flow

### 1. Open

**First**, invoke `preflight-check`. It verifies Python ≥ 3.10, the `fairscape-cli` binary on PATH, and that `fairscape_models`, `fairscape_cli`, and `fairscape_wizard` import. On pass, one-line confirmation and continue. On fail, surface the blockers and offer `env-setup` (it walks the user through PyPI vs editable dev install, optionally setting up a fresh `.venv`). If the user picks `skip` at env-setup, stop here — none of the phases below can run without the environment.

`Bash pwd` to confirm the working directory.

Check for state files in priority order: `.fairscape-state.json` (unified, v2) → `.fairscape-remote-state.json` (legacy remote, v1 — auto-upgrade in place) → `.fairscape-wizard-state.json` (legacy local entity-centric — ask before migrating; see "Migration from legacy state files" below).

- **State exists** → invoke `remote-checkpoint`. Ask: **"Resume from `<phase>`, or start over?"** On "start over", confirm before deleting state, then proceed to phase 1.
- **No state** → give the user a real intro, not a one-liner:

  > *"I'll build an RO-Crate — a structured folder of metadata about a dataset. The data can live anywhere: on your machine in a project folder I can walk, or already published online on Dataverse, PhysioNet, Figshare, or any other publicly-accessible source. Either way, I gather metadata, build a manifest of files, and produce a crate ready for grading.*
  >
  > *We'll go through six phases:*
  > *1. **Import.** Get the file list and dataset-level metadata into a starter `ro-crate-metadata.json`. For local folders I'll ask a quick form (name, description, authors, keywords, license) then walk the folder, hash distinct files, and build a manifest. For supported online repositories (Dataverse/PhysioNet/Figshare) this is one API call. For any other online source I research the published file inventory and build a manifest from that.*
  > *2. **Schemas.** Group the tabular files by name pattern, sample one representative per group, and infer column names + types so the crate describes what's in each file.*
  > *3. **AI-Ready enrichment** (optional). If you have a paper describing the dataset, I'll read it and add the fields that make the crate AI-Ready — biases, limitations, collection methods, intended use cases, license/access details. Most of these live in the MLCommons RAI vocabulary (the `rai:*` field prefix); the bucket also includes standard descriptors like `license` and `conditionsOfAccess`.*
  > *4. **Provenance tracking** (optional). Document the pipeline that produced the derived files — for each step, what software ran (ideally a GitHub or Zenodo link), which datasets it consumed, which datasets it produced. We then run a tool that fills in the reverse links so every output points back at the step that made it.*
  > *5. **Grading** (optional). Score the crate against the 28-rubric AI-Ready checklist so you see where it's strong and where there are gaps.*
  > *6. **Improvements** (optional). After grading, I'll show you which rubrics scored below ceiling and offer focused skills for the mechanical fixes — ORCID URIs on authors, ontology IRIs on keywords, the ethics field set, summary statistics, hash coverage, container/env references. Each fix is interview-guided, edits the crate in place, and re-validates against the schema before writing.*
  >
  > *I save my progress after every step to `.fairscape-state.json` in this folder — quit anytime, run me again with the same command and I'll pick up where we left off."*

  Then proceed.

### 2. Phase 1 — Import

Frame the phase first with the source-kind question:

> *"**Phase 1 — Import.** First I need to know where your data is, so I can pick the right way to bring it in. Two top-level options:*
>
> *(a) **A local project folder on your machine.** I'll ask you a quick form for the crate-level metadata (name, description, authors, keywords, license), then walk the folder, compute hashes for distinct files (skipping bulk groups of similar files like '847 microscopy .tif images' — you can fill those in later with `/hash-coverage`), build a manifest, and produce the crate inside your project folder.*
>
> *(b) **A dataset published online.** Paste a DOI or URL. For Dataverse, PhysioNet, or Figshare, I call the repository's API directly. For anywhere else (NCBI, S3 buckets, GitHub releases, etc.) I research the published file inventory and build a manifest from that.*
>
> *Either way, the data bytes themselves stay where they are — the crate just records URLs (`file:///...` for local, `https://...` for remote)."*

Then ask:

> *"Which is it — **(a) local folder** or **(b) published online**? If (b), paste the link/DOI in the same message."*

#### Branch (a) — Local folder

1. Ask for the folder path (default: `pwd`). Tell the user the crate will be written into that same folder (`ro-crate-metadata.json`, `manifest.csv`, `crate.json` will all sit at the project root).
2. Invoke `extract-crate-metadata` with the **form** option (one of its four paths — PDF / existing crate / interview / form). The form collects name, description, authors, keywords, license, publication_date, doi via `AskUserQuestion` + free-text. Writes `state.crate_metadata`. State phase → `metadata_captured`.
3. Invoke `scan-project-folder` against the project root. Detects bulk groups (≥10 same-extension siblings in one directory) and writes `state.scan`.
4. Invoke `build-local-manifest`. It hashes singleton files (streaming md5+sha256), skips hashes for bulk-group members, and writes `<project_root>/manifest.csv` + `<project_root>/crate.json`. State phase → `manifest_built`.
5. Shell out:
   ```bash
   fairscape-cli import manifest <project_root>/manifest.csv --output-dir <project_root>
   ```
   This writes `<project_root>/ro-crate-metadata.json`. State phase → `imported`. Write `state.source = {"kind": "local", "project_root": "<abs>"}`.

#### Branch (b) — Published online

Detect the source kind from what they pasted:

- `doi:` prefix OR a known Dataverse hostname (`dataverse.harvard.edu`, `dataverse.lib.virginia.edu`, etc.) → **dataverse**
- `physionet.org/content/` substring → **physionet**
- DOI prefix `10.6084/m9.figshare.` OR `figshare.com/articles/` substring → **figshare**
- Anything else (NCBI URLs, S3/GCS buckets, GitHub repos, cellxgene links, paper URLs without a repo) → **manifest**

For dataverse / physionet / figshare, invoke `remote-import` (the existing path). It writes state with `state.phase = "imported"` when done.

For **manifest**, route this way:

1. Tell the user *"This source isn't in one of my dedicated repositories, so I'll use the generic manifest path. I'll research the dataset's published file list, write `manifest.csv` + `crate.json`, then run `fairscape-cli import manifest` to build the crate."*
2. Invoke `build-manifest` with the user's brief (whatever they pasted plus any paper they mentioned). It produces `<workdir>/<slug>/manifest.csv` + `<workdir>/<slug>/crate.json`. **`build-manifest` does NOT call the importer** — you do, next.
3. Decide the crate output dir (default: `<workdir>/<slug>-rocrate`). Tell the user the path before running.
4. Shell out:
   ```bash
   fairscape-cli import manifest <workdir>/<slug>/manifest.csv --output-dir <crate_dir>
   ```
5. Write state with `state.phase = "imported"`, `state.source.kind = "manifest"`, `state.source.url_or_doi = <whatever the user pasted>`, plus `state.source.manifest_dir = <workdir>/<slug>` so we can find the originals on resume.

After the import finishes (any branch), summarize plainly for the user — not as a status line. Match the language to the source kind:

- **Local**: *"Imported. Crate at `<project_root>/ro-crate-metadata.json`. Lists **`<N>` files** under your project root — `<M>` had hashes computed, `<K>` are bulk-group files with hashes left blank (e.g. `<example_group_key>`). Categorized as **`<dist>`**. State saved to `.fairscape-state.json`."*
- **Remote (any sub-kind)**: *"Imported. Crate at `<crate_dir>/ro-crate-metadata.json`. Lists **`<N>` files** with their `<source-kind>` URLs and the dataset-level metadata the source provided (title, authors, DOI `<doi>`, version `<v>`). Categorized as **`<dist>`** — gzipped files are skipped when inferring schemas because the schema tool doesn't read gzip. State saved to `.fairscape-state.json`."*

Substitute the real numbers and source label. Don't keep the placeholder `<N>`s.

### 3. Phase 2 — Schemas

Frame the phase first:

> *"**Phase 2 — Schemas.** Right now the crate knows the files exist but not what's *in* them. I'll look at the file names and propose groups of files that probably share a structure (e.g. 3,840 per-patient parquets that all have the same columns). You confirm or revise the grouping. For each group I sample ONE file — Range-GET for text, full download for parquet/hdf5 — and run `fairscape-cli schema infer` to detect column names and types. The resulting schema is then linked to every Dataset entry in the group via `evi:Schema`, so the crate documents what every file looks like without me re-querying 3,840 of them."*

Then invoke `remote-schema-infer`. If `state.tabular_files` is empty, tell the user "no tabular files to infer schemas for — skipping phase 2" and bump phase.

After it finishes, summarize:

> *"Schemas done. I added `<K>` schemas (one per group), with `<M>` total Dataset entries pointing at them. The schema JSONs are at `<crate_dir>/schemas/` and the sampled raw data sits in `<crate_dir>/.cache/samples/` (gitignored). State saved."*

### 4. Phase 3 — AI-Ready enrichment

Frame the phase first:

> *"**Phase 3 — AI-Ready enrichment.** This is the optional but valuable step. We're going to fill in the fields that make the crate **AI-Ready** — the context a downstream model trainer needs before using the data. Most of these live in the MLCommons RAI vocabulary (`rai:dataCollection`, `rai:dataBiases`, `rai:dataLimitations`, `rai:dataUseCases`, ethics/maintenance fields), but the same step also fills in standard descriptors the importer may have missed (`license`, `conditionsOfAccess`, `copyrightNotice`, `associatedPublication`). The repository's API usually doesn't have any of this — but the paper that describes the dataset usually does. If you have a paper PDF (or URL), I'll read it and extract those fields, then merge them into the crate's root entry. I won't overwrite anything the importer already set — only fill in nulls and extend lists."*

Then ask:

> *"Got a paper? Give me a local path, a URL, or say 'skip' and we'll move on."*

Invoke `remote-ai-ready-enrich` with the user's answer. After it finishes, summarize:

> *"Merged `<N>` AI-Ready fields from `<paper>` — `<K>` RAI fields (e.g. `rai:dataCollection`, `rai:dataBiases` with 4 items, `rai:dataLimitations` with 3, `rai:dataUseCases` with 5) plus `<S>` standard descriptors (`license`, `conditionsOfAccess`, …). The full extracted dict is in state under `state.ai_ready` if you want to review or edit before grading."*

### 5. Phase 4 — Provenance Tracking (optional)

Frame the phase first:

> *"**Phase 4 — Provenance Tracking.** Right now the crate lists your files but doesn't connect them — there's no record of which file is a raw input and which was produced by some computation. This phase captures the pipeline: for each computational step, I'll ask what software ran (ideally a GitHub or Zenodo link so it stays reachable), which datasets it consumed, and which datasets it produced. The key thing is we're documenting **steps**, not files — if the same script ran over 50 inputs to produce 50 outputs, that's **one step** with 50 inputs and 50 outputs, not 50 steps. If a step's raw input isn't in the crate (sensitive PHI, temporary recording, file too large to host), I'll add a placeholder Dataset with `contentUrl: \"Embargoed\"` so the chain still has something to link — that path runs through a sub-skill called `register-embargoed-dataset`. When the user-facing half is done, I'll run `fairscape-cli augment link-inverses` to fill in the reverse direction automatically (so every output gets a `generatedBy` pointer back at the step). The Provenance criterion in grading will then have entities to score against."*

Then invoke `remote-provenance-tracking`. The skill asks the user whether to register provenance at all — if they skip, state advances to `provenance_tracked` with `skipped: true` and grading proceeds normally.

After it finishes, summarize:

> *"Provenance done. Recorded `<N>` computations and `<M>` software entries; ran `link-inverses` so every output dataset now has a `generatedBy` link back at the step that produced it. State saved."*

### 5.5 Build the datasheet (auto, before grading)

Not a phase — no user input. Before grading runs, the crate needs a sibling `ro-crate-datasheet.html`: rubric 3.a (Data Documentation) looks for `*datasheet*.html` files on disk (`fairscape_evidence`'s crate loader), and the absence of a human-readable datasheet drags the 3.a score down regardless of how well-populated the metadata is. The build also emits `ro-crate-linkml.yaml` as a side effect.

Tell the user one sentence, then run the command — don't prompt:

> *"Quick auto-step before grading: I'll generate an HTML rendering of the crate so it's shareable as a single page and the grader can find it. No input needed."*

Then:

```bash
fairscape-cli build datasheet "<state.crate_dir>"
```

On success, write `state.datasheet_built_at = <iso utc now>`, append a one-line `history` entry (`"Built ro-crate-datasheet.html"`), and continue to Phase 5. Do not advance `state.phase` — the datasheet build is gating, not a phase.

On failure, surface stderr and stop. Do not proceed to grading — rubric 3.a will misreport without the file. Most failures are missing template assets or a malformed crate; the user can usually fix and retry. Offer to re-run after they fix the underlying issue.

Run the build *every time* you enter Phase 5, even on resume — Phase 4 may have appended Computations and embargoed placeholders since the last build, and the datasheet should reflect them. The command is idempotent; re-running overwrites the HTML and LinkML in place.

### 6. Phase 5 — Grading (optional)

Frame the phase first:

> *"**Phase 5 — Grading.** Now we measure how complete the crate is against the 28-rubric AI-Ready checklist. The rubric text is transcribed from "Rubric for Human Review of AI.docx" v1.0 into `src/fairscape_evidence/rubric_defs.yaml` and covers seven criteria: FAIRness, Provenance, Characterization, Pre-model Explainability, Ethics, Sustainability, Computability. The flow is two-step: first I run the deterministic `fairscape_evidence` pipeline, which walks the crate and dumps typed evidence per rubric — no LLM involved, just structured reading. Then I (Claude) read each rubric's scoring rules and the extracted evidence and give it a 0 (Absent), 1 (Partial), or 2 (Substantive), with a rationale and a list of gaps that would raise the score. The result is a per-rubric folder of `score.json` files plus an `aggregated_score.json` with the total."*

Then ask:

> *"Score all 28 now, or just one criterion (0–6) — say 'all', a digit, or 'skip'?"*

Three answers:
- **All 28** → invoke `agentic-rescore` with no filter.
- **One criterion (digit)** → invoke `agentic-rescore` with that prefix.
- **Skip** → leave `state.phase = "provenance_tracked"` and tell them they can run `/agentic-rescore` later from anywhere with this state file.

When grading finishes, `state.phase = "graded"`. Surface the per-criterion rollup with one-line interpretation, e.g. *"FAIRness 6/8 — strong on findability and accessibility; the gap is around interoperable namespace coverage. Provenance 5/8 — the importer didn't have any computations or software in scope so this whole criterion is below ceiling."*

### 7. Phase 6 — Post-grade improvements (optional)

Frame the phase first:

> *"**Phase 6 — Improvements.** Your score has the room to climb. Most crates after Phase 5 land in the 67–77 % range, and the recurring gaps are mechanical — ORCID URIs not on the authors, keywords not grounded in ontologies, the ethics field set partly filled, summary stats and hashes missing, container/env undocumented. I've got a focused skill for each of those. You pick which to run, I'll interview you for just what's needed, edit the crate JSON in place, and validate every edit against the fairscape_models schema before writing. When you're done choosing, I'll offer to re-grade just the touched rubrics so you can see the new score."*

Then ask:

> *"Want to run any improvement skills, or stop here? (`yes` / `skip`.)"*

If `yes`, invoke `post-grade-improve`. It handles the menu, dispatches the leaves, and writes the new `state.improvements` block. When it returns, `state.phase = "improved"`.

If `skip`, leave `state.phase = "graded"` and tell the user they can run `/post-grade-improve` later from anywhere with this state file.

### 8. Done

Print one paragraph:
```
Done. Your crate is at <crate_dir>.
  Score: <total>/<max> (<pct>%)
  ro-crate-metadata.json:  <abs path>
  Schemas:                 <crate_dir>/schemas/
  Grading evidence:        <crate_dir>/grading/
```

## State file contract

All skills in this flow read and write `<cwd>/.fairscape-state.json` (atomic write: temp + `os.replace`). For one release the wizard also tolerates legacy `.fairscape-remote-state.json` as a fallback name and migrates it in place on first run.

Schema (`schema_version: 2`):

```json
{
  "schema_version": 2,
  "phase": "init|metadata_captured|manifest_built|imported|schemas_done|rai_done|provenance_tracked|graded|improved",
  "source": {"kind": "dataverse|physionet|figshare|manifest|local",
             "url_or_doi": "...",         // dataverse/physionet/figshare/generic-remote
             "server_url": "...",          // dataverse only
             "manifest_dir": "...",        // generic-remote manifest path
             "project_root": "..."},       // local source kind only
  "scan": {/* output of scan-project-folder; only present for source.kind="local" */},
  "crate_metadata": {/* output of extract-crate-metadata form path; only for source.kind="local" */},
  "crate_dir": "/abs/path",
  "crate_path": "/abs/path/ro-crate-metadata.json",
  "imported_at": "ISO-8601",
  "tabular_files": [...],
  "schemas": [...],
  "schemas_done": [...],
  "paper": {"path": "...", "kind": "pdf|url", "fetched_at": "..."},
  "ai_ready": {/* RAI fields (22) + standard descriptors (license, conditionsOfAccess, etc.) */},
  "ai_ready_merged_at": "...",
  "provenance": {
    "skipped": false,
    "source_dataset_ids": ["ark:...", "..."],
    "software": [{"guid": "ark:...", "name": "...",
                  "source_kind": "github|zenodo|local|other",
                  "source_url": "..."}],
    "computations": [{"guid": "ark:...", "name": "...",
                      "usedSoftware": ["..."],
                      "usedDataset": ["..."],
                      "generated": ["..."]}],
    "link_inverses_run_at": "ISO-8601"
  },
  "grading": {"dir": "...", "completed_rubrics": [...],
              "aggregated_score_path": "...",
              "summary": {"total": N, "max": M, "percentage": P}},
  "improvements": {
    "ran": ["link-authors-orcids", "ethics-questionnaire"],
    "skipped": [...],
    "validation_failures": [],
    "rescored_at": "ISO-8601 or null",
    "last_run_at": "ISO-8601"
  },
  "datasheet_built_at": "ISO-8601",
  "history": [{"ts": "...", "skill": "...", "summary": "..."}]
}
```

Each delegated skill appends to `history` with a one-line summary after every confirmed mutation.

### Migration from legacy state files

On every wizard start, before any phase work, check for legacy state files in `cwd`:

- **`.fairscape-remote-state.json` with `schema_version: 1`** → in-place upgrade: rename the key to 2, no field reshape. The new `source.kind = "manifest"` and `source.kind = "local"` values won't appear because v1 only used `dataverse|physionet`; existing values stay.
- **`.fairscape-wizard-state.json`** (the old entity-centric local-wizard state) → ask the user: *"I see an older local-wizard state file. The unified wizard uses a different shape. Want me to migrate it? Your original file gets saved as `.fairscape-wizard-state.v1.json`."* On yes:
  1. Copy `scan` and `crate_metadata` directly to the new v2 state.
  2. Set `source.kind = "local"` and `source.project_root` from `cwd`.
  3. Carry over `datasets`, `bulk_groups`, `software`, `computations`, `branches` to a `legacy_v1_entities` top-level field. The wizard tells the user: *"I'll walk you through these again in Phase 4 (provenance) so they land in the new shape."*
  4. Set `phase = "metadata_captured"` (the form output is already there from the v1 file).
  5. Rename the v1 file to `.fairscape-wizard-state.v1.json`.
  
  On no: stop and route the user to `fairscape-rocrate-wizard-legacy`, which still operates on the v1 file.

## Phase router (resume table)

| `state.phase`         | Next skill                             |
|-----------------------|----------------------------------------|
| missing / init        | `remote-import`                        |
| `imported`            | `remote-schema-infer`                  |
| `schemas_done`        | `remote-ai-ready-enrich`               |
| `rai_done`            | `remote-provenance-tracking` (ask first) |
| `provenance_tracked`  | `fairscape-cli build datasheet` (auto, no prompt) → `agentic-rescore` (ask first) |
| `graded`              | `post-grade-improve` (ask first) — Phase 6 |
| `improved`            | done — offer to run more `post-grade-improve` leaves or re-grade |

(The `rai_done` phase label is internal — the enrichment phase is now called "AI-Ready enrichment" to the user, but the label stays so resume logic works on any state files already on disk. Don't change it.)

## What you must NOT do

- Don't run the local-project wizard's skills (`scan-project-folder`, `register-dataset`, etc.). They write a different state file and assume a different graph shape.
- Don't fetch the full data files. Phase 2 samples ~5 MB; the data stays remote.
- Don't mutate `ro-crate-metadata.json` outside of the documented phases and `fairscape-cli` calls. Phase 1's `fairscape-cli import` creates it; phase 2's `fairscape-cli schema infer --rocrate-path` appends a Schema entity and `remote-schema-infer` back-links it onto every group member; phase 3 merges AI-Ready fields into the root entry; phase 4 appends Software/Computation entities and runs `fairscape-cli augment link-inverses` to fill in inverse properties; nothing else touches it.
- Don't proceed to a later phase if an earlier phase failed and the user hasn't acknowledged. If `remote-import` fails, stop and surface the error.
- Don't ask the user for tokens. Public datasets only in v1.
