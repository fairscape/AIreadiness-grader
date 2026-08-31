"""Load the rubric text (rubric_defs.yaml) — the transcription of
"Rubric for Human Review of AI-readiness Evaluation Criteria" v1.5."""

from pathlib import Path

import yaml

DEFS_PATH = Path(__file__).parent / "rubric_defs.yaml"


def load_rubric():
    """Returns {"version", "date", "glossary", "methodology",
    "sections": [...], "criteria": {"0.a": {...}, ...}}."""
    doc = yaml.safe_load(DEFS_PATH.read_text())
    return {
        "version": doc.get("version", ""),
        "date": doc.get("date", ""),
        "glossary": doc.get("glossary", {}),
        "methodology": doc.get("methodology", {}),
        "sections": doc["sections"],
        "criteria": {c["id"]: c for c in doc["criteria"]},
    }


def rubric_title(rubric=None):
    """The citable rubric name+version string used in reports."""
    rubric = rubric or load_rubric()
    return ("Rubric for Human Review of AI-readiness Evaluation Criteria, "
            f"v{rubric['version']} ({rubric['date']})")


def gate_specs(rubric=None):
    """Gating thresholds: {criterion_id: minimum score demanded by the gate}.
    v1.5 — FAIRness: 0.a = 2, others > 0; Provenance: all > 0;
    Standards: 2.c > 0; Ethics: all > 0."""
    rubric = rubric or load_rubric()
    return {cid: c["gate_min"] for cid, c in rubric["criteria"].items()
            if c.get("gate_min")}


def dependency_rules(rubric=None):
    """Score caps: {criterion_id: id of the criterion whose score caps it}.
    v1.5 — 1.b ≤ 1.a, 6.a ≤ 2.c."""
    rubric = rubric or load_rubric()
    return {cid: c["depends_on"] for cid, c in rubric["criteria"].items()
            if c.get("depends_on")}
