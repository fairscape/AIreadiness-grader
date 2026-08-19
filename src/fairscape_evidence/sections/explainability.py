"""Section 3 — Pre-model Explainability."""

import re

from .. import evidence as ev
from ..crate import as_list

# The seven datasheet-style machine-readable sections counted for 3.a.
DATASHEET_FIELDS = [
    ("rai:dataCollection", "Collection"),
    ("rai:dataUseCases", "Use cases"),
    ("rai:dataLimitations", "Limitations"),
    ("rai:dataBiases", "Biases"),
    ("rai:dataReleaseMaintenancePlan", "Release/maintenance plan"),
    ("license", "License"),
    ("conditionsOfAccess", "Conditions of access"),
]

URL_RE = re.compile(r"https?://[^\s\"\')\]]+|doi:\s?\S+|10\.\d{4,9}/\S+")

# --- 3.a Data documentation template ---------------------------------------


def extract_3a(ctx):
    root = ctx.bundle.root
    return {
        "datasheets": ctx.bundle.datasheets,
        "fields": {label: root.get(field) for field, label in DATASHEET_FIELDS},
    }


def transform_3a(ctx, raw):
    populated = {label: v for label, v in raw["fields"].items() if v}
    return {
        "datasheets": raw["datasheets"],
        "populated": populated,
        "missing": [label for label, v in raw["fields"].items() if not v],
    }


def present_3a(facts):
    items = [
        ev.links("Human-readable datasheet(s)",
                 [{"href": p, "text": p} for p in facts["datasheets"]]),
        ev.count("Machine-readable datasheet sections populated",
                 len(facts["populated"]), of=len(DATASHEET_FIELDS)),
        ev.listing("Missing sections", facts["missing"]),
    ]
    for label, value in facts["populated"].items():
        items.append(ev.text(f"Section — {label}", ev.clip(value, 700)))
    return items


# --- 3.b Fit for purpose ---------------------------------------------------


def extract_3b(ctx):
    root = ctx.bundle.root
    return {
        "use_cases": root.get("rai:dataUseCases"),
        "limitations": root.get("rai:dataLimitations"),
        "prohibited": root.get("prohibitedUses"),
        "usage_info": root.get("usageInfo"),
        "publications": as_list(root.get("associatedPublication")),
    }


def transform_3b(ctx, raw):
    pub_links = []
    for pub in raw["publications"]:
        found = URL_RE.findall(str(pub))
        pub_links.append({"text": ev.clip(pub, 220),
                          "href": found[0].rstrip(".,;") if found else None})
    return {**raw, "pub_links": pub_links}


def present_3b(facts):
    pubs = [{"href": p["href"] or "", "text": p["text"]}
            for p in facts["pub_links"]]
    return [
        ev.text("Appropriate use cases (rai:dataUseCases)",
                ev.clip(facts["use_cases"])),
        ev.text("Limitations / inappropriate uses (rai:dataLimitations)",
                ev.clip(facts["limitations"])),
        ev.text("Prohibited uses", ev.clip(facts["prohibited"])),
        ev.flag("Both appropriate and inappropriate uses stated",
                bool(facts["use_cases"]) and bool(
                    facts["limitations"] or facts["prohibited"])),
        ev.count("Prior publications listed", len(facts["publications"])),
        ev.links("Prior publications", pubs),
    ]


# --- 3.c Verifiable --------------------------------------------------------


def extract_3c(ctx):
    stats = ctx.bundle.stats
    return {
        "dataset_total": stats.dataset_total,
        "software_total": stats.software_total,
        "dataset_with_hash": stats.dataset_with_hash,
        "software_with_hash": stats.software_with_hash,
        "embargoed": stats.dataset_embargoed,
        "example": stats.sample("hashed_entity"),
    }


def transform_3c(ctx, raw):
    hashed = raw["dataset_with_hash"] + raw["software_with_hash"]
    denominator = max(0, raw["dataset_total"] + raw["software_total"]
                      - raw["embargoed"])
    return {**raw, "hashed": hashed, "denominator": denominator}


def present_3c(facts):
    return [
        ev.percent("Hash coverage (datasets + software, embargoed excluded)",
                   facts["hashed"], facts["denominator"]),
        ev.count("Embargoed datasets excluded from the denominator",
                 facts["embargoed"]),
        ev.entity("Example entity with a checksum", facts["example"]),
    ]
