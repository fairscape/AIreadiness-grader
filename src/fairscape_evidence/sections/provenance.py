"""Section 1 — Provenance (gating)."""

from .. import evidence as ev
from ..crate import as_list, ids_of
from ..known import CODE_HOSTS, SOFTWARE_ARCHIVE_HOSTS, match_host

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
        ev.listing("Ground-truth elements present as structured entities",
                   [f"{k}: {'yes' if v else 'no'}" for k, v in gt.items()]),
        ev.count("Sample entities", facts["sample_count"]),
        ev.count("Instrument entities", facts["instrument_count"]),
        ev.count("Experiment entities", facts["experiment_count"]),
        ev.entity("Example dataset with provenance links",
                  facts["input_dataset"]),
        ev.entity("Example sample entity", facts["biosample"]),
        ev.entity("Example instrument entity", facts["instrument"]),
    ]


# --- 1.b Traceable ---------------------------------------------------------


def extract_1b(ctx):
    stats = ctx.bundle.stats
    return {
        "activity_total": stats.activity_total,
        "computation_total": stats.computation_total,
        "experiment_total": stats.experiment_total,
        "with_io": stats.activity_with_io,
        "with_software": stats.activity_with_software,
        "computation": stats.sample("computation") or stats.sample("experiment"),
        "graphs": ctx.bundle.evidence_graph_links(),
    }


def transform_1b(ctx, raw):
    return raw


def present_1b(facts):
    return [
        ev.count("Transformation steps (Computation + Experiment entities)",
                 facts["activity_total"],
                 detail=f"{facts['computation_total']} computations, "
                        f"{facts['experiment_total']} experiments"),
        ev.percent("Steps with inputs and outputs declared",
                   facts["with_io"], facts["activity_total"]),
        ev.percent("Steps linked to software",
                   facts["with_software"], facts["activity_total"],
                   detail="experiments link instruments/samples instead of "
                          "software, so judge software links against "
                          "computations"),
        ev.entity("Example transformation step", facts["computation"]),
        ev.links("Evidence graphs (visual provenance per sub-crate)",
                 facts["graphs"]),
    ]


# --- 1.c Interpretable -----------------------------------------------------


def extract_1c(ctx):
    return {"software": ctx.bundle.stats.software_entities,
            "software_total": ctx.bundle.stats.software_total}


def transform_1c(ctx, raw):
    archived, code_hosted, unhosted = [], [], []
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
        else:
            unhosted.append(entry)
    return {"software_total": raw["software_total"], "archived": archived,
            "code_hosted": code_hosted, "unhosted": unhosted}


def present_1c(facts):
    def fmt(entries):
        return [f"{e['name']} — {', '.join(e['urls']) or 'no URL'}"
                for e in entries]

    return [
        ev.count("Software entities", facts["software_total"]),
        ev.count("Archived with a PID (Zenodo / Software Heritage / DOI / PyPI)",
                 len(facts["archived"]), of=facts["software_total"]),
        ev.count("Mutable code hosting only (GitHub and the like)",
                 len(facts["code_hosted"]), of=facts["software_total"]),
        ev.count("No download/repository link", len(facts["unhosted"]),
                 of=facts["software_total"]),
        ev.listing("Archived software", fmt(facts["archived"])),
        ev.listing("Code-hosted software", fmt(facts["code_hosted"])),
        ev.listing("Software without links", fmt(facts["unhosted"])),
    ]


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
        ev.percent("Authors identified with a PID (ORCID)",
                   len(facts["with_pid"]), facts["total"]),
        ev.listing("Authors with PIDs (first 10)", facts["with_pid"][:10]),
        ev.listing("Authors named in free text only", facts["free_text"][:10]),
        ev.text("Principal investigator", facts["pi"]),
        ev.text("Contact", facts["contact"]),
        ev.listing("Organizations (root isPartOf)", facts["orgs"]),
        ev.flag("Organizations identified with ROR PIDs",
                bool(facts["ror_orgs"]),
                detail=", ".join(facts["ror_orgs"]) or None),
    ]
