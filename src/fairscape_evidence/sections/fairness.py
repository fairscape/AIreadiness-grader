"""Section 0 — FAIRness (gating).

Each criterion is an extract / transform / present trio:
  extract_*   pulls raw fields out of the crate bundle
  transform_* derives facts (pattern checks, registry lookups, URL resolution)
  present_*   builds the evidence items shown to the grader
"""

import re

from .. import evidence as ev
from ..crate import as_list
from ..known import (
    GENERALIST_REPOS, LICENSE_NAMES, ONTOLOGY_HOSTS, SPECIALIST_REPOS,
    detect_pid, match_host,
)

# --- 0.a Findable ----------------------------------------------------------


def extract_0a(ctx):
    root = ctx.bundle.root
    return {
        "identifier": root.get("identifier"),
        "at_id": root.get("@id"),
        "publisher": root.get("publisher"),
    }


def transform_0a(ctx, raw):
    identifier = raw["identifier"] or raw["at_id"]
    pid_scheme = detect_pid(raw["identifier"]) or detect_pid(raw["at_id"])
    resolution = ctx.net.resolve_pid(identifier) if pid_scheme else None

    publisher = raw["publisher"]
    repo = (match_host(publisher, SPECIALIST_REPOS)
            or match_host(publisher, GENERALIST_REPOS))
    query = None
    if isinstance(publisher, str):
        host = re.sub(r"^https?://", "", publisher).split("/")[0]
        query = host or publisher
    re3 = ctx.net.re3data_search(query)

    return {
        "identifier": identifier,
        "pid_scheme": pid_scheme,
        "resolution": resolution,
        "publisher": publisher,
        "known_repo": repo[1] if repo else None,
        "re3data": re3,
    }


def present_0a(facts):
    res = facts["resolution"]
    re3 = facts["re3data"]
    items = [
        ev.text("Identifier", facts["identifier"]),
        ev.flag("Persistent identifier present", bool(facts["pid_scheme"]),
                detail=f"scheme: {facts['pid_scheme']}" if facts["pid_scheme"] else None),
    ]
    if res:
        items.append(ev.flag("Identifier resolves", res.get("ok"),
                             detail=res.get("note") or f"HTTP {res.get('status')}"))
    items += [
        ev.text("Publisher", facts["publisher"]),
        ev.flag("Publisher is a recognized repository", bool(facts["known_repo"]),
                detail=facts["known_repo"]),
        ev.flag(
            "Publisher found in re3data",
            bool(re3["matches"]) if re3.get("checked") else None,
            detail=(", ".join(re3["matches"][:3]) if re3.get("matches")
                    else re3.get("note") or f"query: {re3.get('query')}"),
        ),
    ]
    return items


# --- 0.b Accessible --------------------------------------------------------


def extract_0b(ctx):
    return {
        "identifier": ctx.bundle.root.get("identifier"),
        "context": ctx.bundle.context,
    }


def transform_0b(ctx, raw):
    fetched = ctx.net.fetch_pid_metadata(raw["identifier"])
    vocabs = []
    for ns in as_list(raw["context"]) :
        if isinstance(ns, str):
            vocabs.append(ns)
        elif isinstance(ns, dict):
            vocabs += [str(v) for v in ns.values() if isinstance(v, str)]
    return {"identifier": raw["identifier"], "fetched": fetched, "vocabs": vocabs}


def present_0b(facts):
    fetched = facts["fetched"]
    items = [
        ev.text("Identifier used for lookup", facts["identifier"]),
        ev.flag(
            "Descriptive metadata fetchable via PID alone",
            fetched.get("ok") if fetched.get("checked") else None,
            detail=fetched.get("format") or fetched.get("note"),
        ),
    ]
    if fetched.get("metadata"):
        meta = fetched["metadata"]
        keep = {k: meta[k] for k in
                ("@context", "@type", "name", "title", "publisher", "identifier",
                 "datePublished", "license", "author", "creator") if k in meta}
        items.append(ev.entity("Metadata returned by the PID resolver", keep,
                               detail="truncated to descriptive fields"))
    items.append(ev.listing("@context vocabularies of the crate metadata",
                            facts["vocabs"],
                            detail="schema.org / EVI here means the metadata "
                                   "follows a standard vocabulary"))
    return items


# --- 0.c Interoperable -----------------------------------------------------


def extract_0c(ctx):
    stats = ctx.bundle.stats
    return {
        "context": ctx.bundle.context,
        "about_ids": [t.get("@id") for t in ctx.bundle.defined_terms],
        "vocab_hits": dict(stats.vocab_hits),
        "schema_total": stats.schema_total,
        "dataset_with_schema_ref": stats.dataset_with_schema_ref,
        "schema_sample": stats.sample("schema"),
        "formats": dict(stats.formats),
    }


def transform_0c(ctx, raw):
    vocab_found = {}
    for host, n in raw["vocab_hits"].items():
        vocab_found[ONTOLOGY_HOSTS.get(host, host)] = (
            vocab_found.get(ONTOLOGY_HOSTS.get(host, host), 0) + n)
    parquet = sum(n for f, n in raw["formats"].items() if "parquet" in f.lower())
    return {
        "jsonld": bool(raw["context"]),
        "vocab_found": vocab_found,
        "about_ids": raw["about_ids"],
        "schema_total": raw["schema_total"],
        "dataset_with_schema_ref": raw["dataset_with_schema_ref"],
        "parquet_count": parquet,
        "schema_sample": raw["schema_sample"],
    }


def present_0c(facts):
    return [
        ev.flag("Metadata is JSON-LD (formal interoperable specification)",
                facts["jsonld"]),
        ev.flag("Standard vocabularies referenced", bool(facts["vocab_found"]),
                detail=", ".join(f"{k} ({n} refs)"
                                 for k, n in sorted(facts["vocab_found"].items(),
                                                    key=lambda kv: -kv[1]))),
        ev.listing("Subject terms on the root (about)", facts["about_ids"][:8]),
        ev.count("Machine-readable schema entities (EVI:Schema)",
                 facts["schema_total"]),
        ev.count("Datasets linked to a schema", facts["dataset_with_schema_ref"]),
        ev.count("Parquet-format datasets (embedded schema)",
                 facts["parquet_count"]),
        ev.entity("Example schema entity", facts["schema_sample"]),
    ]


# --- 0.d Reusable ----------------------------------------------------------

AI_ML_RE = re.compile(
    r"(AI/ML|artificial intelligence|machine[- ]learning|\bAI\b|\bML\b)", re.I)


def extract_0d(ctx):
    root = ctx.bundle.root
    return {
        "license": root.get("license"),
        "conditions": root.get("conditionsOfAccess"),
        "usage_info": root.get("usageInfo"),
        "prohibited": root.get("prohibitedUses"),
    }


def transform_0d(ctx, raw):
    license_url = " ".join(str(x) for x in as_list(raw["license"])) or None
    known = match_host(license_url, LICENSE_NAMES)
    resolution = ctx.net.check_url(license_url) if license_url else None

    mentions = []
    for label in ("conditions", "usage_info", "prohibited"):
        for m in AI_ML_RE.finditer(str(raw[label] or "")):
            start, end = max(0, m.start() - 150), m.end() + 150
            mentions.append(f"[{label}] …{str(raw[label])[start:end]}…")
    return {
        "license_url": license_url,
        "license_name": known[1] if known else None,
        "resolution": resolution,
        "conditions": raw["conditions"],
        "mentions": mentions[:4],
    }


def present_0d(facts):
    res = facts["resolution"]
    items = [
        ev.link("License", facts["license_url"],
                display=facts["license_name"] or facts["license_url"]),
        ev.flag("License is a well-known open license",
                bool(facts["license_name"]), detail=facts["license_name"]),
    ]
    if res:
        items.append(ev.flag("License link resolves", res.get("ok") if res.get("checked") else None,
                             detail=res.get("note")))
    items += [
        ev.text("Conditions of access / DUA terms", ev.clip(facts["conditions"])),
        ev.flag("AI/ML explicitly mentioned in license or use terms",
                bool(facts["mentions"]),
                detail="context excerpts below" if facts["mentions"] else None),
    ]
    if facts["mentions"]:
        items.append(ev.listing("AI/ML mention excerpts (for the reviewer's call)",
                                facts["mentions"]))
    return items
