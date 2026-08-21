"""Section 2 — Characterization (2.c Standards is gating)."""

import re

from .. import evidence as ev
from ..crate import as_list
from ..known import summarize_vocab_hits

# --- 2.a Semantics ---------------------------------------------------------


def extract_2a(ctx):
    root = ctx.bundle.root
    return {
        "description": root.get("description"),
        "keywords": as_list(root.get("keywords")),
        "terms": ctx.bundle.defined_terms,
    }


def transform_2a(ctx, raw):
    terms = [{"@id": t.get("@id"), "name": t.get("name")} for t in raw["terms"]]
    mesh = [t for t in terms if "mesh" in str(t["@id"]).lower()]
    return {
        "description": raw["description"],
        "description_len": len(str(raw["description"] or "")),
        "keywords": raw["keywords"],
        "terms": terms,
        "mesh": mesh,
    }


def present_2a(facts):
    return [
        ev.text("Dataset abstract/description", ev.clip(facts["description"]),
                detail=f"{facts['description_len']} chars"),
        ev.listing("Keywords", facts["keywords"][:25]),
        ev.flag("Controlled-vocabulary terms present", bool(facts["terms"]),
                detail=f"{len(facts['mesh'])} MeSH terms of "
                       f"{len(facts['terms'])} DefinedTerms"),
        ev.sub(ev.listing("Controlled-vocabulary terms",
                          [f"{t['name']} — {t['@id']}"
                           for t in facts["terms"][:10]])),
    ]


def estimate_2a(facts):
    if not facts["description"]:
        return ev.estimate("0", "no abstract/description on the root")
    if facts["keywords"] and facts["terms"]:
        return ev.estimate("2",
                           f"abstract present ({facts['description_len']} "
                           "chars — length-checked only, not read for "
                           "substance)",
                           f"{len(facts['keywords'])} keywords",
                           f"{len(facts['terms'])} controlled-vocabulary "
                           "terms")
    if facts["keywords"]:
        return ev.estimate("1", "abstract and keywords present, no "
                                "controlled-vocabulary terms")
    return None  # abstract without keywords — rubric doesn't map cleanly


# --- 2.b Statistics --------------------------------------------------------


def extract_2b(ctx):
    stats = ctx.bundle.stats
    return {
        "with_stats": stats.dataset_with_summary_stats,
        "dataset_total": stats.dataset_total,
        "example": stats.sample("summary_stats"),
        "missing_data": ctx.bundle.root.get("rai:dataCollectionMissingData"),
        "formats": dict(stats.formats),
    }


def transform_2b(ctx, raw):
    tabular = {f: n for f, n in raw["formats"].items()
               if re.search(r"csv|tsv|parquet|xlsx?", f, re.I)}
    raw["tabular_formats"] = tabular
    return raw


def present_2b(facts):
    return [
        ev.percent("Datasets with summary statistics (hasSummaryStatistics)",
                   facts["with_stats"], facts["dataset_total"]),
        ev.sub(ev.entity("Example summary-statistics reference",
                         facts["example"])),
        ev.text("Missing-data statement (rai:dataCollectionMissingData)",
                ev.clip(facts["missing_data"])),
        ev.listing("Tabular formats in the crate (N/A applies only if none)",
                   [f"{f}: {n}" for f, n in facts["tabular_formats"].items()]),
    ]


def estimate_2b(facts):
    if not facts["tabular_formats"]:
        return ev.estimate("N/A", "no tabular formats in the crate — the "
                                  "rubric marks this criterion N/A for "
                                  "non-tabular data")
    if facts["with_stats"] and facts["missing_data"]:
        return ev.estimate("2",
                           f"{facts['with_stats']} datasets carry summary "
                           "statistics",
                           "missing-data statement present (its consistency "
                           "is asserted, not verified against the files)")
    return None  # missing-value encoding can't be verified from metadata


# --- 2.c Standards (gating) ------------------------------------------------


def extract_2c(ctx):
    stats = ctx.bundle.stats
    return {
        "schema_total": stats.schema_total,
        "dataset_with_schema_ref": stats.dataset_with_schema_ref,
        "dataset_total": stats.dataset_total,
        "dataset_image_total": stats.dataset_image_total,
        "schema_sample": stats.sample("schema"),
        "vocab_hits": dict(stats.vocab_hits),
        "formats": dict(stats.formats),
    }


def transform_2c(ctx, raw):
    # image files (jpeg/png/tiff...) don't take a data dictionary, so they
    # are excluded from the schema-coverage denominator
    return {
        **raw,
        "vocab_found": summarize_vocab_hits(raw["vocab_hits"]),
        "schema_denominator": max(0, raw["dataset_total"]
                                  - raw["dataset_image_total"]),
    }


def present_2c(facts):
    return [
        ev.count("Machine-readable schema entities (EVI:Schema, JSON Schema "
                 "dialect)", facts["schema_total"]),
        ev.sub(ev.percent("Non-image datasets linked to a schema",
                          facts["dataset_with_schema_ref"],
                          facts["schema_denominator"],
                          detail=f"{facts['dataset_image_total']:,} image "
                                 "datasets excluded — image files don't take "
                                 "a data dictionary; a schema covering a "
                                 "format class covers every file in that "
                                 "class")),
        ev.flag("Standard vocabulary bindings populated",
                bool(facts["vocab_found"]),
                detail=", ".join(f"{k} ({n})" for k, n in
                                 sorted(facts["vocab_found"].items(),
                                        key=lambda kv: -kv[1]))),
        ev.listing("File formats present (format-class view)",
                   [f"{f}: {n}" for f, n in
                    sorted(facts["formats"].items(), key=lambda kv: -kv[1])]),
        ev.sub(ev.entity("Example schema entity", facts["schema_sample"])),
    ]


def estimate_2c(facts):
    if facts["schema_total"] == 0:
        return ev.estimate("0", "no machine-readable schema entities")
    if facts["vocab_found"]:
        return ev.estimate("2",
                           f"{facts['schema_total']} schema entities",
                           "standard vocabulary bindings populated: "
                           + ", ".join(facts["vocab_found"]))
    return ev.estimate("1", f"{facts['schema_total']} schema entities but "
                            "no standard-vocabulary binding found")


# --- 2.d Potential Sources of Bias -----------------------------------------


def extract_2d(ctx):
    root = ctx.bundle.root
    return {
        "biases": root.get("rai:dataBiases"),
        "missing": root.get("rai:dataCollectionMissingData"),
        "completeness": root.get("completeness"),
    }


def transform_2d(ctx, raw):
    return {
        **raw,
        "biases_substantive": ev.substantive(raw["biases"]),
        "missing_substantive": ev.substantive(raw["missing"]),
    }


def present_2d(facts):
    return [
        ev.text("Bias description (rai:dataBiases)", ev.clip(facts["biases"])),
        ev.sub(ev.flag("Bias description present and substantive-length",
                       facts["biases_substantive"])),
        ev.text("Missing-data reasons (rai:dataCollectionMissingData)",
                ev.clip(facts["missing"])),
        ev.sub(ev.flag("Missingness explanation present and substantive-length",
                       facts["missing_substantive"])),
        ev.text("Completeness statement", ev.clip(facts["completeness"])),
    ]


def estimate_2d(facts):
    if not (facts["biases"] or facts["missing"] or facts["completeness"]):
        return ev.estimate("0", "no bias, missingness, or completeness "
                                "description anywhere in the metadata")
    return None  # text exists — whether it is substantive is a human read


# --- 2.e Data quality ------------------------------------------------------

QC_RE = re.compile(r"quality[- ]control|\bQC\b|quality assessment|outlier|"
                   r"filter(ed|ing)", re.I)
URL_IN_TEXT_RE = re.compile(r"https?://[^\s\"\')\]]+")


def extract_2e(ctx):
    root = ctx.bundle.root
    return {
        "collection": root.get("rai:dataCollection"),
        "missing": root.get("rai:dataCollectionMissingData"),
        "description": root.get("description"),
    }


def transform_2e(ctx, raw):
    text_blob = " ".join(str(raw[k] or "") for k in raw)
    qc_hits = sorted({m.group(0).lower() for m in QC_RE.finditer(text_blob)})
    link_checks = []
    for url in URL_IN_TEXT_RE.findall(str(raw["collection"] or ""))[:3]:
        link_checks.append(ctx.net.check_url(url.rstrip(".,;")))
    return {**raw, "qc_hits": qc_hits[:8], "link_checks": link_checks}


def present_2e(facts):
    items = [
        ev.text("Collection / QC description (rai:dataCollection)",
                ev.clip(facts["collection"])),
        ev.text("Missing-data handling", ev.clip(facts["missing"])),
        ev.sub(ev.flag("QC language found in metadata", bool(facts["qc_hits"]),
                       detail=", ".join(facts["qc_hits"]) or None)),
    ]
    for chk in facts["link_checks"]:
        items.append(ev.sub(ev.flag(
            f"QC description link resolves: {chk['url']}",
            chk.get("ok") if chk.get("checked") else None,
            detail=chk.get("note"))))
    return items


def estimate_2e(facts):
    if not facts["collection"] and not facts["qc_hits"]:
        return ev.estimate("0", "no QC description and no quality-control "
                                "language anywhere in the metadata")
    dead = [c["url"] for c in facts["link_checks"]
            if c.get("checked") and c.get("ok") is False]
    if dead:
        return ev.estimate("0", "QC description link does not resolve: "
                           + ", ".join(dead))
    return None  # QC adequacy (1 vs 2) is a domain-expert determination
