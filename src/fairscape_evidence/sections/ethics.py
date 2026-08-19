"""Section 4 — Ethics (gating)."""

import re

from .. import evidence as ev
from ..known import hl7_confidentiality_code

IRB_RE = re.compile(r"\bIRB\b|\bREC\b|protocol\s*(#|no\.?|number)|institutional "
                    r"review board|ethics (board|committee|review)", re.I)
URL_RE = re.compile(r"https?://[^\s\"\')\]]+")


def _first(root, *fields):
    """First populated value among aliased field spellings (d4d:/rai:/bare)."""
    for f in fields:
        v = root.get(f)
        if v:
            return v
    return None


# --- 4.a Ethically acquired ------------------------------------------------


def extract_4a(ctx):
    root = ctx.bundle.root
    return {
        "collection": root.get("rai:dataCollection"),
        "ethical_review": root.get("ethicalReview"),
        "human_subjects": _first(root, "humanSubjectResearch",
                                 "d4d:humanSubjectResearch"),
        "exemption": _first(root, "humanSubjectExemption",
                            "d4d:humanSubjectExemption"),
        "consent": _first(root, "informedConsent", "d4d:informedConsent"),
        "at_risk": _first(root, "atRiskPopulations", "d4d:atRiskPopulations"),
        "irb": _first(root, "irb", "irbProtocolId", "d4d:irb"),
        "maintenance_plan": root.get("rai:dataReleaseMaintenancePlan"),
    }


def transform_4a(ctx, raw):
    blob = " ".join(str(v or "") for v in raw.values())
    irb_signals = sorted({m.group(0) for m in IRB_RE.finditer(blob)})
    dmp_links = URL_RE.findall(str(raw["maintenance_plan"] or ""))
    dmp_check = ctx.net.check_url(dmp_links[0].rstrip(".,;")) if dmp_links else None
    return {**raw, "irb_signals": irb_signals, "dmp_check": dmp_check}


def present_4a(facts):
    items = [
        ev.text("Collection description (rai:dataCollection)",
                ev.clip(facts["collection"])),
        ev.text("Ethics reviewers (ethicalReview)", ev.clip(facts["ethical_review"])),
        ev.text("Human subjects research", ev.clip(facts["human_subjects"])),
        ev.text("Human subjects exemption", ev.clip(facts["exemption"])),
        ev.text("Informed consent", ev.clip(facts["consent"])),
        ev.text("At-risk populations", ev.clip(facts["at_risk"])),
        ev.flag("IRB / ethics-review references found",
                bool(facts["irb"] or facts["irb_signals"]),
                detail=", ".join(facts["irb_signals"]) or None),
        ev.text("Management plan (rai:dataReleaseMaintenancePlan)",
                ev.clip(facts["maintenance_plan"])),
    ]
    if facts["dmp_check"]:
        chk = facts["dmp_check"]
        items.append(ev.flag(f"DMP link resolves: {chk['url']}",
                             chk.get("ok") if chk.get("checked") else None,
                             detail=chk.get("note")))
    return items


# --- 4.b Ethically managed -------------------------------------------------


def extract_4b(ctx):
    root = ctx.bundle.root
    return {
        "confidentiality": root.get("confidentialityLevel"),
        "sensitive": root.get("rai:personalSensitiveInformation"),
        "governance": root.get("dataGovernanceCommittee"),
        "ethical_review": root.get("ethicalReview"),
        "maintenance_plan": root.get("rai:dataReleaseMaintenancePlan"),
    }


def transform_4b(ctx, raw):
    return raw


def present_4b(facts):
    return [
        ev.text("Confidentiality level", facts["confidentiality"]),
        ev.text("Personal/sensitive information statement",
                ev.clip(facts["sensitive"])),
        ev.text("Data governance committee", ev.clip(facts["governance"])),
        ev.text("Ethics review", ev.clip(facts["ethical_review"])),
        ev.text("Management plan content (judge adequacy for the declared "
                "sensitivity)", ev.clip(facts["maintenance_plan"])),
    ]


# --- 4.c Ethically Disseminated --------------------------------------------


def extract_4c(ctx):
    root = ctx.bundle.root
    return {
        "license": root.get("license"),
        "conditions": root.get("conditionsOfAccess"),
        "use_cases": root.get("rai:dataUseCases"),
        "prohibited": _first(root, "prohibitedUses", "usageInfo"),
        "contact": root.get("contactEmail"),
        "sensitive": root.get("rai:personalSensitiveInformation"),
    }


def transform_4c(ctx, raw):
    return {**raw, "access_controlled": bool(raw["conditions"])}


def present_4c(facts):
    return [
        ev.text("License", facts["license"]),
        ev.text("Conditions of access / DUA", ev.clip(facts["conditions"])),
        ev.flag("Permitted uses stated", bool(facts["use_cases"]),
                detail=ev.clip(facts["use_cases"], 300)),
        ev.flag("Prohibited uses stated", bool(facts["prohibited"]),
                detail=ev.clip(facts["prohibited"], 300)),
        ev.text("Access-committee / dataset contact",
                facts["contact"] or "none listed",
                detail="N/A if fully open with no access committee"),
    ]


# --- 4.d Secure ------------------------------------------------------------


def extract_4d(ctx):
    root = ctx.bundle.root
    return {
        "confidentiality": root.get("confidentialityLevel"),
        "deidentified": _first(root, "deidentified", "d4d:deidentified"),
        "sensitive": root.get("rai:personalSensitiveInformation"),
    }


def transform_4d(ctx, raw):
    code = hl7_confidentiality_code(raw["confidentiality"])
    return {**raw, "hl7_code": code}


def present_4d(facts):
    return [
        ev.text("Confidentiality level", facts["confidentiality"]),
        ev.flag("Value is an HL7 v3-Confidentiality code",
                bool(facts["hl7_code"]),
                detail=(f"matches code '{facts['hl7_code']}' in "
                        "http://terminology.hl7.org/ValueSet/v3-Confidentiality"
                        if facts["hl7_code"] else
                        "prose value — compare against U/L/M/N/R/V display names")),
        ev.text("De-identification statement", ev.clip(facts["deidentified"])),
        ev.text("Personal/sensitive information statement",
                ev.clip(facts["sensitive"])),
    ]
