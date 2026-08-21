"""Assemble the presentation document.

    bundle = CrateBundle.load(crate_dir)      # extraction (one pass)
    for criterion: extract -> transform -> present
    + rubric text from rubric_defs.yaml

The result is the presentation JSON: evidence for the LLM grader, and the
input to the human-review HTML template. No scoring happens here.
"""

import datetime
from dataclasses import dataclass

from .crate import CrateBundle, as_list
from .network import Network
from .rubric import load_rubric
from .sections import CRITERIA


@dataclass
class RunContext:
    bundle: CrateBundle
    net: Network


def build_presentation(crate_dir, network=True, progress=None):
    say = progress or (lambda msg: None)
    say(f"loading crate: {crate_dir}")
    bundle = CrateBundle.load(crate_dir, progress=progress)
    ctx = RunContext(bundle=bundle, net=Network(enabled=network))

    rubric = load_rubric()
    sections = []
    for sec in rubric["sections"]:
        sections.append({
            "number": sec["number"],
            "title": sec["title"],
            "gating": sec["gating"],
            "criteria": [],
        })

    for criterion in CRITERIA:
        defs = rubric["criteria"][criterion.id]
        say(f"criterion {criterion.id} {defs['name']}")
        try:
            items, estimate = criterion.run(ctx)
            error = None
        except Exception as err:
            items, estimate = [], None
            error = f"{type(err).__name__}: {err}"
        entry = {
            "id": criterion.id,
            "name": defs["name"],
            "gating": defs.get("gating", False),
            "practice": defs["practice"].strip(),
            "questions": [q.strip() for q in defs["questions"]],
            "scoring": {k: v.strip() for k, v in defs["scoring"].items()},
            "evidence": items,
            # mechanical application of the scoring rules to the extracted
            # facts; None where the criterion needs human judgment
            "estimate": estimate,
        }
        for opt in ("notes", "gating_note"):
            if defs.get(opt):
                entry[opt] = defs[opt].strip()
        if error:
            entry["error"] = error
        sections[int(criterion.id.split(".")[0])]["criteria"].append(entry)

    stats = bundle.stats
    return {
        "rubric": "Rubric for Human Review of AI-readiness Evaluation Criteria, "
                  "v1.0 (2026-08-14)",
        "generated": datetime.datetime.now(datetime.timezone.utc)
                     .strftime("%Y-%m-%d %H:%M UTC"),
        "network_checks": network,
        "crate": {
            "@id": bundle.root.get("@id"),
            "name": bundle.root.get("name"),
            "identifier": bundle.root.get("identifier"),
            "version": bundle.root.get("version"),
            "datePublished": bundle.root.get("datePublished"),
            "path": str(bundle.root_dir),
        },
        "inventory": {
            "entities": stats.entity_total,
            "by_type": dict(stats.type_counts),
            "sub_crates": [
                {"name": s.name, "@id": s.ark, "dir": s.rel_dir,
                 "entities": s.entity_count, "prov_graphs": s.prov_graphs,
                 "preview": s.preview}
                for s in bundle.subcrates
            ],
            "hasPart_count": len(as_list(bundle.root.get("hasPart"))),
        },
        "artifacts": {
            "datasheets": bundle.datasheets,
            "evidence_graphs": bundle.evidence_graph_links(),
        },
        "sections": sections,
    }
