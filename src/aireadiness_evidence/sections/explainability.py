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

URL_RE = re.compile(r"https?://[^\s\"\')\]]+|\bdoi:\s?\S+|\b10\.\d{4,9}/\S+")


def _normalize_link(link):
    """Turn a matched reference into a resolvable URL."""
    link = link.rstrip(".,;")
    if link.lower().startswith("doi:"):
        link = link[4:].strip()
    if link.startswith("10."):
        link = "https://doi.org/" + link
    return link

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
        ev.sub(ev.listing("Missing sections", facts["missing"])),
    ]
    for label, value in facts["populated"].items():
        items.append(ev.sub(ev.text(f"Section — {label}", ev.clip(value, 700))))
    return items


def estimate_3a(facts):
    has_ds = bool(facts["datasheets"])
    n = len(facts["populated"])
    if not has_ds and n == 0:
        return ev.estimate("0", "no human-readable datasheet and no "
                                "machine-readable datasheet fields")
    if has_ds and n >= 5:
        return ev.estimate("2",
                           "human-readable datasheet linked",
                           f"{n} of {len(DATASHEET_FIELDS)} machine-readable "
                           "sections populated (presence-checked only — "
                           "whether coverage is substantive is a human read)")
    return ev.estimate("1",
                       "human-readable datasheet linked" if has_ds
                       else "no human-readable datasheet",
                       f"{n} of {len(DATASHEET_FIELDS)} machine-readable "
                       "sections populated")


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
                          "href": _normalize_link(found[0]) if found else None})
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
        ev.sub(ev.flag("Both appropriate and inappropriate uses stated",
                       bool(facts["use_cases"]) and bool(
                           facts["limitations"] or facts["prohibited"]))),
        ev.count("Prior publications listed", len(facts["publications"])),
        ev.sub(ev.links("Prior publications", pubs)),
    ]


def estimate_3b(facts):
    appropriate = bool(facts["use_cases"])
    inappropriate = bool(facts["limitations"] or facts["prohibited"])
    pubs = len(facts["publications"])
    if appropriate and inappropriate:
        return ev.estimate("2",
                           "appropriate and inappropriate uses both stated",
                           f"{pubs} prior publications linked" if pubs else
                           "no prior publications listed — N/A if none "
                           "exist, downgrade if some do")
    if appropriate or inappropriate:
        return ev.estimate("1", "use cases stated only partially "
                                "(appropriate or inappropriate, not both)")
    return ev.estimate("0", "no use-case guidance in the metadata")


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
        ev.sub(ev.count("Embargoed datasets excluded from the denominator",
                        facts["embargoed"])),
        ev.sub(ev.entity("Example entity with a checksum", facts["example"])),
    ]


def estimate_3c(facts):
    if facts["denominator"] == 0:
        return None
    if facts["hashed"] >= facts["denominator"]:
        return ev.estimate("2", f"checksums on all {facts['denominator']} "
                                "datasets and software (embargoed excluded)")
    if facts["hashed"] > 0:
        return ev.estimate("1", f"checksums on {facts['hashed']} of "
                                f"{facts['denominator']} entities")
    return ev.estimate("0", "no checksums found")
