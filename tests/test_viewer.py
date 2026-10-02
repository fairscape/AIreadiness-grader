"""fairscape-review-viewer: the committed docs/ copy must match the template
and rubric, and the embedded rubric must parse back out of the page."""

import json
import re
from pathlib import Path

from aireadiness_evidence.rubric import load_rubric
from aireadiness_evidence.viewer import REPO_COPY, render_viewer

REPO = Path(__file__).resolve().parents[1]


def test_repo_copy_is_current():
    committed = (REPO / REPO_COPY).read_text()
    assert committed == render_viewer(), (
        "docs/ai-ready-review-viewer.html is stale — run "
        "`fairscape-review-viewer -o docs/ai-ready-review-viewer.html`")


def test_embedded_rubric_round_trips():
    html = render_viewer()
    m = re.search(r'<script type="application/json" id="rubric-data">(.*?)</script>',
                  html, re.S)
    assert m
    rubric = json.loads(m.group(1))
    assert rubric["criteria"].keys() == load_rubric()["criteria"].keys()
    assert '<script type="application/json" id="viewer-data">{}</script>' in html
