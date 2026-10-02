"""Section 2 — Characterization (2.c Standards is gating)."""

import re

from .. import evidence as ev
from ..crate import as_list
from ..known import summarize_vocab_hits

# --- 2.a Semantics ---------------------------------------------------------


def _keyword_label(k):
    """Display text for a keyword: free text, or a DefinedTerm's name."""
    if isinstance(k, dict):
        return k.get("name") or k.get("termCode") or k.get("@id") or str(k)
    return str(k)


def extract_2a(ctx):
    root = ctx.bundle.root
    return {
        "description": root.get("description"),
        "keywords": [_keyword_label(k) for k in as_list(root.get("keywords"))],
        "terms": ctx.bundle.subject_terms,
    }


def transform_2a(ctx, raw):
    terms = raw["terms"]
    by_ontology = {}
    for t in terms:
        if t["ontology"]:
            by_ontology[t["ontology"]] = by_ontology.get(t["ontology"], 0) + 1
    return {
        "description": raw["description"],
        "description_len": len(str(raw["description"] or "")),
        "keywords": raw["keywords"],
        "terms": terms,
        "from_about": sum(t["source"] == "about" for t in terms),
        "from_keywords": sum(t["source"] == "keywords" for t in terms),
        "by_ontology": by_ontology,
    }


def present_2a(facts):
    return [
        ev.text("Dataset abstract/description", ev.clip(facts["description"]),
                detail=f"{facts['description_len']} chars"),
        ev.listing("Keywords", facts["keywords"][:25]),
        ev.flag("Controlled-vocabulary terms present", bool(facts["terms"]),
                detail=f"{len(facts['terms'])} subject terms "
                       f"({facts['from_about']} from root `about`, "
                       f"{facts['from_keywords']} from keywords); "
                       + (", ".join(f"{n} {o}" for o, n in
                                    facts["by_ontology"].items())
                          or "none on a recognised ontology host")),
        ev.sub(ev.listing("Controlled-vocabulary terms",
                          [f"{t['name'] or '(no label)'} — {t['@id']}"
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
        "croissant": ctx.bundle.format == "croissant",
        "field_total": stats.field_total,
        "field_bindings": dict(stats.field_bindings),
        "bound_field": stats.sample("bound_field"),
        "empty_recordsets": stats.empty_recordsets,
    }


def binding_vocabularies(raw):
    """{vocabulary: count} of standard-vocabulary bindings on data elements.

    A Croissant file binds data elements on its Fields (a semantic dataType or
    equivalentProperty), so only those count there. An ontology IRI anywhere
    else in a Croissant file (a MeSH keyword) describes the dataset, not a
    data element. For crates the document-wide ontology-host scan stands in."""
    if raw.get("croissant"):
        return dict(sorted(raw["field_bindings"].items(), key=lambda kv: -kv[1]))
    return summarize_vocab_hits(raw["vocab_hits"])


def transform_2c(ctx, raw):
    # image files (jpeg/png/tiff...) don't take a data dictionary, so they
    # are excluded from the schema-coverage denominator
    return {
        **raw,
        "vocab_found": binding_vocabularies(raw),
        "schema_denominator": max(0, raw["dataset_total"]
                                  - raw["dataset_image_total"]),
    }


def present_2c(facts):
    items = [
        ev.count("Machine-readable schema entities (EVI:Schema, JSON Schema "
                 "dialect, Croissant RecordSet with fields)",
                 facts["schema_total"],
                 detail=f"{facts['empty_recordsets']} RecordSet(s) without "
                        "fields not counted" if facts["empty_recordsets"]
                 else None),
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
                                        key=lambda kv: -kv[1]))
                + (f" — Croissant: counted on Fields with a semantic dataType "
                   f"or equivalentProperty, of {facts['field_total']} Fields"
                   if facts["croissant"] else "")),
        ev.listing("File formats present (format-class view)",
                   [f"{f}: {n}" for f, n in
                    sorted(facts["formats"].items(), key=lambda kv: -kv[1])]),
        ev.sub(ev.entity("Example schema entity", facts["schema_sample"])),
    ]
    if facts["bound_field"]:
        items.append(ev.sub(ev.entity("Example Field bound to a vocabulary term",
                                      facts["bound_field"])))
    return items


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
        "annotators": root.get("rai:annotatorDemographics"),
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
        ev.text("Annotator demographics (rai:annotatorDemographics)",
                ev.clip(facts["annotators"])),
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
            or facts["limitations"] or facts["annotators"]):
        return ev.estimate("0", "no bias, missingness, limitations, or "
                                "completeness description anywhere in the "
                                "metadata")
    return None  # text exists — whether it is substantive is a human read


# --- 2.e Data quality ------------------------------------------------------

QC_RE = re.compile(r"quality[- ]control|\bQC\b|quality assessment|outlier|"
                   r"filter(ed|ing)|inter[- ]?(rater|annotator)|"
                   r"(rater|annotator) agreement|kappa|krippendorff|"
                   r"quality (check|criteria)|deduplicat\w*|validat(ed|ion)",
                   re.I)

# Croissant RAI fields that describe how data was checked or processed.
QC_FIELDS = [
    ("rai:dataAnnotationAnalysis", "Annotation analysis"),
    ("rai:dataAnnotationProtocol", "Annotation protocol"),
    ("rai:dataPreprocessingProtocol", "Preprocessing protocol"),
    ("rai:dataManipulationProtocol", "Manipulation protocol"),
    ("rai:dataImputationProtocol", "Imputation protocol"),
]
URL_IN_TEXT_RE = re.compile(r"https?://[^\s\"\')\]]+")


def extract_2e(ctx):
    root = ctx.bundle.root
    return {
        "collection": root.get("rai:dataCollection"),
        "missing": root.get("rai:dataCollectionMissingData"),
        "description": root.get("description"),
        "qc_fields": {label: root.get(f) for f, label in QC_FIELDS
                      if root.get(f)},
    }


def transform_2e(ctx, raw):
    text_blob = " ".join(str(raw[k] or "") for k in
                         ("collection", "missing", "description"))
    text_blob += " " + " ".join(str(v) for v in raw["qc_fields"].values())
    qc_hits = sorted({m.group(0).lower() for m in QC_RE.finditer(text_blob)})
    qc_links = [u.rstrip(".,;") for u in URL_IN_TEXT_RE.findall(
        " ".join(str(v or "") for v in
                 [raw["collection"], *raw["qc_fields"].values()]))]
    link_checks = [ctx.net.check_url(url) for url in qc_links[:3]]
    return {**raw, "qc_hits": qc_hits[:8], "qc_links": qc_links[:6],
            "link_checks": link_checks}


def present_2e(facts):
    items = [
        ev.text("Collection / QC description (rai:dataCollection)",
                ev.clip(facts["collection"])),
        ev.text("Missing-data handling", ev.clip(facts["missing"])),
        *[ev.text(f"{label} (rai:)", ev.clip(v, 700))
          for label, v in facts["qc_fields"].items()],
        ev.sub(ev.flag("QC language found in metadata", bool(facts["qc_hits"]),
                       detail=", ".join(facts["qc_hits"]) or None)),
        ev.sub(ev.listing("Links to QC protocol/software found in the "
                          "collection / processing descriptions", facts["qc_links"],
                          detail=None if facts["qc_links"] else
                          "the rubric asks for a link to the specific protocol or "
                          "software used")),
    ]
    for chk in facts["link_checks"]:
        items.append(ev.sub(ev.flag(
            f"QC description link resolves: {chk['url']}",
            chk.get("ok") if chk.get("checked") else None,
            detail=chk.get("note"))))
    return items


def estimate_2e(facts):
    if not facts["collection"] and not facts["qc_fields"] \
            and not facts["qc_hits"]:
        return ev.estimate("0", "no QC description and no quality-control "
                                "language anywhere in the metadata")
    dead = [c["url"] for c in facts["link_checks"]
            if c.get("checked") and c.get("ok") is False]
    if dead:
        return ev.estimate("0", "QC description link does not resolve: "
                           + ", ".join(dead))
    return None  # QC adequacy (1 vs 2) is a domain-expert determination
