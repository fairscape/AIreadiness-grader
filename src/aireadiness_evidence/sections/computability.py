"""Section 6 — Computability."""

from .. import evidence as ev
from ..crate import as_list, ids_of
from ..known import (
    KNOWN_VALIDATORS, STANDARD_NAMESPACES, classify_format, match_host,
    summarize_vocab_hits,
)

# --- 6.a Standardized ------------------------------------------------------


def extract_6a(ctx):
    return {
        "descriptor_conforms": ids_of(ctx.bundle.descriptor.get("conformsTo")),
        "root_conforms": ids_of(ctx.bundle.root.get("conformsTo")),
        "context": ctx.bundle.context,
        "schema_total": ctx.bundle.stats.schema_total,
        "vocab_hits": dict(ctx.bundle.stats.vocab_hits),
        "formats": dict(ctx.bundle.stats.formats),
    }


def transform_6a(ctx, raw):
    conforms = raw["descriptor_conforms"] + raw["root_conforms"]

    standards = {}
    ns_values = []
    for c in as_list(raw["context"]):
        if isinstance(c, str):
            ns_values.append(c)
        elif isinstance(c, dict):
            ns_values += [str(v) for v in c.values() if isinstance(v, str)]
    for value in conforms + ns_values:
        hit = match_host(value, STANDARD_NAMESPACES)
        if hit:
            standards[hit[1]] = value

    validators = {}
    for value in conforms + ns_values + (["json-schema.org"] if raw["schema_total"] else []):
        hit = match_host(value, KNOWN_VALIDATORS)
        if hit:
            validators[hit[1]] = value

    return {**raw, "conforms": conforms, "standards": standards,
            "validators": validators,
            "vocab_found": summarize_vocab_hits(raw["vocab_hits"])}


def present_6a(facts):
    return [
        ev.listing("conformsTo declarations (metadata descriptor + root)",
                   facts["conforms"]),
        ev.sub(ev.listing("Recognized standards in @context / conformsTo",
                          sorted(facts["standards"]))),
        ev.sub(ev.flag("Deterministic validator known for the declared standards",
                       bool(facts["validators"]),
                       detail="; ".join(sorted(facts["validators"])) or
                              "none matched — an unlisted validator may still exist")),
        ev.count("Machine-readable schema entities", facts["schema_total"]),
        ev.sub(ev.flag("Populated standard vocabulary bindings (2.c evidence — "
                       "without them 6.a caps at 1)",
                       bool(facts["vocab_found"]),
                       detail=", ".join(f"{k} ({n})" for k, n in
                                        facts["vocab_found"].items()))),
        ev.listing("File formats present",
                   [f"{f}: {n}" for f, n in
                    sorted(facts["formats"].items(), key=lambda kv: -kv[1])]),
    ]


def estimate_6a(facts):
    if facts["validators"] and facts["vocab_found"]:
        return ev.estimate("2", "declared standards: "
                           + ", ".join(sorted(facts["standards"]) or
                                       sorted(facts["validators"])),
                           "deterministic validator known: "
                           + "; ".join(sorted(facts["validators"])),
                           "populated vocabulary bindings present "
                           "(final score is capped at 2.c's score — rule "
                           "6.a ≤ 2.c)")
    if facts["validators"] or facts["standards"] or facts["conforms"] \
            or facts["schema_total"]:
        return ev.estimate("1",
                           "formal schema/standard declared, so structural "
                           "validation is possible",
                           "no populated standard-vocabulary bindings — "
                           "semantic conformance cannot be deterministically "
                           "validated (the 1-rule)"
                           if not facts["vocab_found"] else
                           "no deterministic validator matched (an unlisted "
                           "one may exist)")
    return ev.estimate("0", "no declared standard in conformsTo or @context")


# --- 6.b Computationally accessible ----------------------------------------


def extract_6b(ctx):
    stats = ctx.bundle.stats
    return {
        "hosts": dict(stats.hosts),
        "dataset_total": stats.dataset_total,
        "dataset_with_contenturl": stats.dataset_with_contenturl,
        "dataset_with_remote_url": stats.dataset_with_remote_url,
        "protocols": dict(stats.url_schemes),
        "conditions": ctx.bundle.root.get("conditionsOfAccess"),
        "publisher": ctx.bundle.root.get("publisher"),
    }


def transform_6b(ctx, raw):
    # resolve one sample link per http(s) host, capped at 3 hosts
    checks = []
    seen_hosts = set()
    for host in raw["hosts"]:
        scheme, name = host.split("://", 1)
        if scheme not in ("http", "https") or name in seen_hosts:
            continue
        seen_hosts.add(name)
        checks.append(ctx.net.check_url(f"{scheme}://{name}/"))
        if len(checks) >= 3:
            break
    return {**raw, "checks": checks}


def present_6b(facts):
    items = [
        ev.percent("Datasets with a distribution link (contentUrl)",
                   facts["dataset_with_contenturl"], facts["dataset_total"]),
        ev.sub(ev.percent("Datasets with a REMOTE distribution link "
                          "(http/ftp/s3-style)", facts["dataset_with_remote_url"],
                          facts["dataset_total"],
                          detail="the rest are file:// paths inside the crate "
                                 "or embargoed placeholders")),
        ev.sub(ev.listing("Protocols used by distribution links",
                          [f"{p}: {n} files" for p, n in
                           sorted(facts["protocols"].items(), key=lambda kv: -kv[1])],
                          detail="file = paths inside the crate; none = "
                                 "placeholder values such as 'Embargoed'")),
        ev.sub(ev.listing("Distribution hosts",
                          [f"{h}: {n} files" for h, n in
                           sorted(facts["hosts"].items(), key=lambda kv: -kv[1])[:10]])),
        ev.text("Access instructions (conditionsOfAccess)",
                ev.clip(facts["conditions"])),
    ]
    for chk in facts["checks"]:
        items.append(ev.sub(ev.flag(f"Sample host reachable: {chk['url']}",
                                    chk.get("ok") if chk.get("checked") else None,
                                    detail=chk.get("note"))))
    return items


def estimate_6b(facts):
    if facts["dataset_with_remote_url"] == 0:
        return ev.estimate("0", "no dataset has a remote distribution link — "
                                "no programmatic access mechanism visible")
    return None  # API/documentation quality (1 vs 2) is a human read


# --- 6.c Portable ----------------------------------------------------------


def extract_6c(ctx):
    stats = ctx.bundle.stats
    return {
        "formats": dict(stats.formats),
        "activity_total": stats.activity_total,
        "computation_total": stats.computation_total,
        "with_container": stats.activity_with_container,
        "computation": stats.sample("computation"),
        "software": stats.software_entities[:3],
    }


def transform_6c(ctx, raw):
    common, proprietary = {}, {}
    for fmt, n in raw["formats"].items():
        label = classify_format(fmt)
        if label:
            proprietary[f"{fmt} — {label}"] = n
        else:
            common[fmt] = n
    return {**raw, "common": common, "proprietary": proprietary}


def present_6c(facts):
    sw_descriptions = [
        f"{s.get('name')}: {ev.clip(s.get('description'), 220)}"
        for s in facts["software"]
    ]
    return [
        ev.count("Files in open/common formats", sum(facts["common"].values()),
                 detail=", ".join(f"{f}: {n}" for f, n in
                                  sorted(facts["common"].items(),
                                         key=lambda kv: -kv[1])[:8])),
        ev.count("Files in proprietary vendor formats",
                 sum(facts["proprietary"].values()),
                 detail=", ".join(f"{f}: {n}" for f, n in
                                  sorted(facts["proprietary"].items(),
                                         key=lambda kv: -kv[1])[:8]) or None),
        ev.percent("Computations with a container declared (usedContainer)",
                   facts["with_container"], facts["computation_total"]),
        ev.sub(ev.entity("Example computation (environment description)",
                         facts["computation"])),
        ev.sub(ev.listing("Software descriptions", sw_descriptions)),
    ]


def estimate_6c(facts):
    total = facts["computation_total"]
    if total and facts["with_container"] == total:
        return ev.estimate("2", f"all {total} computations declare a "
                                "container (machine-executable environment)")
    if facts["with_container"]:
        return ev.estimate("1", f"containers on {facts['with_container']} of "
                                f"{total} computations")
    return None  # data may need no specialized environment at all — human call


# --- 6.d Contextualized ----------------------------------------------------


def extract_6d(ctx):
    stats = ctx.bundle.stats
    root = ctx.bundle.root
    return {
        "split_count": stats.dataset_split_count,
        "split_names": stats.dataset_split_names,
        "sampling": root.get("d4d:samplingStrategies") or root.get("samplingStrategies"),
        "missing": root.get("rai:dataCollectionMissingData"),
        "preprocessing": root.get("rai:dataPreprocessingProtocol"),
        "example_dataset": stats.sample("example_dataset"),
        "schema_sample": stats.sample("schema"),
    }


def transform_6d(ctx, raw):
    return raw


def present_6d(facts):
    return [
        ev.flag("Datasets with split-like names (train/test/validation/holdout)",
                facts["split_count"] > 0,
                detail=f"{facts['split_count']} matches" if facts["split_count"] else None),
        ev.sub(ev.listing("Split-named datasets", facts["split_names"])),
        ev.text("Sampling strategies (d4d:samplingStrategies)",
                ev.clip(facts["sampling"])),
        ev.text("Withheld / missing information",
                ev.clip(facts["missing"])),
        ev.text("Preprocessing protocol (rai:dataPreprocessingProtocol)",
                ev.clip(facts["preprocessing"])),
        ev.entity("Example / synthetic dataset provided", facts["example_dataset"]),
        ev.sub(ev.entity("Structural example — schema entity (documents exact "
                         "record structure)", facts["schema_sample"])),
    ]


def estimate_6d(facts):
    context = [facts["split_count"], facts["sampling"], facts["missing"],
               facts["preprocessing"], facts["example_dataset"]]
    if not any(context):
        return ev.estimate("0", "no splits, withheld-information statement, "
                                "or example data anywhere in the metadata")
    if facts["example_dataset"] and (facts["missing"]
                                     or facts["preprocessing"]):
        return ev.estimate("2",
                           "machine-readable example dataset provided",
                           "withheld/preprocessing information described",
                           "splits N/A unless the dataset should define "
                           "them — reviewer to confirm")
    return ev.estimate("1", "some context present but incomplete "
                            "(example data or withheld-information "
                            "description missing)")
