"""fairscape-improve: build the AI-Ready improvements form for an RO-Crate.

    fairscape-improve /path/to/crate                 # -> <crate>/ai-ready-improve.html
    fairscape-improve /path/to/crate -o out.html
    fairscape-improve -o generic.html                # no crate embedded; load one in the page

The page is a single HTML file. It embeds the crate (if given), the rubric
text, the field catalogue and the fairscape_models JSON schemas, and runs
entirely offline: it re-scores the crate as you type (the mechanical rubric
estimates of the evidence pipeline) and lets you download the edited
ro-crate-metadata.json at any time.

If the crate directory holds ``grading/aggregated_score.json``
(fairscape-grade / agentic-rescore), that score is embedded and shown per
criterion as the prior grade.
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from aireadiness_evidence.rubric import load_rubric, rubric_title

from .fields import EFFORT_LABELS, OUT_OF_SCOPE_NOTES, catalogue
from .schemas import build_schemas

TEMPLATES = Path(__file__).parent / "templates"


def _embed_json(value):
    """JSON for a <script type=application/json> block: '</' must not appear."""
    return Markup(json.dumps(value, ensure_ascii=False).replace("</", "<\\/"))


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def resolve_crate(arg):
    """(crate_dir, metadata_path) from a directory or a metadata file."""
    p = Path(arg).resolve()
    if p.is_dir():
        meta = p / "ro-crate-metadata.json"
        if not meta.exists():
            raise FileNotFoundError(f"no ro-crate-metadata.json in {p}")
        return p, meta
    if p.is_file():
        return p.parent, p
    raise FileNotFoundError(str(p))


def find_prior_scores(crate_dir, grade=None):
    """Prior scores to embed: {"grade": {...}|None}."""
    out = {"grade": None}
    grade_path = Path(grade) if grade else crate_dir / "grading" / "aggregated_score.json"
    if grade_path.exists():
        out["grade"] = _read_json(grade_path)
    return out


def render_improve(crate=None, prior=None, crate_label=""):
    """Render the page. ``crate`` is the parsed ro-crate-metadata.json (or
    None for the generic page); ``prior`` is the dict from
    ``find_prior_scores`` (or None)."""
    rubric = load_rubric()
    sections = []
    for sec in rubric["sections"]:
        entry = dict(sec)
        entry["criteria"] = [
            {
                "id": c["id"],
                "name": c["name"],
                "practice": c["practice"].strip(),
                "questions": [q.strip() for q in c["questions"]],
                "scoring": {k: v.strip() for k, v in c["scoring"].items()},
                "notes": (c.get("notes") or "").strip(),
                "gate_min": c.get("gate_min"),
                "gating": bool(c.get("gating")),
                "depends_on": c.get("depends_on"),
                "out_of_scope": OUT_OF_SCOPE_NOTES.get(c["id"], ""),
            }
            for cid, c in rubric["criteria"].items()
            if int(cid.split(".")[0]) == sec["number"]
        ]
        sections.append(entry)

    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html", "j2"]),
    )
    env.filters["embed_json"] = _embed_json
    template = env.get_template("improve.html.j2")
    return template.render(
        rubric_title=rubric_title(rubric),
        generated=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        sections=sections,
        fields=catalogue(),
        effort_labels={str(k): v for k, v in EFFORT_LABELS.items()},
        schemas=build_schemas(),
        crate=crate,
        crate_label=crate_label,
        prior=prior or {"grade": None},
        core_js=(TEMPLATES / "improve.js").read_text(encoding="utf-8"),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="fairscape-improve", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("crate", nargs="?",
                        help="crate directory or ro-crate-metadata.json to embed (optional)")
    parser.add_argument("-o", "--out",
                        help="output HTML path (default: <crate>/ai-ready-improve.html, "
                             "or ./ai-ready-improve.html without a crate)")
    parser.add_argument("--grade", help="aggregated_score.json to show as the prior rubric grade")
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args(argv)

    crate = None
    prior = None
    label = ""
    if args.crate:
        crate_dir, meta = resolve_crate(args.crate)
        crate = _read_json(meta)
        prior = find_prior_scores(crate_dir, args.grade)
        label = str(meta)
        out = Path(args.out) if args.out else crate_dir / "ai-ready-improve.html"
    else:
        if args.grade:
            prior = find_prior_scores(Path("."), args.grade)
        out = Path(args.out) if args.out else Path("ai-ready-improve.html")

    html = render_improve(crate=crate, prior=prior, crate_label=label)
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    if not args.quiet:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
