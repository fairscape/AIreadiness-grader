"""Section 5 — Sustainability."""

import re

from .. import evidence as ev
from ..crate import as_list
from ..known import GENERALIST_REPOS, SPECIALIST_REPOS, detect_pid, match_host

URL_RE = re.compile(r"https?://[^\s\"\')\]]+")

# --- 5.a Persistent --------------------------------------------------------


def extract_5a(ctx):
    stats = ctx.bundle.stats
    root = ctx.bundle.root
    return {
        "identifier": root.get("identifier"),
        "at_id": root.get("@id"),
        "publisher": root.get("publisher"),
        "hosts": dict(stats.hosts),
        "dataset_total": stats.dataset_total,
        "dataset_with_contenturl": stats.dataset_with_contenturl,
        "dataset_with_remote_url": stats.dataset_with_remote_url,
    }


def transform_5a(ctx, raw):
    pid_scheme = detect_pid(raw["identifier"]) or detect_pid(raw["at_id"])
    archives = {}
    for target in [raw["publisher"], *raw["hosts"]]:
        hit = (match_host(str(target), SPECIALIST_REPOS)
               or match_host(str(target), GENERALIST_REPOS))
        if hit:
            archives[hit[1]] = archives.get(hit[1], 0) + 1
    return {**raw, "pid_scheme": pid_scheme, "archives": sorted(archives)}


def present_5a(facts):
    return [
        ev.text("Identifier", facts["identifier"]),
        ev.sub(ev.flag("Identifier is a PID", bool(facts["pid_scheme"]),
                       detail=f"scheme: {facts['pid_scheme']}" if facts["pid_scheme"] else None)),
        ev.listing("Recognized archives detected (publisher + content hosts)",
                   facts["archives"]),
        ev.percent("Datasets with a contentUrl (data parked somewhere)",
                   facts["dataset_with_contenturl"], facts["dataset_total"],
                   detail=f"{facts['dataset_with_remote_url']:,} of these are "
                          "remote archive links; the rest live inside the "
                          "crate deposit"),
    ]


def estimate_5a(facts):
    pid = facts["pid_scheme"]
    if pid and facts["archives"]:
        return ev.estimate("2", f"PID present (scheme: {pid})",
                           "recognized archive(s): "
                           + ", ".join(facts["archives"]))
    if pid or facts["archives"] or facts["dataset_with_contenturl"]:
        return ev.estimate("1",
                           f"PID present (scheme: {pid})" if pid else
                           "no PID on the deposit",
                           "recognized archives: "
                           + ", ".join(facts["archives"])
                           if facts["archives"] else
                           f"{facts['dataset_with_contenturl']} datasets "
                           "have a contentUrl but no recognized archive "
                           "detected")
    return ev.estimate("0", "no PID, no recognized archive, and no dataset "
                            "has a contentUrl")


# --- 5.b Domain-appropriate ------------------------------------------------


def extract_5b(ctx):
    stats = ctx.bundle.stats
    root = ctx.bundle.root
    return {
        "hosts": dict(stats.hosts),
        "publisher": root.get("publisher"),
        "keywords": as_list(root.get("keywords")),
        "collection_type": as_list(root.get("rai:dataCollectionType")),
        "dataset_total": stats.dataset_total,
    }


def transform_5b(ctx, raw):
    specialist, generalist, unrecognized = {}, {}, {}
    in_recognized = 0
    for host, n in raw["hosts"].items():
        if match_host(host, SPECIALIST_REPOS):
            specialist[f"{host} — {match_host(host, SPECIALIST_REPOS)[1]}"] = n
            in_recognized += n
        elif match_host(host, GENERALIST_REPOS):
            generalist[f"{host} — {match_host(host, GENERALIST_REPOS)[1]}"] = n
            in_recognized += n
        else:
            unrecognized[host] = n
    pub = match_host(str(raw["publisher"]), {**SPECIALIST_REPOS, **GENERALIST_REPOS})
    total_urls = sum(raw["hosts"].values())
    return {**raw, "specialist": specialist, "generalist": generalist,
            "unrecognized": unrecognized, "in_recognized": in_recognized,
            "total_urls": total_urls, "publisher_repo": pub[1] if pub else None}


def present_5b(facts):
    def fmt(d):
        return [f"{k}: {n} files" for k, n in
                sorted(d.items(), key=lambda kv: -kv[1])[:10]]

    return [
        ev.text("Publisher repository", str(facts["publisher"]),
                detail=facts["publisher_repo"]),
        ev.listing("Specialist (domain) hosts", fmt(facts["specialist"])),
        ev.sub(ev.listing("Generalist repository hosts", fmt(facts["generalist"]))),
        ev.sub(ev.listing("Unrecognized hosts", fmt(facts["unrecognized"]))),
        ev.sub(ev.percent("Dataset files on recognized repository hosts",
                          facts["in_recognized"], facts["total_urls"])),
        ev.listing("Domain hint — collection types", facts["collection_type"]),
        ev.sub(ev.listing("Domain hint — keywords", facts["keywords"][:15])),
    ]


def estimate_5b(facts):
    if facts["specialist"]:
        return ev.estimate("2", "data on specialist (domain) hosts: "
                           + ", ".join(list(facts["specialist"])[:3]))
    if facts["generalist"] or facts["publisher_repo"]:
        return None  # generalist only — whether a specialist repository
        # exists for this domain is a human/domain call
    return ev.estimate("0", "no recognized repository host detected")


# --- 5.c Well-governed -----------------------------------------------------


def extract_5c(ctx):
    root = ctx.bundle.root
    return {
        "maintenance_plan": root.get("rai:dataReleaseMaintenancePlan"),
        "governance": root.get("dataGovernanceCommittee"),
        "conditions": root.get("conditionsOfAccess"),
        "license": root.get("license"),
        "pi": root.get("principalInvestigator"),
        "contact": root.get("contactEmail"),
    }


def transform_5c(ctx, raw):
    links = URL_RE.findall(str(raw["maintenance_plan"] or ""))
    dmp_link = links[0].rstrip(".,;") if links else None
    dmp_check = ctx.net.check_url(dmp_link) if dmp_link else None
    return {**raw, "dmp_link": dmp_link, "dmp_check": dmp_check,
            "has_plan": bool(raw["maintenance_plan"] or raw["governance"]),
            "has_terms": bool(raw["conditions"] or raw["license"])}


def present_5c(facts):
    items = [
        ev.text("Governance / maintenance plan",
                ev.clip(facts["maintenance_plan"])),
        ev.sub(ev.link("DMP link extracted from the plan", facts["dmp_link"],
                       display=facts["dmp_link"] or "none found")),
    ]
    if facts["dmp_check"]:
        chk = facts["dmp_check"]
        items.append(ev.sub(ev.flag("DMP link resolves",
                                    chk.get("ok") if chk.get("checked") else None,
                                    detail=chk.get("note"))))
    items += [
        ev.sub(ev.flag("Governance plan present", facts["has_plan"])),
        ev.text("Terms of access (conditionsOfAccess)",
                ev.clip(facts["conditions"])),
        ev.sub(ev.text("License", facts["license"])),
        ev.sub(ev.flag("Terms of access present", facts["has_terms"])),
        ev.text("Responsible party",
                "; ".join(str(x) for x in
                          [facts["governance"], facts["pi"], facts["contact"]]
                          if x)),
    ]
    return items


def estimate_5c(facts):
    if facts["has_plan"] and facts["has_terms"]:
        return ev.estimate("2", "governance/maintenance plan present",
                           "terms of access present")
    if facts["has_plan"]:
        return ev.estimate("1", "governance plan present but no terms of "
                                "access")
    if facts["has_terms"]:
        return None  # terms without a plan — the rubric has no rule for this
    return ev.estimate("0", "neither a governance plan nor terms of access")


# --- 5.d Associated --------------------------------------------------------


def extract_5d(ctx):
    stats = ctx.bundle.stats
    return {
        "entity_total": stats.entity_total,
        "entity_with_prov": stats.entity_with_prov_link,
        "haspart_count": len(as_list(ctx.bundle.root.get("hasPart"))),
        "subcrates_found": len(ctx.bundle.subcrates),
        "subcrates_referenced": ctx.bundle.subcrates_referenced,
        "graphs": ctx.bundle.evidence_graph_links(),
    }


def transform_5d(ctx, raw):
    return raw


def present_5d(facts):
    return [
        ev.percent("Entities carrying at least one machine-readable "
                   "provenance link", facts["entity_with_prov"],
                   facts["entity_total"]),
        ev.count("Sub-crates linked from the parent and present",
                 facts["subcrates_found"], of=facts["subcrates_referenced"]),
        ev.sub(ev.count("hasPart references on the root",
                        facts["haspart_count"])),
        ev.links("Evidence graphs (machine-derived association views)",
                 facts["graphs"]),
    ]


def estimate_5d(facts):
    if facts["subcrates_found"] < facts["subcrates_referenced"]:
        return ev.estimate("0",
                           f"only {facts['subcrates_found']} of "
                           f"{facts['subcrates_referenced']} referenced "
                           "sub-crates are present")
    if facts["entity_with_prov"] and (facts["graphs"]
                                      or facts["haspart_count"]):
        return ev.estimate("2",
                           "components associated machine-readably in the "
                           "archived RO-Crate (hasPart + provenance links)",
                           "accessibility of every component not verified — "
                           "downgrade if pieces are missing")
    return None
