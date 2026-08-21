"""Load the rubric text (rubric_defs.yaml) — the transcription of
"Rubric for Human Review of AI.docx" v1.0."""

from pathlib import Path

import yaml

DEFS_PATH = Path(__file__).parent / "rubric_defs.yaml"


def load_rubric():
    """Returns {"sections": [...], "criteria": {"0.a": {...}, ...}}."""
    doc = yaml.safe_load(DEFS_PATH.read_text())
    return {
        "sections": doc["sections"],
        "criteria": {c["id"]: c for c in doc["criteria"]},
    }
