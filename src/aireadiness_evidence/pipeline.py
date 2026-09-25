"""Assemble the presentation document.

    bundle = CrateBundle.load(crate_dir)      # extraction (one pass)
    for criterion: extract -> transform -> present
    + rubric text from rubric_defs.yaml

The result is the presentation JSON: evidence for the LLM grader, and the
input to the human-review HTML template. No grading happens here — the only
scores attached are the per-criterion mechanical estimates (see the
``estimate_`` hooks), clearly labeled as such.
"""

import datetime
from dataclasses import dataclass

from . import evidence as ev
from .crate import CrateBundle, as_list
from .network import Network
from .source import FORMAT_LABELS
from .rubric import load_rubric, rubric_title
from .sections import CRITERIA


# Criteria that a single-document dialect cannot satisfy structurally. The
# estimate stays what the facts say (usually 0); the note tells the grader why.
_PROV_NOTE = ("{fmt} has no provenance vocabulary: samples, instruments, "
              "computations and derivation links cannot be expressed in this "
              "format, only described in prose (description, rai:dataCollection).")
FORMAT_NOTES = {
    "croissant": {
        "1.a": _PROV_NOTE,
        "1.b": _PROV_NOTE,
        "1.c": "{fmt} carries no software entities; code used to produce the "
               "data can only be cited in prose.",
        "5.d": "{fmt} is a single document without sub-crates or a hasPart "
               "graph; association is limited to distribution and recordSet "
               "links.",
    },
    "jsonld": {
        "1.a": _PROV_NOTE,
        "1.b": _PROV_NOTE,
        "1.c": "{fmt} carries no software entities; code used to produce the "
               "data can only be cited in prose.",
        "2.c": "{fmt} has no data-dictionary construct (Croissant recordSets "
               "or EVI schemas); variable-level structure can only be described "
               "in prose.",
        "5.d": "{fmt} is a single document without sub-crates or a hasPart "
               "graph.",
    },
}


@dataclass
class RunContext:
    bundle: CrateBundle
    net: Network


def build_presentation(crate_dir, network=True, progress=None, cache_dir=None):
    say = progress or (lambda msg: None)
    say(f"loading metadata: {crate_dir}")
    bundle = CrateBundle.load(crate_dir, progress=progress, cache_dir=cache_dir)
    fmt_label = FORMAT_LABELS.get(bundle.format, bundle.format)
    say(f"format: {fmt_label}")
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
        note = FORMAT_NOTES.get(bundle.format, {}).get(criterion.id)
        if note:
            items = [ev.text("Metadata format", fmt_label,
                             detail=note.format(fmt=fmt_label)), *items]
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
        if defs.get("gate_min"):
            entry["gate_min"] = defs["gate_min"]
        if defs.get("depends_on"):
            entry["depends_on"] = defs["depends_on"]
        if error:
            entry["error"] = error
        sections[int(criterion.id.split(".")[0])]["criteria"].append(entry)

    stats = bundle.stats
    return {
        "rubric": rubric_title(rubric),
        "rubric_version": rubric["version"],
        "glossary": rubric["glossary"],
        "methodology": rubric["methodology"],
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
            "source": bundle.source,
            "format": bundle.format,
            "format_label": fmt_label,
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
