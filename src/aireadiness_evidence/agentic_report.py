"""Agentic-review document: the evidence presentation plus a machine grader's
per-criterion score.

Input is a grading directory produced by
``aireadiness_wizard.rubric_eval extract-evidence`` in which each
``<id>-<slug>/`` folder has gained a ``score.json`` (score / rationale /
evidence / gaps) written by an isolated grading agent. This module merges the
two, rolls the scores up per section, and renders a read-only HTML report —
the pre-filled counterpart to the blank ``ai-ready-review.html`` that
``render.render_review`` produces for human reviewers.

CLI:
    python -m aireadiness_evidence.agentic_report <grading_dir> -o <out_dir>
        [--link-base ..] [--label "Claude Opus 5, isolated per-section agents"]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .render import linkify
from .rubric import dependency_rules, gate_specs

TEMPLATES = Path(__file__).parent / "templates"

SCORE_LABELS = {0: "Absent", 1: "Partial", 2: "Substantive", "N/A": "N/A"}

# v1.8 gate thresholds ({criterion_id: min score}) and dependency caps
# ({criterion_id: capping criterion_id}), read from rubric_defs.yaml.
GATE_MINIMUMS = gate_specs()
DEPENDENCY_RULES = dependency_rules()

# Radar geometry. One axis per section, first axis straight up. The box is
# wider than it is tall so the axis labels have room to sit outside the rings.
RADAR_W = 420
RADAR_H = 300
RADAR_CX = RADAR_W / 2
RADAR_CY = RADAR_H / 2
RADAR_R = 92
LABEL_GAP = 18


def load_scores(grading_dir: Path) -> dict[str, dict]:
    """Map criterion id -> the score.json written for it (absent ones skipped)."""
    scores: dict[str, dict] = {}
    for folder in sorted(Path(grading_dir).iterdir()):
        path = folder / "score.json"
        if folder.is_dir() and path.exists():
            scores[folder.name.partition("-")[0]] = json.loads(path.read_text())
    return scores


def radar_points(fractions: list[float], scale: float = 1.0) -> str:
    """`points` attribute for a polygon over the section axes."""
    n = len(fractions)
    out = []
    for i, frac in enumerate(fractions):
        angle = -math.pi / 2 + 2 * math.pi * i / n
        r = RADAR_R * frac * scale
        x = RADAR_CX + r * math.cos(angle)
        y = RADAR_CY + r * math.sin(angle)
        out.append(f"{x:.1f},{y:.1f}")
    return " ".join(out)


def radar_axis_label(index: int, count: int) -> dict:
    """Position and text-anchor for the label at the end of one axis."""
    angle = -math.pi / 2 + 2 * math.pi * index / count
    x = RADAR_CX + (RADAR_R + LABEL_GAP) * math.cos(angle)
    y = RADAR_CY + (RADAR_R + LABEL_GAP) * math.sin(angle)
    cos, sin = math.cos(angle), math.sin(angle)
    anchor = "middle" if abs(cos) < 0.3 else ("start" if cos > 0 else "end")
    # two-line label: lift it above the ring on the top half, drop it below on
    # the bottom half, so neither line crosses the polygon
    dy = -4 if sin < -0.2 else (12 if sin > 0.2 else 4)
    return {"x": round(x, 1), "y": round(y + dy, 1), "anchor": anchor}


def _capped_scores(scores: dict[str, dict]) -> dict[str, dict]:
    """Apply the v1.8 dependency rules (1.b ≤ 1.a, 6.a ≤ 2.c) to a copy of
    the score map. A capped verdict keeps the grader's original score in
    ``uncapped_score`` and gains a ``capped_by`` note."""
    out = {cid: dict(v) for cid, v in scores.items()}
    for cid, prereq_id in DEPENDENCY_RULES.items():
        v, prereq = out.get(cid), out.get(prereq_id)
        if not v or not prereq:
            continue
        s, ps = v.get("score"), prereq.get("score")
        if isinstance(s, int) and isinstance(ps, int) and s > ps:
            v["uncapped_score"] = s
            v["score"] = ps
            v["capped_by"] = (f"dependency rule {cid} ≤ {prereq_id}: the "
                              f"grader's {s} is capped at {prereq_id}'s {ps}")
    return out


def build_report(presentation: dict, scores: dict[str, dict],
                 grader_label: str = "") -> dict:
    """Merge presentation + scores into the dict the template renders.

    Implements the v1.8 scoring methodology: dependency caps, N/A excluded
    from the denominator, per-criterion gate thresholds rolled up to domain
    "Gating FAIL", and an overall score that is the unweighted average of the
    domain percentages."""
    scores = _capped_scores(scores)
    sections = []
    counts = {"substantive": 0, "partial": 0, "absent": 0, "na": 0,
              "unscored": 0}
    total = max_total = 0
    gate_failures = []
    gate_unscored = []

    for section in presentation["sections"]:
        criteria = []
        pts = 0
        section_max = 0
        graded = 0
        section_gate_failures = []
        for c in section["criteria"]:
            verdict = scores.get(c["id"])
            score = verdict.get("score") if verdict else None
            gate_min = c.get("gate_min") or GATE_MINIMUMS.get(c["id"])
            if score is None:
                counts["unscored"] += 1
                if gate_min:
                    gate_unscored.append(c["id"])
            elif score == "N/A":
                graded += 1
                counts["na"] += 1
                if gate_min:
                    section_gate_failures.append(
                        f"{c['id']} scored N/A (not permitted on a gating "
                        "criterion)")
            else:
                pts += score
                section_max += 2
                graded += 1
                counts[SCORE_LABELS[score].lower()] += 1
                if gate_min and score < gate_min:
                    section_gate_failures.append(
                        f"{c['id']} scored {score} (gate requires "
                        f"{'2' if gate_min == 2 else 'above 0'})")
            estimate = (c.get("estimate") or {}).get("score")
            # estimates are strings and may be "N/A" where the rule has no
            # mechanical form; only numeric ones are comparable to a score
            criteria.append({
                **c,
                "score": score,
                "label": SCORE_LABELS.get(score, "Not scored"),
                "gate_min": gate_min,
                "rationale": (verdict or {}).get("rationale", ""),
                "cited": (verdict or {}).get("evidence", []),
                "gaps": (verdict or {}).get("gaps", []),
                "uncapped_score": (verdict or {}).get("uncapped_score"),
                "capped_by": (verdict or {}).get("capped_by"),
                "estimate_score": estimate,
                # flag only a real disagreement; a criterion with no mechanical
                # estimate is a judgment call, not a mismatch
                "estimate_differs": (str(estimate) in {"0", "1", "2"}
                                     and isinstance(score, int)
                                     and int(estimate) != score),
            })
        total += pts
        max_total += section_max
        gate_failures += section_gate_failures
        sections.append({
            "number": section["number"],
            "title": section["title"],
            "gating": section["gating"] or any(
                c.get("gate_min") for c in criteria),
            "criteria": criteria,
            "points": pts,
            "max": section_max,
            "graded": graded,
            "percentage": round(100 * pts / section_max, 1) if section_max else 0.0,
            "gate_failures": section_gate_failures,
            "gate_failed": bool(section_gate_failures),
        })

    axes = [
        {"number": s["number"], "title": s["title"], "points": s["points"],
         "max": s["max"], "percentage": s["percentage"],
         **radar_axis_label(i, len(sections))}
        for i, s in enumerate(sections)
    ]
    gating = [s for s in sections if s["gating"]]
    scored_sections = [s for s in sections if s["max"]]
    overall_score = (round(sum(s["percentage"] for s in scored_sections)
                           / len(scored_sections), 1)
                     if scored_sections else 0.0)
    gate_pass = False if gate_failures else (None if gate_unscored else True)

    return {
        "rubric": presentation["rubric"],
        "generated": presentation["generated"],
        "network_checks": presentation["network_checks"],
        "crate": presentation["crate"],
        "inventory": presentation["inventory"],
        "artifacts": presentation["artifacts"],
        "grader": grader_label,
        "sections": sections,
        "total": {
            "points": total,
            "max": max_total,
            "percentage": round(100 * total / max_total, 1) if max_total else 0.0,
            # v1.8 overall AI-readiness score: unweighted average of the
            # domain percentages (N/A criteria excluded from denominators)
            "overall_score": overall_score,
            "gate_pass": gate_pass,
            "gate_label": "Gating FAIL" if gate_failures else (
                "gates passed" if gate_pass else "gates not fully scored"),
            "counts": counts,
        },
        "gating": [
            {"number": s["number"], "title": s["title"],
             "passed": not s["gate_failed"],
             "failures": s["gate_failures"],
             "points": s["points"], "max": s["max"]}
            for s in gating
        ],
        "gate_failures": gate_failures,
        "gate_unscored": gate_unscored,
        "radar": {
            "width": RADAR_W,
            "height": RADAR_H,
            "cx": RADAR_CX,
            "cy": RADAR_CY,
            "radius": RADAR_R,
            "axes": axes,
            "rings": [
                {"fraction": f, "points": radar_points([f] * len(sections))}
                for f in (0.25, 0.5, 0.75, 1.0)
            ],
            "spokes": radar_points([1.0] * len(sections)).split(" "),
            "polygon": radar_points([s["percentage"] / 100 for s in sections]),
            "vertices": [
                {"xy": xy, "section": s["number"], "points": s["points"],
                 "max": s["max"]}
                for xy, s in zip(
                    radar_points([s["percentage"] / 100 for s in sections]).split(" "),
                    sections,
                )
            ],
        },
        "worst": sorted(
            [c for s in sections for c in s["criteria"]
             if isinstance(c["score"], int) and c["score"] < 2],
            key=lambda c: (c["score"], c["id"]),
        ),
    }


def render_agentic(report: dict, link_base: str = "") -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["linkify"] = linkify
    env.filters["tojson_pretty"] = lambda v: json.dumps(v, indent=2, ensure_ascii=False)

    def href(path):
        if not path or "://" in path or path.startswith(("doi:", "10.", "ark:")):
            return path
        return f"{link_base}/{path}" if link_base else path

    env.filters["href"] = href
    return env.get_template("agentic_review.html.j2").render(r=report)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m aireadiness_evidence.agentic_report",
        description="Render an agentic AI-readiness review from a scored grading dir.",
    )
    ap.add_argument("grading_dir", type=Path,
                    help="dir holding ai-ready-presentation.json and <id>-<slug>/score.json")
    ap.add_argument("-o", "--out-dir", type=Path, required=True)
    ap.add_argument("--link-base", default="",
                    help="prefix for crate-relative hrefs (datasheets, evidence graphs)")
    ap.add_argument("--label", default="",
                    help="how the scores were produced, shown in the header")
    args = ap.parse_args(argv)

    presentation = json.loads(
        (args.grading_dir / "ai-ready-presentation.json").read_text())
    scores = load_scores(args.grading_dir)
    report = build_report(presentation, scores, grader_label=args.label)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "ai-ready-agentic-scores.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n")
    (args.out_dir / "ai-ready-agentic-review.html").write_text(
        render_agentic(report, link_base=args.link_base))

    print(json.dumps({
        "out_dir": str(args.out_dir),
        "scored": len(scores),
        "total": report["total"]["points"],
        "max": report["total"]["max"],
        "percentage": report["total"]["percentage"],
        "overall_score": report["total"]["overall_score"],
        "gating": report["total"]["gate_label"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
