"""Render the presentation dict to the human-review HTML."""

import json
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape

TEMPLATES = Path(__file__).parent / "templates"

# http(s) URLs plus doi:/bare-DOI references found inside prose values.
_LINK_RE = re.compile(r"https?://[^\s<>\"\)\]]+|\bdoi:10\.\d{4,9}/\S+"
                      r"|\b10\.\d{4,9}/[^\s<>\"\)\],;]+")

# One-line "why this domain exists" copy for the review page. Indexed by
# section number so the template can look up domain_blurbs[s.number].
DOMAIN_BLURBS = [
    "Can someone find this dataset, reach it, read its metadata, and reuse it under a license?",
    "Do we know where the data came from, how it was transformed, which software was used, and who is responsible?",
    "Is the data described well enough — meaning, units, schemas, bias, quality — to train or evaluate a model?",
    "Can a downstream user inspect the files, judge whether they fit the intended use, and verify they have the bytes you shipped?",
    "Was the data acquired, managed, shared, and secured in a way that matches its sensitivity?",
    "Will the data still be findable and governed in a sustainable repository years from now, together with its related parts?",
    "Can software actually consume this data — valid formats, reachable files, portable environments, documented splits?",
]

DOMAIN_SHORT = ["FAIR", "Prov", "Char", "Expl", "Ethic", "Sust", "Comp"]

SCORE_LABELS = {
    "2": "Substantive",
    "1": "Partial",
    "0": "Absent",
    "N/A": "Not applicable",
}

SCORE_HINTS = {
    "2": "The practice is in place.",
    "1": "Something is there, but incomplete.",
    "0": "The required evidence is missing.",
    "N/A": "Every part of this criterion does not apply to this dataset.",
}

# Inventory tiles: show the types a reviewer actually reasons about first.
_TYPE_ORDER = [
    "Dataset", "Sample", "Experiment", "Computation", "Software",
    "Schema", "Instrument", "Person", "Organization", "BioChemEntity",
    "Container", "DefinedTerm", "CreativeWork",
]

# Labels where "true" is a problem (so False should look like a pass).
_NEGATIVE_LABEL = re.compile(
    r"unmanaged|excluded from|embargoed|missing value", re.I
)


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


def grouped_evidence(items):
    """Fold `sub: true` items under the primary item above them.

    The review page shows supporting checks collapsed so the reviewer
    first sees the facts, then the derived tests.
    """
    groups = []
    for item in items or []:
        if item.get("sub") and groups:
            groups[-1]["subs"].append(item)
        else:
            groups.append({"primary": item, "subs": []})
    return groups


def ordered_types(by_type):
    """Type counts with the reviewer-relevant types first."""
    by_type = by_type or {}
    seen = set()
    out = []
    for name in _TYPE_ORDER:
        if name in by_type:
            out.append((name, by_type[name]))
            seen.add(name)
    for name, n in sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0])):
        if name not in seen:
            out.append((name, n))
    return out


def bool_tone(item):
    """CSS tone for a boolean evidence chip: good / bad / na.

    A bare Yes/No coloring is misleading when the label is itself a
    negative ('unmanaged storage' = False is actually fine).
    """
    label = item.get("label") or ""
    negated = bool(_NEGATIVE_LABEL.search(label))
    value = item.get("value")
    if value is True:
        return "bad" if negated else "good"
    if value is False:
        return "good" if negated else "bad"
    return "na"


def render_review(presentation, link_base=""):
    """`link_base` is prefixed onto crate-relative hrefs (datasheets, evidence
    graphs) so the HTML can live outside the crate directory."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=True,
    )
    env.filters["tojson_pretty"] = lambda v: json.dumps(v, indent=2, ensure_ascii=False)
    env.filters["linkify"] = linkify
    env.filters["grouped"] = grouped_evidence
    env.filters["ordered_types"] = ordered_types
    env.filters["bool_tone"] = bool_tone

    def href(path):
        # prefix only crate-relative paths, never absolute URLs/identifiers
        if not path or "://" in path or path.startswith(("doi:", "10.", "ark:")):
            return path
        return f"{link_base}/{path}" if link_base else path

    env.filters["href"] = href

    n_criteria = sum(len(s["criteria"]) for s in presentation["sections"])
    n_estimates = sum(
        1 for s in presentation["sections"]
        for c in s["criteria"] if c.get("estimate")
    )
    n_gates = sum(
        1 for s in presentation["sections"]
        for c in s["criteria"] if c.get("gate_min")
    )

    template = env.get_template("review.html.j2")
    return template.render(
        p=presentation,
        score_labels=SCORE_LABELS,
        score_hints=SCORE_HINTS,
        domain_blurbs=DOMAIN_BLURBS,
        domain_short=DOMAIN_SHORT,
        n_criteria=n_criteria,
        n_estimates=n_estimates,
        n_gates=n_gates,
    )
