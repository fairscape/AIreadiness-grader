"""Section 1 — Provenance (gating)."""

import re

from .. import evidence as ev
from ..crate import as_list, ids_of
from ..known import CODE_HOSTS, SOFTWARE_ARCHIVE_HOSTS, match_host

# v1.5 1.b asks whether known provenance gaps / chain-of-custody breaks are
# explicitly disclosed. Prose signal only — a structured field doesn't exist.
GAP_DISCLOSURE_RE = re.compile(
    r"chain[- ]of[- ]custody|provenance gap|missing provenance|"
    r"collection circumstances|retrospective(ly)? (collected|acquired)|"
    r"original (collection|source) (records? )?(unavailable|unknown|lost)",
    re.I)

# --- 1.a Transparent -------------------------------------------------------


def extract_1a(ctx):
    stats = ctx.bundle.stats
    return {
        "dataset_total": stats.dataset_total,
        "dataset_with_prov": stats.dataset_with_prov,
        "sample_count": stats.type_counts.get("Sample", 0),
        "instrument_count": stats.type_counts.get("Instrument", 0),
        "experiment_count": stats.experiment_total,
        "input_dataset": (stats.sample("input_dataset")
                          or stats.sample("dataset_with_prov")),
        "biosample": stats.sample("biosample"),
        "instrument": stats.sample("instrument"),
    }


def transform_1a(ctx, raw):
    # ground truth for lab data = samples + instruments + generated datasets,
    # all as structured entities rather than prose
    raw["ground_truth_elements"] = {
        "samples": raw["sample_count"] > 0,
        "instruments": raw["instrument_count"] > 0,
        "experiments": raw["experiment_count"] > 0,
        "datasets_with_provenance": raw["dataset_with_prov"] > 0,
    }
    return raw


def present_1a(facts):
    gt = facts["ground_truth_elements"]
    return [
        ev.percent("Datasets carrying provenance links (EVI/PROV terms)",
                   facts["dataset_with_prov"], facts["dataset_total"]),
        ev.sub(ev.entity("Example dataset with provenance links",
                         facts["input_dataset"])),
        ev.listing("Ground-truth elements present as structured entities",
                   [f"{k}: {'yes' if v else 'no'}" for k, v in gt.items()]),
        ev.sub(ev.count("Sample entities", facts["sample_count"])),
        ev.sub(ev.count("Instrument entities", facts["instrument_count"])),
        ev.sub(ev.count("Experiment entities", facts["experiment_count"])),
        ev.sub(ev.entity("Example sample entity", facts["biosample"])),
        ev.sub(ev.entity("Example instrument entity", facts["instrument"])),
    ]


def estimate_1a(facts):
    if facts["dataset_with_prov"] == 0:
        return ev.estimate("0", "no dataset carries a machine-readable "
                                "provenance link")
    gt = facts["ground_truth_elements"]
    if all(gt.values()):
        return ev.estimate("2",
                           f"{facts['dataset_with_prov']} datasets carry "
                           "provenance links",
                           "all ground-truth elements present as structured "
                           "entities (samples, instruments, experiments)")
    missing = [k for k, v in gt.items() if not v]
    return ev.estimate("1",
                       f"{facts['dataset_with_prov']} datasets carry "
                       "provenance links",
                       "ground-truth elements missing: " + ", ".join(missing))


# --- 1.b Traceable ---------------------------------------------------------


def extract_1b(ctx):
    stats = ctx.bundle.stats
    root = ctx.bundle.root
    return {
        "activity_total": stats.activity_total,
        "computation_total": stats.computation_total,
        "experiment_total": stats.experiment_total,
        "with_io": stats.activity_with_io,
        "computation_with_software": stats.computation_with_software,
        "computation": stats.sample("computation") or stats.sample("experiment"),
        "graphs": ctx.bundle.evidence_graph_links(),
        "prose": " ".join(str(root.get(f) or "") for f in
                          ("description", "rai:dataCollection",
                           "rai:dataLimitations")),
    }


def transform_1b(ctx, raw):
    hits = sorted({m.group(0) for m in
                   GAP_DISCLOSURE_RE.finditer(raw.pop("prose"))})
    return {**raw, "gap_disclosures": hits[:6]}


def present_1b(facts):
    return [
        ev.count("Transformation steps (Computation + Experiment entities)",
                 facts["activity_total"],
                 detail=f"{facts['computation_total']} computations, "
                        f"{facts['experiment_total']} experiments"),
        ev.sub(ev.percent("Steps with inputs and outputs declared",
                          facts["with_io"], facts["activity_total"])),
        ev.sub(ev.percent("Computations linked to software",
                          facts["computation_with_software"],
                          facts["computation_total"])),
        ev.sub(ev.entity("Example transformation step", facts["computation"])),
        ev.flag("Provenance-gap / chain-of-custody disclosure language found "
                "in the prose metadata",
                bool(facts["gap_disclosures"]),
                detail=(", ".join(facts["gap_disclosures"])
                        if facts["gap_disclosures"] else
                        "a 2 requires records to be complete OR known gaps "
                        "explicitly disclosed — absence of this language is "
                        "fine if the record is complete")),
        ev.links("Evidence graphs (visual provenance per sub-crate)",
                 facts["graphs"]),
    ]


def estimate_1b(facts):
    if facts["activity_total"] == 0:
        return ev.estimate("0", "no transformation steps (Computation or "
                                "Experiment entities) in the crate")
    n, total = facts["computation_with_software"], facts["computation_total"]
    if total and n == total:
        return ev.estimate("2",
                           f"{facts['activity_total']} machine-readable "
                           "transformation steps",
                           "every computation links its software",
                           "completeness of the provenance record (or "
                           "disclosure of known gaps) is asserted, not "
                           "verified",
                           "final score is capped at 1.a's score (rule "
                           "1.b ≤ 1.a)")
    return ev.estimate("1",
                       f"{facts['activity_total']} machine-readable "
                       "transformation steps",
                       f"software linked on {n} of {total} computations — "
                       "consider 2 if the gap is negligible",
                       "final score is capped at 1.a's score (rule "
                       "1.b ≤ 1.a)")


# --- 1.c Interpretable -----------------------------------------------------


def extract_1c(ctx):
    return {"software": ctx.bundle.stats.software_entities,
            "software_total": ctx.bundle.stats.software_total}


def transform_1c(ctx, raw):
    archived, code_hosted, provider_site, unhosted = [], [], [], []
    for sw in raw["software"]:
        urls = ids_of(sw.get("contentUrl")) + ids_of(sw.get("codeRepository")) \
            + ids_of(sw.get("additionalDocumentation"))
        url_blob = " ".join(urls)
        entry = {"name": sw.get("name"), "@id": sw.get("@id"),
                 "urls": urls[:3]}
        if match_host(url_blob, SOFTWARE_ARCHIVE_HOSTS):
            archived.append(entry)
        elif match_host(url_blob, CODE_HOSTS):
            code_hosted.append(entry)
        elif any(u.startswith(("http://", "https://")) for u in urls):
            # v1.5: for proprietary commercial software, a URI to the
            # provider's website scores 2 — whether the software IS
            # proprietary commercial is the reviewer's call
            provider_site.append(entry)
        else:
            unhosted.append(entry)
    return {"software_total": raw["software_total"], "archived": archived,
            "code_hosted": code_hosted, "provider_site": provider_site,
            "unhosted": unhosted}


def present_1c(facts):
    def fmt(entries):
        return [f"{e['name']} — {', '.join(e['urls']) or 'no URL'}"
                for e in entries]

    return [
        ev.count("Software entities", facts["software_total"]),
        ev.sub(ev.count("Archived with a PID (Zenodo / Software Heritage / DOI / PyPI)",
                        len(facts["archived"]), of=facts["software_total"])),
        ev.sub(ev.count("Mutable code hosting only (GitHub and the like)",
                        len(facts["code_hosted"]), of=facts["software_total"])),
        ev.sub(ev.count("Provider/vendor website URI only",
                        len(facts["provider_site"]), of=facts["software_total"],
                        detail="counts as 2 only for proprietary commercial "
                               "software (reviewer's call)")),
        ev.sub(ev.count("No download/repository link", len(facts["unhosted"]),
                        of=facts["software_total"])),
        ev.sub(ev.listing("Archived software", fmt(facts["archived"]))),
        ev.sub(ev.listing("Code-hosted software", fmt(facts["code_hosted"]))),
        ev.sub(ev.listing("Provider-site software", fmt(facts["provider_site"]))),
        ev.sub(ev.listing("Software without links", fmt(facts["unhosted"]))),
    ]


def estimate_1c(facts):
    total = facts["software_total"]
    if total == 0:
        return ev.estimate("0", "no software entities in the crate")
    archived = len(facts["archived"])
    hosted = len(facts["code_hosted"])
    provider = len(facts["provider_site"])
    if archived == total:
        return ev.estimate("2", f"all {total} software entities point at an "
                                "archive with a PID")
    if provider and archived + provider == total:
        return None  # provider URIs score 2 only for proprietary commercial
        # software — a human must judge what the software is
    if archived or hosted or provider:
        return ev.estimate("1",
                           f"{archived} of {total} archived with a PID"
                           if archived else None,
                           f"{hosted} on mutable code hosting only"
                           if hosted else None,
                           f"{provider} with a provider/vendor URI only "
                           "(a 2 if proprietary commercial)"
                           if provider else None,
                           f"{len(facts['unhosted'])} with no link"
                           if facts["unhosted"] else None)
    return ev.estimate("0", "software entities exist but none has a "
                            "download or repository link")


# --- 1.d Key actors identified ---------------------------------------------


def extract_1d(ctx):
    root = ctx.bundle.root
    return {
        "authors": as_list(root.get("author")),
        "persons": ctx.bundle.persons,
        "pi": root.get("principalInvestigator"),
        "contact": root.get("contactEmail"),
        "orgs": ids_of(root.get("isPartOf")),
    }


def transform_1d(ctx, raw):
    with_pid, free_text = [], []
    person_ids = {p.get("@id") for p in raw["persons"]}
    for a in raw["authors"]:
        if isinstance(a, dict) and "@id" in a:
            aid = a["@id"]
            label = next((p.get("name", aid) for p in raw["persons"]
                          if p.get("@id") == aid), aid)
            if "orcid.org" in aid or aid in person_ids:
                with_pid.append(f"{label} ({aid})" if label != aid else aid)
            else:
                free_text.append(aid)
        elif isinstance(a, str):
            free_text.append(a)
    ror_orgs = [o for o in raw["orgs"] if "ror.org" in str(o)]
    return {
        "total": len(raw["authors"]),
        "with_pid": with_pid,
        "free_text": free_text,
        "pi": raw["pi"],
        "contact": raw["contact"],
        "orgs": raw["orgs"],
        "ror_orgs": ror_orgs,
    }


def present_1d(facts):
    return [
        ev.flag("Key actors identified", facts["total"] > 0),
        ev.sub(ev.percent("Authors identified with a PID (ORCID)",
                          len(facts["with_pid"]), facts["total"])),
        ev.sub(ev.listing("Authors with PIDs (first 10)", facts["with_pid"][:10])),
        ev.sub(ev.listing("Authors named in free text only",
                          facts["free_text"][:10])),
        ev.text("Principal investigator", facts["pi"]),
        ev.text("Contact", facts["contact"]),
        ev.listing("Organizations (root isPartOf)", facts["orgs"]),
        ev.sub(ev.flag("Organizations identified with ROR PIDs",
                       bool(facts["ror_orgs"]),
                       detail=", ".join(facts["ror_orgs"]) or None)),
    ]


def estimate_1d(facts):
    if facts["total"] == 0:
        return ev.estimate("0", "no authors on the root metadata")
    if not facts["free_text"]:
        return ev.estimate("2",
                           f"all {facts['total']} authors carry a PID (ORCID)",
                           "organizations carry ROR PIDs: "
                           + ", ".join(facts["ror_orgs"])
                           if facts["ror_orgs"] else None)
    return ev.estimate("1",
                       f"{len(facts['with_pid'])} of {facts['total']} authors "
                       "carry a PID",
                       f"{len(facts['free_text'])} named in free text only")
