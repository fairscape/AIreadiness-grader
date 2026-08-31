"""Extraction -> transformation -> presentation for the AI-readiness rubric.

Builds, from a FAIRSCAPE RO-Crate, the evidence document requested by
"Rubric for Human Review of AI-readiness Evaluation Criteria" v1.5: a
presentation JSON handed to an LLM grader, and a human-review HTML page
rendered from the same dict.
"""

from .pipeline import build_presentation
from .render import render_review

__all__ = ["build_presentation", "render_review"]
