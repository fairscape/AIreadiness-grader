"""fairscape-review-viewer: build the standalone AI-readiness review viewer.

    fairscape-review-viewer                      # -> ai-ready-review-viewer.html
    fairscape-review-viewer -o docs/ai-ready-review-viewer.html

The viewer is one static HTML page with the rubric text embedded. Open it in
a browser and drop in a scores JSON (current_scores.json, from the review
page's "Copy scores as JSON") and, optionally, the matching
ai-ready-evidence.json; it shows the scores, rubric and evidence side by side,
recomputes the section and overall totals, and can save edited scores or one
shareable HTML file. Nothing crate-specific is baked in, so a single copy in
the repo serves every review.
"""

import argparse
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from .render import TEMPLATES
from .rubric import load_rubric, rubric_title

REPO_COPY = Path("docs") / "ai-ready-review-viewer.html"


def render_viewer():
    rubric = load_rubric()
    env = Environment(loader=FileSystemLoader(TEMPLATES),
                      autoescape=select_autoescape(["html"]))
    # "<" escaped so rubric text can never close the <script> block
    rubric_json = json.dumps(rubric, ensure_ascii=False).replace("<", "\\u003c")
    return env.get_template("viewer.html.j2").render(
        rubric_title=rubric_title(rubric), rubric_json=Markup(rubric_json))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="fairscape-review-viewer", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--out", default="ai-ready-review-viewer.html",
                        help="output HTML path (default: ./ai-ready-review-viewer.html; "
                             f"the repo copy is {REPO_COPY})")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_viewer())
    print(out.resolve())


if __name__ == "__main__":
    main()
