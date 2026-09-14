"""grade.py — full RO-Crate AI-Ready scoring pipeline (packaged engine).

Builds the ``aireadiness_evidence`` presentation for an RO-Crate (the
docx-derived rubric text + typed evidence per criterion), then for each of the
28 criteria asks an LLM (via ``pydantic-ai``) to apply the criterion's 0/1/2
scoring rules to the evidence. Writes a per-criterion folder containing
``rubric.json`` + ``evidence.json`` + ``score.json``, plus a top-level
``aggregated_score.json`` grouped by criterion.

Evidence extraction, folder layout, and aggregation are shared with the
agentic (Claude-as-grader) path in ``aireadiness_grader.rubric_eval``; this
module only adds the LLM round-trips.

Run as a CLI (console script registered in pyproject.toml):

    fairscape-grade <crate-dir-or-metadata.json> <output-dir> \\
        --model anthropic:claude-opus-4-7 \\
        --api-key <key>

Or equivalently::

    python -m aireadiness_grader.grade <crate> <out-dir> --model ... --api-key ...

Or from inside a script::

    from aireadiness_grader import grade
    result = grade.grade_crate(
        "path/to/crate", "out/",
        model="anthropic:claude-opus-4-7", api_key=key,
    )
    print(result["percentage"])

``model`` is a pydantic-ai model string. Supported provider prefixes:
anthropic, openai, google-gla, google, groq. The ``api_key`` value is written to
the matching env var (ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY,
GROQ_API_KEY) before the Agent is instantiated.

The ``uvarc`` prefix routes to the UVA Research Computing GenAI
OpenAI-compatible endpoint (bypasses pydantic-ai; uses urllib + RubricScore
validation directly). Example::

    --model "uvarc:Kimi K2.5" --api-key $UVARC_GenAI_API

Calls are made sequentially — 28 round-trips per run. Failed criteria get
score: null and an error string in score.json; in the aggregate they contribute
0 to the subscore but their max still counts toward the criterion total.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Literal, Optional, Union

from pydantic import BaseModel, field_validator
from pydantic_ai import Agent

from aireadiness_grader.rubric_eval import (
    SCORE_LABELS,
    _aggregate,
    build_crate_presentation,
    dump_presentation,
)

__all__ = ["grade_crate", "RubricScore", "main"]


PROVIDER_ENV_MAP = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google-gla": "GOOGLE_API_KEY",
    "google": "GOOGLE_API_KEY",
    "groq": "GROQ_API_KEY",
}

UVARC_PROVIDER = "uvarc"
UVARC_BASE_URL = "https://open-webui.rc.virginia.edu/api/chat/completions"

BASE_SYSTEM_PROMPT = (
    "You are an RO-Crate AI-Readiness rubric grader. You score one criterion "
    "at a time using only the evidence payload provided. Follow the "
    "criterion's scoring rules literally — choose 0 (Absent), 1 (Partial), or "
    "2 (Substantive) based solely on the rule that matches the evidence. "
    "Score \"N/A\" only when every element of the criterion is inapplicable "
    "to this dataset; N/A is never permitted on a gating criterion. "
    "Quote @id refs, evidence labels, or short text fragments from the "
    "evidence to justify the score, and list specific gaps that would raise "
    "the score (empty if score is 2)."
)

PROMPT_TEMPLATE = """\
You are grading a single criterion for an RO-Crate AI-Readiness assessment.
Return a JSON object matching the output schema below — your reply will be
validated against the RubricScore model.

================ CRITERION ================
ID:      {rubric_id}
Name:    {name}
Section: {section_number} — {section_title}{gating_suffix}

PRACTICE (what the rubric asks data producers to do):
{practice}

REVIEW QUESTIONS:
{questions}

SCORING RULES (apply LITERALLY — pick the single rule that matches the evidence):
{rules}
{notes_block}
OUTPUT SCHEMA (your response must conform):
{output_schema_json}

================ EVIDENCE ================
The evidence below was deterministically extracted from the crate. Treat it as
the complete factual basis for your decision — do not invent or assume fields
that are not present. Each item has a `label`, a `kind`, and a `value`; the
`evidence_kinds` map explains the kinds. Items marked `sub: true` are derived
checks on the primary item above them. A bool value of null means the check
was inconclusive or not performed.

{evidence_json}

================ INSTRUCTIONS ================
1. Decide which scoring rule matches the evidence above.
2. Write a 1-3 sentence rationale that cites the specific rule that applied
   and points at the evidence items that decided it.
3. Populate `evidence` with direct @id refs, item labels, or short string
   fragments from the payload above (no fabrication — only strings actually
   present).
4. Populate `gaps` with what is missing that would raise the score; leave it
   empty if score == 2.
"""


class RubricScore(BaseModel):
    score: Union[int, Literal["N/A"]]
    rationale: str
    evidence: list[str] = []
    gaps: list[str] = []

    @field_validator("score")
    @classmethod
    def _score_in_range(cls, v):
        if isinstance(v, int) and not 0 <= v <= 2:
            raise ValueError("integer score must be 0, 1, or 2")
        return v


def _setup_api_key(model: str, api_key: str) -> None:
    if ":" not in model:
        raise ValueError(
            f"model must be 'provider:name' (got {model!r}); "
            f"e.g. anthropic:claude-opus-4-7"
        )
    prefix = model.split(":", 1)[0]
    if prefix == UVARC_PROVIDER:
        return
    env_var = PROVIDER_ENV_MAP.get(prefix)
    if env_var is None:
        supported = sorted([*PROVIDER_ENV_MAP, UVARC_PROVIDER])
        raise ValueError(
            f"unknown provider prefix {prefix!r}; supported: {supported}"
        )
    os.environ[env_var] = api_key


class UVARCClient:
    """pydantic-ai Agent stand-in for the UVA RC GenAI OpenAI-compatible endpoint.

    Exposes a ``run_sync(prompt)`` method that returns an object with ``.output``
    populated by a RubricScore instance, so the scoring loop can treat it
    identically to a real pydantic-ai Agent.
    """

    def __init__(self, model_name: str, api_key: str, system_prompt: str):
        self.model_name = model_name
        self.api_key = api_key
        self.system_prompt = system_prompt

    def run_sync(self, prompt: str):
        body = json.dumps(
            {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {
                        "role": "user",
                        "content": (
                            prompt
                            + "\n\nReturn ONLY a single JSON object matching the "
                            "output schema above. No markdown fences, no prose "
                            "before or after."
                        ),
                    },
                ],
                "temperature": 0,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            UVARC_BASE_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[: -3]
            content = content.strip()
            if content.startswith("json"):
                content = content[4:].lstrip()
        data = json.loads(content)
        return SimpleNamespace(output=RubricScore(**data))


def _build_prompt(rubric: dict, evidence: dict) -> str:
    questions = "\n".join(f"- {q}" for q in rubric["questions"])
    # rules come from the docx; a criterion may define no rule for a level
    # (0.d has only 0 and 2), so build the block from what exists.
    rules = "\n".join(
        f"  {level} — {SCORE_LABELS[level]}: {rubric['scoring'][level].strip()}"
        for level in ("0", "1", "2")
        if level in rubric["scoring"]
    )
    notes = []
    if rubric.get("notes"):
        notes.append(f"NOTES:\n{rubric['notes']}\n")
    if rubric.get("gating_note"):
        notes.append(f"GATING NOTE:\n{rubric['gating_note']}\n")
    if rubric.get("depends_on"):
        notes.append(
            "DEPENDENCY NOTE:\n"
            f"This criterion's final score is capped at criterion "
            f"{rubric['depends_on']}'s score during aggregation. Score this "
            "criterion on its own evidence; the cap is applied downstream.\n"
        )
    return PROMPT_TEMPLATE.format(
        rubric_id=rubric["id"],
        name=rubric["name"],
        section_number=rubric["section"]["number"],
        section_title=rubric["section"]["title"],
        gating_suffix=" (gating)" if rubric["section"]["gating"] else "",
        practice=rubric["practice"].strip(),
        questions=questions,
        rules=rules,
        notes_block=("\n" + "\n".join(notes)) if notes else "",
        output_schema_json=json.dumps(rubric["output_schema"], indent=2),
        evidence_json=json.dumps(evidence, indent=2, ensure_ascii=False, default=str),
    )


def _score_one(agent, prompt: str) -> tuple[Optional[RubricScore], Optional[str]]:
    try:
        result = agent.run_sync(prompt)
        return result.output, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _make_agent(model: str, api_key: str, system_prompt: str):
    prefix, _, model_name = model.partition(":")
    if prefix == UVARC_PROVIDER:
        return UVARCClient(model_name, api_key, system_prompt)
    return Agent(
        model,
        output_type=RubricScore,
        system_prompt=system_prompt,
        model_settings={"temperature": 0},
    )


def grade_crate(
    crate_path: Union[str, Path],
    output_dir: Union[str, Path],
    *,
    model: str,
    api_key: str,
    system_prompt_extra: str = "",
    network: bool = True,
    verbose: bool = True,
) -> dict:
    """Run the full 28-criterion LLM scoring pipeline against an RO-Crate.

    Args:
        crate_path: crate directory, or path to its ``ro-crate-metadata.json``.
        output_dir: directory to write per-criterion folders + aggregate into
            (created if missing).
        model: pydantic-ai model string, e.g. ``anthropic:claude-opus-4-7`` or
            ``uvarc:Kimi K2.5``.
        api_key: provider API key; set as the matching env var for this run.
        system_prompt_extra: optional text appended to the base system prompt.
        network: run the evidence pipeline's URL resolution / registry lookups
            (default True).
        verbose: emit progress to stderr (default True). The returned dict is
            the sole stdout-safe result regardless.

    Returns:
        The aggregate dict (``total_score``, ``max_score``, ``percentage``,
        ``counts``, ``criteria``, plus ``model`` and ``target``) — the same
        object written to ``<output_dir>/aggregated_score.json``.

    Raises:
        FileNotFoundError: if the crate is missing.
        ValueError: if ``model`` is malformed or its provider is unsupported.
    """
    crate_path = Path(crate_path)
    output_dir = Path(output_dir)

    if not crate_path.exists():
        raise FileNotFoundError(f"crate not found: {crate_path}")

    _setup_api_key(model, api_key)

    def log(msg: str) -> None:
        if verbose:
            print(msg, file=sys.stderr)

    log(f"[grade] loading {crate_path}")
    crate_dir, presentation = build_crate_presentation(
        crate_path, network=network, verbose=verbose,
    )
    inv = presentation["inventory"]
    log(
        f"[grade] loaded {inv['entities']} entities "
        f"({len(inv['sub_crates'])} sub-crates)"
    )

    rubrics_dir = output_dir / "rubrics"
    records = dump_presentation(presentation, rubrics_dir)

    system_prompt = BASE_SYSTEM_PROMPT
    if system_prompt_extra:
        system_prompt = f"{system_prompt}\n\n{system_prompt_extra}"

    log(f"[grade] using model {model}")
    agent = _make_agent(model, api_key, system_prompt)

    per_rubric: list[dict] = []

    for rec in records:
        prompt = _build_prompt(rec["rubric"], rec["evidence"])
        score, err = _score_one(agent, prompt)

        if score is not None:
            score_dict = score.model_dump()
        else:
            score_dict = {
                "score": None,
                "rationale": None,
                "evidence": [],
                "gaps": [],
                "error": err,
            }
        (rec["dir"] / "score.json").write_text(json.dumps(score_dict, indent=2) + "\n")

        per_rubric.append({**score_dict, "id": rec["id"], "slug": rec["slug"]})
        log(f"  [{rec['id']}] {rec['slug']}  -> score={score_dict.get('score')}")

    aggregate = _aggregate(per_rubric, model)
    aggregate["target"] = str(crate_dir)
    (output_dir / "aggregated_score.json").write_text(
        json.dumps(aggregate, indent=2, default=str) + "\n"
    )

    log(
        f"[grade] total {aggregate['total_score']}/{aggregate['max_score']} "
        f"points; overall score {aggregate['overall_score']}% "
        f"(unweighted domain average) — {aggregate['gating']['label']}  "
        f"(substantive={aggregate['counts']['substantive']}, "
        f"partial={aggregate['counts']['partial']}, "
        f"absent={aggregate['counts']['absent']}, "
        f"na={aggregate['counts']['na']}, "
        f"error={aggregate['counts']['error']})"
    )
    for failure in aggregate["gating"]["failures"]:
        log(f"[grade]   gate failure: {failure}")
    log(f"[grade] wrote {output_dir / 'aggregated_score.json'}")
    return aggregate


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="fairscape-grade",
        description="Score an RO-Crate against the 28 AI-Ready criteria using an LLM.",
    )
    ap.add_argument("crate_path", type=Path,
                    help="crate directory or its ro-crate-metadata.json")
    ap.add_argument("output_dir", type=Path, help="output directory (created if missing)")
    ap.add_argument(
        "--model",
        required=True,
        help="pydantic-ai model string, e.g. anthropic:claude-opus-4-7",
    )
    ap.add_argument(
        "--api-key",
        required=True,
        help="API key for the provider; set as the matching env var for this run",
    )
    ap.add_argument(
        "--system-prompt-extra",
        default="",
        help="optional extra text appended to the base system prompt",
    )
    ap.add_argument(
        "--no-network",
        action="store_true",
        help="skip the evidence pipeline's URL resolution / registry lookups",
    )
    args = ap.parse_args(argv)

    try:
        grade_crate(
            args.crate_path,
            args.output_dir,
            model=args.model,
            api_key=args.api_key,
            system_prompt_extra=args.system_prompt_extra,
            network=not args.no_network,
            verbose=True,
        )
    except (FileNotFoundError, ValueError) as e:
        raise SystemExit(str(e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
