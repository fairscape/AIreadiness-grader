"""Render the presentation dict to the human-review HTML."""

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES = Path(__file__).parent / "templates"


def render_review(presentation, link_base=""):
    """`link_base` is prefixed onto crate-relative hrefs (datasheets, evidence
    graphs) so the HTML can live outside the crate directory."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["tojson_pretty"] = lambda v: json.dumps(v, indent=2, ensure_ascii=False)

    def href(path):
        if not path or path.startswith(("http://", "https://")):
            return path
        return f"{link_base}/{path}" if link_base else path

    env.filters["href"] = href
    template = env.get_template("review.html.j2")
    return template.render(p=presentation)
