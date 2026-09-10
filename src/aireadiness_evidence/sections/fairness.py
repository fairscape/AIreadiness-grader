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
    GENERALIST_REPOS, LICENSE_NAMES, NON_SUSTAINABLE_HOSTS, SPECIALIST_REPOS,
    detect_pid, match_host, summarize_vocab_hits,
)


def _context_vocabs(context):
    """Namespace URIs declared in the crate's @context."""
    vocabs = []
    for ns in as_list(context):
        if isinstance(ns, str):
            vocabs.append(ns)
        elif isinstance(ns, dict):
            vocabs += [str(v) for v in ns.values() if isinstance(v, str)]
    return vocabs


def _vocab_evidence(context_vocabs, vocab_found):
    """The standard-vocabularies block shared by 0.b and 0.c: what the
    @context declares, and which published vocabularies the metadata
    actually references."""
    return [
        ev.listing("@context vocabularies of the crate metadata",
                   context_vocabs,
                   detail="schema.org / EVI here means the metadata follows "
                          "a standard vocabulary"),
        ev.flag("Standard vocabulary references found in metadata",
                bool(vocab_found),
                detail=", ".join(f"{k} ({n} refs)"
                                 for k, n in vocab_found.items())),
    ]

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
    # the rubric glossary excludes unmanaged storage (S3/GCS/Drive/Box/…)
    # from "sustainable repository"
    unsustainable = match_host(publisher, NON_SUSTAINABLE_HOSTS)
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
        "unsustainable_host": unsustainable[1] if unsustainable else None,
        "re3data": re3,
    }


def present_0a(facts):
    res = facts["resolution"]
    re3 = facts["re3data"]
    items = [
        ev.text("Identifier", facts["identifier"]),
        ev.sub(ev.flag("Persistent identifier present", bool(facts["pid_scheme"]),
                       detail=f"scheme: {facts['pid_scheme']}" if facts["pid_scheme"] else None)),
    ]
    if res:
        items.append(ev.sub(ev.flag("Identifier resolves", res.get("ok"),
                                    detail=res.get("note") or f"HTTP {res.get('status')}")))
    items += [
        ev.text("Publisher", facts["publisher"]),
        ev.sub(ev.flag("Publisher is a recognized sustainable repository",
                       bool(facts["known_repo"]), detail=facts["known_repo"])),
        ev.sub(ev.flag(
            "Publisher is unmanaged storage (excluded from 'sustainable "
            "repository' by the rubric glossary)",
            bool(facts["unsustainable_host"]),
            detail=facts["unsustainable_host"])),
        ev.sub(ev.flag(
            "Publisher found in re3data",
            bool(re3["matches"]) if re3.get("checked") else None,
            detail=(", ".join(re3["matches"][:3]) if re3.get("matches")
                    else re3.get("note") or f"query: {re3.get('query')}"),
        )),
    ]
    return items


def estimate_0a(facts):
    pid = facts["pid_scheme"]
    res = facts["resolution"]
    re3 = facts["re3data"]
    repo = facts["known_repo"] or \
        (re3["matches"][0] if re3.get("matches") else None)
    if facts["unsustainable_host"]:
        repo = None  # unmanaged storage never counts as sustainable
    if pid and res and res.get("checked") and res.get("ok") is False:
        return ev.estimate("1", f"PID present (scheme: {pid}) but it did not "
                                "resolve when checked")
    if pid and repo:
        return ev.estimate("2", f"PID present (scheme: {pid})",
                           "PID resolved" if res and res.get("ok") else None,
                           f"deposited in a sustainable repository ({repo})",
                           "that the PID resolves to a specific VERSION of "
                           "the dataset is not verified — confirm before "
                           "accepting (the gate requires a 2 here)")
    if pid or repo:
        return ev.estimate("1",
                           f"PID present (scheme: {pid})" if pid else None,
                           f"sustainable repository ({repo}) but no "
                           "resolvable PID" if repo else
                           "PID present but publisher is not a recognized "
                           "sustainable repository"
                           + (f" ({facts['unsustainable_host']} is excluded "
                              "by the glossary)"
                              if facts["unsustainable_host"] else ""))
    return ev.estimate("0", "no PID detected and publisher not a recognized "
                            "sustainable repository")


# --- 0.b Accessible --------------------------------------------------------


def extract_0b(ctx):
    return {
        "identifier": ctx.bundle.root.get("identifier"),
        "context": ctx.bundle.context,
        "vocab_hits": dict(ctx.bundle.stats.vocab_hits),
    }


def transform_0b(ctx, raw):
    fetched = ctx.net.fetch_pid_metadata(raw["identifier"])
    return {
        "identifier": raw["identifier"],
        "fetched": fetched,
        "vocabs": _context_vocabs(raw["context"]),
        "vocab_found": summarize_vocab_hits(raw["vocab_hits"]),
    }


def present_0b(facts):
    fetched = facts["fetched"]
    items = [
        ev.text("Identifier used for lookup", facts["identifier"]),
        ev.sub(ev.flag(
            "Descriptive metadata fetchable via PID alone",
            fetched.get("ok") if fetched.get("checked") else None,
            detail=fetched.get("format") or fetched.get("note"),
        )),
    ]
    if fetched.get("metadata"):
        meta = fetched["metadata"]
        keep = {k: meta[k] for k in
                ("@context", "@type", "name", "title", "publisher", "identifier",
                 "datePublished", "license", "author", "creator") if k in meta}
        items.append(ev.sub(ev.entity("Metadata returned by the PID resolver",
                                      keep,
                                      detail="truncated to descriptive fields")))
    return items + _vocab_evidence(facts["vocabs"], facts["vocab_found"])


def estimate_0b(facts):
    fetched = facts["fetched"]
    if not fetched.get("checked"):
        return None  # can't verify PID-independent availability offline
    if not fetched.get("ok"):
        return ev.estimate("0", "descriptive metadata could not be fetched "
                                "via the PID alone")
    if facts["vocab_found"]:
        return ev.estimate("2", "metadata fetchable via PID lookup",
                           "standard vocabularies referenced: "
                           + ", ".join(facts["vocab_found"]))
    return ev.estimate("1", "metadata fetchable via PID lookup but no "
                            "standard-vocabulary references found")


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
    parquet = sum(n for f, n in raw["formats"].items() if "parquet" in f.lower())
    return {
        "jsonld": bool(raw["context"]),
        "vocabs": _context_vocabs(raw["context"]),
        "vocab_found": summarize_vocab_hits(raw["vocab_hits"]),
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
        *_vocab_evidence(facts["vocabs"], facts["vocab_found"]),
        ev.listing("Subject terms on the root (about)", facts["about_ids"][:8]),
        ev.count("Machine-readable schema entities (EVI:Schema)",
                 facts["schema_total"]),
        ev.sub(ev.count("Datasets linked to a schema",
                        facts["dataset_with_schema_ref"])),
        ev.sub(ev.count("Parquet-format datasets (embedded schema)",
                        facts["parquet_count"])),
        ev.sub(ev.entity("Example schema entity", facts["schema_sample"])),
    ]


def estimate_0c(facts):
    if facts["jsonld"] and facts["vocab_found"]:
        return ev.estimate("2", "metadata is JSON-LD",
                           "standard vocabularies referenced: "
                           + ", ".join(facts["vocab_found"]))
    if facts["jsonld"] or facts["schema_total"]:
        return ev.estimate("1",
                           "metadata is JSON-LD but references no standard "
                           "vocabulary" if facts["jsonld"] else None,
                           f"{facts['schema_total']} machine-readable schema "
                           "entities" if facts["schema_total"] else None)
    return ev.estimate("0", "no formal specification and no machine-readable "
                            "schema found")


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
    vals = []
    for x in as_list(raw["license"]):
        if isinstance(x, dict):
            x = x.get("@id") or x.get("url") or ""
        if x:
            vals.append(str(x))
    license_value = " ".join(vals) or None
    # the 0.d 2-vs-1 split: the license must be programmatically linked in the
    # metadata (e.g. schema.org:license holding a resolvable IRI), not prose
    machine_readable = bool(license_value) and bool(
        re.match(r"https?://\S+$", license_value.strip()))
    known = match_host(license_value, LICENSE_NAMES)
    resolution = ctx.net.check_url(license_value) if machine_readable else None

    mentions = []
    for label in ("conditions", "usage_info", "prohibited"):
        for m in AI_ML_RE.finditer(str(raw[label] or "")):
            start, end = max(0, m.start() - 150), m.end() + 150
            mentions.append(f"[{label}] …{str(raw[label])[start:end]}…")
    return {
        "license_url": license_value,
        "license_machine_readable": machine_readable,
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
        ev.sub(ev.flag("License is machine-readable (an IRI linked in the "
                       "metadata, not prose)",
                       facts["license_machine_readable"])),
    ]
    if res:
        items.append(ev.sub(ev.flag("License link resolves",
                                    res.get("ok") if res.get("checked") else None,
                                    detail=res.get("note"))))
    items += [
        ev.text("Conditions of access / DUA terms", ev.clip(facts["conditions"])),
        ev.text("AI/ML language in license or use terms", _ai_ml_summary(facts),
                detail="the reviewer decides whether the terms permit or "
                       "prohibit AI/ML reuse" if facts["mentions"] else None),
    ]
    return items


def _ai_ml_summary(facts):
    """Plain-text summary of the AI/ML scan — not a pass/fail flag, since a
    mention can be a permission just as easily as a prohibition."""
    if not facts["mentions"]:
        return "No specific mention of AI/ML detected"
    sample = facts["mentions"][0]
    return f"AI/ML language detected. Sample: {sample}"


def estimate_0d(facts):
    if not facts["license_url"]:
        return ev.estimate("0", "no license, DUA, or public-domain "
                                "dedication linked in the metadata")
    if facts["mentions"]:
        return None  # AI/ML is mentioned — a human must read whether it
        # permits or prohibits
    if facts["license_machine_readable"]:
        return ev.estimate("2",
                           "machine-readable license linked in the metadata"
                           + (f" ({facts['license_name']})"
                              if facts["license_name"] else ""),
                           "no AI/ML prohibition language found in license or "
                           "use terms")
    return ev.estimate("1", "license/DUA present but not machine-readable "
                            "(prose value, not a linked IRI)",
                       "no AI/ML prohibition language found")
