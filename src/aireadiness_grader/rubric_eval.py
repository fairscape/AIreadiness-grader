"""Evidence dump and score aggregation for agentic RO-Crate rubric scoring.

Both halves run on the ``aireadiness_evidence`` presentation pipeline — the
docx-derived rubric text in ``rubric_defs.yaml`` plus the typed evidence
extractors. The flow is split into two deterministic halves:

* ``extract-evidence`` — build the presentation for a crate and split it into
  per-criterion folders ``<out_dir>/<id>-<slug>/{rubric.json,evidence.json}``.
  Also writes the full ``ai-ready-presentation.json`` and a ``summary.json``.
  No LLM involved; deterministic apart from the optional network checks
  (``--no-network`` disables URL resolution / registry lookups).

* ``aggregate`` — scan ``<out_dir>/*/score.json`` (written by the wizard one
  criterion at a time, in-conversation) and emit
  ``<out_dir>/aggregated_score.json`` with totals grouped by criterion (id[0]).
  Matches the shape that ``aireadiness_grader.grade`` produces so downstream
  tooling can consume either.

The agentic scoring itself lives in the ``agentic-rescore`` SKILL — Claude
reads ``rubric.json`` + ``evidence.json`` and writes ``score.json`` per
criterion. The LLM-driven equivalent is ``aireadiness_grader.grade``.

CLI:
    python -m aireadiness_grader.rubric_eval extract-evidence <crate> <out_dir> [--no-network]
    python -m aireadiness_grader.rubric_eval aggregate <out_dir>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from aireadiness_evidence.pipeline import build_presentation
from aireadiness_evidence.rubric import dependency_rules, gate_specs

CRITERION_NAMES = {
    "0": "FAIRness",
    "1": "Provenance",
    "2": "Characterization",
    "3": "Pre-model Explainability",
    "4": "Ethics",
    "5": "Sustainability",
    "6": "Computability",
}

SCORE_LABELS = {"0": "Absent", "1": "Partial", "2": "Substantive"}

# v1.8 gating thresholds and score-dependency caps, read from rubric_defs.yaml
# ({criterion_id: min score} / {criterion_id: capping criterion_id}).
GATE_MINIMUMS = gate_specs()
DEPENDENCY_RULES = dependency_rules()

# Which domains carry a gate (any criterion with a gate_min).
GATED_DOMAINS = sorted({cid[0] for cid in GATE_MINIMUMS})

# The grader's response contract, shared by every criterion. Carried over from
# the retired rubrics/ai-ready YAMLs, where it was identical across all 28.
OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["score", "rationale", "evidence"],
    "additionalProperties": False,
    "properties": {
        "score": {
            "enum": [0, 1, 2, "N/A"],
            "description": (
                "0, 1, or 2 per the scoring rules. \"N/A\" only when every "
                "element of the criterion is inapplicable to this dataset; "
                "N/A is never permitted on a gating criterion."
            ),
        },
        "rationale": {
            "type": "string",
            "description": "1–3 sentences citing the rule that applied.",
        },
        "evidence": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Direct quotes or @id refs from the crate that justify the score.",
        },
        "gaps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific things missing that would raise the score. Empty if score is 2.",
        },
    },
}

# Legend embedded in each evidence.json so an isolated grader (a subagent that
# sees only the two files) can interpret the typed items without reading
# aireadiness_evidence.evidence's docstring.
EVIDENCE_KINDS = {
    "text": "free text (already truncated at build time)",
    "bool": "True / False / null; null means the check was inconclusive or not performed",
    "count": "integer, optionally 'n of total' via the `of` key",
    "percent": "0-100 float plus the n/total it came from",
    "link": "href (+ optional display text); crate-relative path or absolute URL",
    "links": "list of {href, text}",
    "list": "list of short strings",
    "entity": "a trimmed JSON-LD entity from the crate",
    "sub": "items marked `sub: true` are derived checks on the primary item above them",
}


def slugify(name: str) -> str:
    """Criterion name -> folder slug, e.g. 'Key actors identified' ->
    'key-actors-identified'. Matches the retired rubrics/ai-ready filenames."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def resolve_crate_dir(crate_path: Path) -> Path:
    """Accept either the crate directory or its ro-crate-metadata.json."""
    crate_path = Path(crate_path)
    crate_dir = crate_path.parent if crate_path.is_file() else crate_path
    if not (crate_dir / "ro-crate-metadata.json").exists():
        raise FileNotFoundError(f"no ro-crate-metadata.json in {crate_dir}")
    return crate_dir


def build_crate_presentation(crate_path, network: bool = True, verbose: bool = True):
    """Run the aireadiness_evidence pipeline. Returns (crate_dir, presentation)."""
    crate_dir = resolve_crate_dir(crate_path)
    progress = (lambda msg: print(f"[rubric_eval] {msg}", file=sys.stderr)) if verbose \
        else (lambda msg: None)
    presentation = build_presentation(crate_dir, network=network, progress=progress)
    return crate_dir, presentation


def dump_presentation(presentation: dict, out_dir: Path) -> list[dict]:
    """Split a presentation into per-criterion grading folders.

    Writes ``<out_dir>/ai-ready-presentation.json``, ``<out_dir>/summary.json``
    and, per criterion, ``<out_dir>/<id>-<slug>/rubric.json`` (the rubric text
    + output_schema) and ``evidence.json`` (the typed evidence items).

    Returns one record per criterion:
    ``{"id", "slug", "dir", "rubric", "evidence"}``.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "ai-ready-presentation.json").write_text(
        json.dumps(presentation, indent=2, ensure_ascii=False) + "\n"
    )

    records: list[dict] = []
    for section in presentation["sections"]:
        for criterion in section["criteria"]:
            slug = slugify(criterion["name"])
            slug_dir = out_dir / f"{criterion['id']}-{slug}"
            slug_dir.mkdir(parents=True, exist_ok=True)

            rubric = {
                "id": criterion["id"],
                "name": criterion["name"],
                "section": {
                    "number": section["number"],
                    "title": section["title"],
                    "gating": section["gating"],
                },
                "practice": criterion["practice"],
                "questions": criterion["questions"],
                "scoring": criterion["scoring"],
                "score_labels": SCORE_LABELS,
                "output_schema": OUTPUT_SCHEMA,
            }
            for opt in ("notes", "gating_note", "gate_min", "depends_on"):
                if criterion.get(opt):
                    rubric[opt] = criterion[opt]

            evidence = {
                "criterion": criterion["id"],
                "crate": presentation["crate"],
                "network_checks": presentation["network_checks"],
                "evidence_kinds": EVIDENCE_KINDS,
                "evidence": criterion["evidence"],
            }
            if criterion.get("error"):
                evidence["error"] = criterion["error"]

            (slug_dir / "rubric.json").write_text(
                json.dumps(rubric, indent=2, ensure_ascii=False) + "\n"
            )
            (slug_dir / "evidence.json").write_text(
                json.dumps(evidence, indent=2, ensure_ascii=False, default=str) + "\n"
            )
            records.append({
                "id": criterion["id"],
                "slug": slug,
                "dir": slug_dir,
                "rubric": rubric,
                "evidence": evidence,
            })

    summary = {
        "rubric": presentation["rubric"],
        "generated": presentation["generated"],
        "network_checks": presentation["network_checks"],
        "crate": presentation["crate"],
        "inventory": presentation["inventory"],
        "artifacts": presentation["artifacts"],
        "rubric_ids": [r["id"] for r in records],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n"
    )
    return records


def cmd_extract_evidence(crate_path: Path, out_dir: Path, network: bool = True) -> int:
    if not Path(crate_path).exists():
        raise SystemExit(f"crate not found: {crate_path}")

    try:
        crate_dir, presentation = build_crate_presentation(crate_path, network=network)
    except FileNotFoundError as e:
        raise SystemExit(str(e))

    records = dump_presentation(presentation, Path(out_dir))
    for rec in records:
        print(f"  [{rec['id']}] {rec['slug']}", file=sys.stderr)

    print(json.dumps({
        "out_dir": str(out_dir),
        "crate_dir": str(crate_dir),
        "rubrics": len(records),
        "network_checks": network,
    }))
    return 0


def cmd_aggregate(out_dir: Path, model: str = "agentic:claude-code") -> int:
    if not out_dir.exists():
        raise SystemExit(f"output dir not found: {out_dir}")

    per_rubric: list[dict] = []
    for slug_dir in sorted(out_dir.iterdir()):
        if not slug_dir.is_dir():
            continue
        score_path = slug_dir / "score.json"
        if not score_path.exists():
            continue
        rubric_json = slug_dir / "rubric.json"
        rubric_id, _, slug = slug_dir.name.partition("-")
        score = json.loads(score_path.read_text())
        per_rubric.append({
            "id": rubric_id,
            "slug": slug,
            "score": score.get("score"),
            "rationale": score.get("rationale"),
            "evidence": score.get("evidence", []),
            "gaps": score.get("gaps", []),
            "error": score.get("error"),
            "rubric_json_path": str(rubric_json) if rubric_json.exists() else None,
        })

    if not per_rubric:
        raise SystemExit(f"no score.json files found under {out_dir}")

    aggregate = _aggregate(per_rubric, model)
    aggregate_path = out_dir / "aggregated_score.json"
    aggregate_path.write_text(json.dumps(aggregate, indent=2, default=str) + "\n")

    counts = aggregate["counts"]
    gating = aggregate["gating"]
    print(
        f"[rubric_eval] {aggregate['total_score']}/{aggregate['max_score']} "
        f"points; overall score {aggregate['overall_score']}% "
        f"(unweighted domain average) — {gating['label']}  "
        f"(substantive={counts['substantive']}, partial={counts['partial']}, "
        f"absent={counts['absent']}, na={counts['na']}, "
        f"error={counts['error']})",
        file=sys.stderr,
    )
    for failure in gating["failures"]:
        print(f"[rubric_eval]   gate failure: {failure}", file=sys.stderr)
    print(json.dumps({
        "aggregated_score_path": str(aggregate_path),
        "total_score": aggregate["total_score"],
        "max_score": aggregate["max_score"],
        "percentage": aggregate["percentage"],
        "overall_score": aggregate["overall_score"],
        "gating": gating["label"],
        "rubrics_scored": len(per_rubric),
    }))
    return 0


def _apply_dependency_caps(per_rubric: list[dict]) -> None:
    """Enforce the v1.8 dependency rules in place (1.b ≤ 1.a, 6.a ≤ 2.c).
    A capped rubric keeps the grader's original score in ``uncapped_score``
    and gains a ``capped_by`` note."""
    by_id = {r["id"]: r for r in per_rubric}
    for cid, prereq_id in DEPENDENCY_RULES.items():
        r, prereq = by_id.get(cid), by_id.get(prereq_id)
        if not r or not prereq:
            continue
        s, ps = r.get("score"), prereq.get("score")
        if isinstance(s, int) and isinstance(ps, int) and s > ps:
            r["uncapped_score"] = s
            r["score"] = ps
            r["capped_by"] = (f"dependency rule {cid} ≤ {prereq_id}: "
                              f"score lowered from {s} to {ps}")


def _evaluate_gates(per_rubric: list[dict]) -> dict:
    """Apply the v1.8 gate thresholds. Returns {"pass": bool|None,
    "failures": [...], "unscored": [...]} — pass is None while any gated
    criterion is still unscored and nothing has failed yet."""
    by_id = {r["id"]: r for r in per_rubric}
    failures, unscored = [], []
    for cid, minimum in sorted(GATE_MINIMUMS.items()):
        r = by_id.get(cid)
        s = r.get("score") if r else None
        if s is None:
            unscored.append(cid)
        elif s == "N/A":
            failures.append(f"{cid} scored N/A (not permitted on a gating "
                            "criterion)")
        elif s < minimum:
            failures.append(f"{cid} scored {s} (gate requires "
                            f"{'2' if minimum == 2 else 'above 0'})")
    passed = False if failures else (None if unscored else True)
    return {"pass": passed, "failures": failures, "unscored": unscored}


def _aggregate(per_rubric: list[dict], model: str) -> dict:
    """v1.8 scoring methodology, shared with ``aireadiness_grader.grade``.

    Group by ``id[0]`` (domain). Domain score = points earned / max points over
    applicable (non-N/A) criteria. Overall score = unweighted average of domain
    percentages, reported alongside the raw point total. Gates (FAIRness 0.a=2
    + all >0, Provenance all >0, Standards 2.c >0, Ethics all >0) are evaluated
    independently; a failure marks the domain and the overall result
    "Gating FAIL" but the score is still computed. Dependency caps
    (1.b ≤ 1.a, 6.a ≤ 2.c) are applied before anything is summed."""
    _apply_dependency_caps(per_rubric)
    gate = _evaluate_gates(per_rubric)
    gate_failed_domains = {f.split(" ", 1)[0][0] for f in gate["failures"]}

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in per_rubric:
        groups[r["id"][0]].append(r)

    criteria = []
    total = 0
    max_total = 0
    counts = {"substantive": 0, "partial": 0, "absent": 0, "na": 0, "error": 0}

    for prefix in sorted(groups):
        rubrics = groups[prefix]
        c_score = sum(r["score"] for r in rubrics
                      if isinstance(r["score"], int))
        # N/A criteria leave the domain denominator (per the N/A policy);
        # errors still count against it so a crashed grader can't inflate %
        c_max = 2 * sum(1 for r in rubrics if r["score"] != "N/A")
        for r in rubrics:
            s = r["score"]
            if s == 2:
                counts["substantive"] += 1
            elif s == 1:
                counts["partial"] += 1
            elif s == 0:
                counts["absent"] += 1
            elif s == "N/A":
                counts["na"] += 1
            else:
                counts["error"] += 1
        entry = {
            "id": prefix,
            "name": CRITERION_NAMES.get(prefix, f"Unknown ({prefix})"),
            "score": c_score,
            "max": c_max,
            "percentage": round(100 * c_score / c_max, 1) if c_max else None,
            "rubrics": rubrics,
        }
        if prefix in GATED_DOMAINS:
            entry["gating"] = True
            entry["gate_failed"] = prefix in gate_failed_domains
        criteria.append(entry)
        total += c_score
        max_total += c_max

    percentage = round(100 * total / max_total, 1) if max_total else 0.0
    domain_pcts = [c["percentage"] for c in criteria
                   if c["percentage"] is not None]
    domain_average = (round(sum(domain_pcts) / len(domain_pcts), 1)
                      if domain_pcts else 0.0)
    return {
        "model": model,
        "total_score": total,
        "max_score": max_total,
        "percentage": percentage,
        # the v1.8 overall AI-readiness score: unweighted average of domain
        # percentages (differs from `percentage` since domains vary in size)
        "overall_score": domain_average,
        "gating": {
            "pass": gate["pass"],
            "label": "Gating FAIL" if gate["failures"] else (
                "gates passed" if gate["pass"] else "gates not fully scored"),
            "failures": gate["failures"],
            "unscored": gate["unscored"],
            "thresholds": dict(sorted(GATE_MINIMUMS.items())),
        },
        "counts": counts,
        "criteria": criteria,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Evidence dump + score aggregation for agentic RO-Crate grading.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    ee = sub.add_parser(
        "extract-evidence",
        help="Build the presentation and dump rubric.json + evidence.json per criterion.",
    )
    ee.add_argument("crate_path", type=Path,
                    help="crate directory or its ro-crate-metadata.json")
    ee.add_argument("out_dir", type=Path)
    ee.add_argument("--no-network", action="store_true",
                    help="skip URL resolution / registry lookups")

    ag = sub.add_parser("aggregate", help="Aggregate per-rubric score.json files into aggregated_score.json.")
    ag.add_argument("out_dir", type=Path)
    ag.add_argument("--model", default="agentic:claude-code")

    args = ap.parse_args(argv)

    if args.cmd == "extract-evidence":
        return cmd_extract_evidence(args.crate_path, args.out_dir,
                                    network=not args.no_network)
    if args.cmd == "aggregate":
        return cmd_aggregate(args.out_dir, args.model)
    return 2


if __name__ == "__main__":
    sys.exit(main())
