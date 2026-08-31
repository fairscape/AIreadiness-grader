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
        "with_stats": stats.summary_stats_total,
        "located": list(stats.summary_stats_entities),
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
        ev.count("Entities carrying a summary-statistics link "
                 "(hasSummaryStatistics)", facts["with_stats"]),
        ev.sub(ev.listing(
            "Entities located",
            [f"{x['type']}: {x['name'] or x['@id']}"
             + (f" -> {x['target']}" if x["target"] else "")
             for x in facts["located"]])),
        ev.sub(ev.entity("Example summary-statistics reference",
                         facts["example"])),
        ev.text("Missing-data statement (rai:dataCollectionMissingData)",
                ev.clip(facts["missing_data"])),
        ev.listing("Tabular formats in the crate",
                   [f"{f}: {n}" for f, n in facts["tabular_formats"].items()],
                   detail="for non-tabular data, per-variable statistics are "
                          "N/A but missing-value consistency is still scored "
                          "in modality terms (absent channels, dropped leads, "
                          "corrupt slices, time-series gaps); the criterion "
                          "is N/A only if the data has no representable "
                          "missingness at all"),
    ]


def estimate_2b(facts):
    if facts["with_stats"] and facts["missing_data"]:
        return ev.estimate("2",
                           f"{facts['with_stats']} "
                           + ("entity carries" if facts["with_stats"] == 1
                              else "entities carry")
                           + " a summary-statistics link",
                           "missing-data statement present (its consistency "
                           "and domain-appropriateness are asserted, not "
                           "verified against the files)")
    # non-tabular data is no longer blanket-N/A (v1.5): missing-value
    # consistency is still scored in modality-appropriate terms, and whether
    # any representable missingness exists at all is a human call
    return None


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

# v1.5's added questions: demographic/cohort representativeness disclosure and
# clinical admission-pattern / site-selection bias. Prose signals only.
REPRESENTATIVENESS_RE = re.compile(
    r"demograph|represent\w*|socioeconomic|geograph|underserved|"
    r"minorit|ancestr|ethnicit|race\b|racial", re.I)
CASE_CONTROL_RE = re.compile(
    r"case[- ]?(vs\.?|versus)?[- ]?control|state[- ]vs\.?[- ]control|"
    r"healthy control|disease state|control (group|cohort|arm)", re.I)
CLINICAL_SITE_RE = re.compile(
    r"admission|site selection|recruit\w* site|referral pattern|"
    r"single[- ](center|centre|site)|multi[- ](center|centre|site)", re.I)


def extract_2d(ctx):
    root = ctx.bundle.root
    return {
        "biases": root.get("rai:dataBiases"),
        "missing": root.get("rai:dataCollectionMissingData"),
        "completeness": root.get("completeness"),
        "limitations": root.get("rai:dataLimitations"),
    }


def transform_2d(ctx, raw):
    blob = " ".join(str(v or "") for v in raw.values())
    return {
        **raw,
        "biases_substantive": ev.substantive(raw["biases"]),
        "missing_substantive": ev.substantive(raw["missing"]),
        "representativeness_hits": sorted(
            {m.group(0).lower()
             for m in REPRESENTATIVENESS_RE.finditer(blob)})[:8],
        "case_control_hits": sorted(
            {m.group(0).lower() for m in CASE_CONTROL_RE.finditer(blob)})[:6],
        "clinical_site_hits": sorted(
            {m.group(0).lower() for m in CLINICAL_SITE_RE.finditer(blob)})[:6],
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
        ev.text("Limitations (rai:dataLimitations)",
                ev.clip(facts["limitations"])),
        ev.flag("Demographic / cohort-representativeness language found",
                bool(facts["representativeness_hits"]),
                detail=", ".join(facts["representativeness_hits"]) or None),
        ev.sub(ev.flag("Case-vs-control language found",
                       bool(facts["case_control_hits"]),
                       detail=", ".join(facts["case_control_hits"]) or None)),
        ev.sub(ev.flag("Clinical admission-pattern / site-selection language "
                       "found",
                       bool(facts["clinical_site_hits"]),
                       detail=", ".join(facts["clinical_site_hits"]) or
                              "only applicable to clinically-derived data")),
    ]


def estimate_2d(facts):
    if not (facts["biases"] or facts["missing"] or facts["completeness"]
            or facts["limitations"]):
        return ev.estimate("0", "no bias, missingness, limitations, or "
                                "completeness description anywhere in the "
                                "metadata")
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
    qc_links = [u.rstrip(".,;") for u in
                URL_IN_TEXT_RE.findall(str(raw["collection"] or ""))]
    link_checks = [ctx.net.check_url(url) for url in qc_links[:3]]
    return {**raw, "qc_hits": qc_hits[:8], "qc_links": qc_links[:6],
            "link_checks": link_checks}


def present_2e(facts):
    items = [
        ev.text("Collection / QC description (rai:dataCollection)",
                ev.clip(facts["collection"])),
        ev.text("Missing-data handling", ev.clip(facts["missing"])),
        ev.sub(ev.flag("QC language found in metadata", bool(facts["qc_hits"]),
                       detail=", ".join(facts["qc_hits"]) or None)),
        ev.sub(ev.listing("Links to QC protocol/software found in the "
                          "collection description", facts["qc_links"],
                          detail=None if facts["qc_links"] else
                          "v1.5 asks for a link to the specific protocol or "
                          "software used")),
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
