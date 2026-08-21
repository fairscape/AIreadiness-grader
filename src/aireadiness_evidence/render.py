"""Render the presentation dict to the human-review HTML."""

import json
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

TEMPLATES = Path(__file__).parent / "templates"

# http(s) URLs plus doi:/bare-DOI references found inside prose values.
_LINK_RE = re.compile(r"https?://[^\s<>\"\)\]]+|\bdoi:10\.\d{4,9}/\S+"
                      r"|\b10\.\d{4,9}/[^\s<>\"\)\],;]+")


def linkify(value):
    """Escape `value` and wrap URLs / DOIs in anchor tags."""
    if value is None:
        return ""
    text = str(value)
    out, last = [], 0
    for m in _LINK_RE.finditer(text):
        token = m.group(0)
        stripped = token.rstrip(".,;:")
        href = stripped
        if stripped.startswith("doi:"):
            href = "https://doi.org/" + stripped[4:]
        elif stripped.startswith("10."):
            href = "https://doi.org/" + stripped
        out.append(escape(text[last:m.start()]))
        out.append(Markup('<a href="%s">%s</a>') % (href, stripped))
        out.append(escape(token[len(stripped):]))
        last = m.end()
    out.append(escape(text[last:]))
    return Markup("").join(out)


def render_review(presentation, link_base=""):
    """`link_base` is prefixed onto crate-relative hrefs (datasheets, evidence
    graphs) so the HTML can live outside the crate directory."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["tojson_pretty"] = lambda v: json.dumps(v, indent=2, ensure_ascii=False)
    env.filters["linkify"] = linkify

    def href(path):
        # prefix only crate-relative paths, never absolute URLs/identifiers
        if not path or "://" in path or path.startswith(("doi:", "10.", "ark:")):
            return path
        return f"{link_base}/{path}" if link_base else path

    env.filters["href"] = href
    template = env.get_template("review.html.j2")
    return template.render(p=presentation)
