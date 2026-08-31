"""Section 4 — Ethics (gating)."""

import re

from .. import evidence as ev
from ..known import hl7_confidentiality_code

IRB_RE = re.compile(r"\bIRB\b|\bREC\b|protocol\s*(#|no\.?|number)|institutional "
                    r"review board|ethics (board|committee|review)", re.I)
URL_RE = re.compile(r"https?://[^\s\"\')\]]+")

# v1.5 4.a: prospective consent must cover downstream AI/ML use; retrospective
# data needs an explicit waiver/exemption basis for secondary AI/ML use.
AI_ML_USE_RE = re.compile(
    r"AI/ML|artificial intelligence|machine[- ]learning|\bAI\b|\bML\b|"
    r"commercializ", re.I)
WAIVER_RE = re.compile(
    r"waiver|exempt\w*|secondary (use|analysis)|retrospective", re.I)

# v1.5 4.b: Privacy Impact Assessment + periodic re-identification-risk
# reassessment for sensitive data.
PIA_RE = re.compile(
    r"privacy impact assessment|\bPIA\b|(privacy|disclosure|"
    r"re[- ]?identification) risk assess\w*", re.I)
REASSESS_RE = re.compile(
    r"(periodic\w*|annual\w*|regular\w*|ongoing) (re[- ]?)?(assess|review|"
    r"evaluat)\w*|reassess\w*|re[- ]?identification risk", re.I)


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
    consent_blob = " ".join(str(raw[k] or "") for k in
                            ("consent", "collection", "exemption",
                             "human_subjects", "ethical_review"))
    return {**raw, "irb_signals": irb_signals, "dmp_check": dmp_check,
            "aiml_use_hits": sorted(
                {m.group(0) for m in AI_ML_USE_RE.finditer(consent_blob)})[:6],
            "waiver_hits": sorted(
                {m.group(0).lower()
                 for m in WAIVER_RE.finditer(consent_blob)})[:6]}


def present_4a(facts):
    items = [
        ev.text("Collection description (rai:dataCollection)",
                ev.clip(facts["collection"])),
        ev.text("Ethics reviewers (ethicalReview)", ev.clip(facts["ethical_review"])),
        ev.text("Human subjects research", ev.clip(facts["human_subjects"])),
        ev.sub(ev.text("Human subjects exemption", ev.clip(facts["exemption"]))),
        ev.text("Informed consent", ev.clip(facts["consent"])),
        ev.text("At-risk populations", ev.clip(facts["at_risk"])),
        ev.sub(ev.flag("IRB / ethics-review references found",
                       bool(facts["irb"] or facts["irb_signals"]),
                       detail=", ".join(facts["irb_signals"]) or None)),
        ev.sub(ev.flag("Consent/ethics text mentions AI/ML or "
                       "commercialization (prospective data: consent must "
                       "explicitly cover downstream AI/ML use)",
                       bool(facts["aiml_use_hits"]),
                       detail=", ".join(facts["aiml_use_hits"]) or None)),
        ev.sub(ev.flag("Waiver / exemption / secondary-use language found "
                       "(retrospective data: the basis for secondary AI/ML "
                       "use must be explicit)",
                       bool(facts["waiver_hits"]),
                       detail=", ".join(facts["waiver_hits"]) or None)),
        ev.text("Management plan (rai:dataReleaseMaintenancePlan)",
                ev.clip(facts["maintenance_plan"])),
    ]
    if facts["dmp_check"]:
        chk = facts["dmp_check"]
        items.append(ev.sub(ev.flag(f"DMP link resolves: {chk['url']}",
                                    chk.get("ok") if chk.get("checked") else None,
                                    detail=chk.get("note"))))
    return items


def estimate_4a(facts):
    described = any(facts[k] for k in
                    ("collection", "ethical_review", "human_subjects",
                     "consent", "irb")) or facts["irb_signals"]
    if not described:
        return ev.estimate("0", "no acquisition, consent, or ethics-review "
                                "description anywhere in the metadata")
    return None  # sufficiency and legitimacy are a human read


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
    blob = " ".join(str(v or "") for v in raw.values())
    return {**raw,
            "pia_hits": sorted(
                {m.group(0).lower() for m in PIA_RE.finditer(blob)})[:6],
            "reassess_hits": sorted(
                {m.group(0).lower() for m in REASSESS_RE.finditer(blob)})[:6]}


def present_4b(facts):
    return [
        ev.text("Confidentiality level", facts["confidentiality"]),
        ev.text("Personal/sensitive information statement",
                ev.clip(facts["sensitive"])),
        ev.text("Data governance committee", ev.clip(facts["governance"])),
        ev.text("Ethics review", ev.clip(facts["ethical_review"])),
        ev.text("Management plan content (judge adequacy for the declared "
                "sensitivity)", ev.clip(facts["maintenance_plan"])),
        ev.flag("Privacy Impact Assessment / risk-assessment language found "
                "(required for high-sensitivity data)",
                bool(facts["pia_hits"]),
                detail=", ".join(facts["pia_hits"]) or None),
        ev.sub(ev.flag("Periodic re-identification-risk reassessment "
                       "language found (required for sensitive data)",
                       bool(facts["reassess_hits"]),
                       detail=", ".join(facts["reassess_hits"]) or None)),
    ]


def estimate_4b(facts):
    if not (facts["confidentiality"] or facts["sensitive"]
            or facts["maintenance_plan"]):
        return ev.estimate("0", "no sensitivity classification, sensitivity "
                                "statement, or management description")
    return None  # adequacy of management for the sensitivity — and whether
    # the data is high-sensitivity enough to demand a PIA — is a human read


# --- 4.c Ethically Disseminated --------------------------------------------

# v1.5: modality-specific ethical prohibitions are required where the data can
# synthesize / impersonate / re-identify an individual — raw voice or speech,
# personal genomes, face or full-head imaging, dense longitudinal geolocation.
HIGH_RISK_MODALITY_RE = re.compile(
    r"\bvoice\b|\bspeech\b|audio recording|genom\w+|whole[- ]genome|"
    r"\bWGS\b|face|facial|full[- ]head|geolocation|GPS trace|location "
    r"histor\w+", re.I)


def extract_4c(ctx):
    root = ctx.bundle.root
    return {
        "license": root.get("license"),
        "conditions": root.get("conditionsOfAccess"),
        "use_cases": root.get("rai:dataUseCases"),
        "prohibited": _first(root, "prohibitedUses", "usageInfo"),
        "contact": root.get("contactEmail"),
        "sensitive": root.get("rai:personalSensitiveInformation"),
        "keywords": root.get("keywords"),
        "description": root.get("description"),
    }


def transform_4c(ctx, raw):
    modality_blob = " ".join(str(raw[k] or "") for k in
                             ("keywords", "description", "sensitive"))
    return {**raw, "access_controlled": bool(raw["conditions"]),
            "high_risk_modality_hits": sorted(
                {m.group(0).lower()
                 for m in HIGH_RISK_MODALITY_RE.finditer(modality_blob)})[:8]}


def present_4c(facts):
    return [
        ev.text("License", facts["license"]),
        ev.text("Conditions of access / DUA", ev.clip(facts["conditions"])),
        ev.flag("Permitted uses stated", bool(facts["use_cases"]),
                detail=ev.clip(facts["use_cases"], 300)),
        ev.flag("Prohibited uses stated", bool(facts["prohibited"]),
                detail=ev.clip(facts["prohibited"], 300)),
        ev.flag("High-risk modality signals in the metadata (voice, genomes, "
                "face imaging, geolocation, …)",
                bool(facts["high_risk_modality_hits"]),
                detail=(", ".join(facts["high_risk_modality_hits"])
                        if facts["high_risk_modality_hits"] else None) or
                       "where such a modality is present, a 2 requires "
                       "explicit modality-specific ethical prohibitions "
                       "(e.g., no biometric synthesis, identity cloning, "
                       "discriminatory use)"),
        ev.text("Access-committee / dataset contact",
                facts["contact"] or "none listed",
                detail="required (and active) where access is controlled"),
    ]


def estimate_4c(facts):
    if not facts["license"] and not facts["conditions"]:
        return ev.estimate("0", "no license, DUA, or defined ethical terms — "
                                "openly released with no ethical framework, "
                                "or access-controlled without one")
    # everything above 0 is a judgment call under v1.5: whether terms are
    # "as open as possible, as closed as necessary", whether the modality
    # demands specific prohibitions, and whether a DAC contact is active
    return None


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
        ev.sub(ev.flag("Value is an HL7 v3-Confidentiality code",
                       bool(facts["hl7_code"]),
                       detail=(f"matches code '{facts['hl7_code']}' in "
                               "http://terminology.hl7.org/ValueSet/v3-Confidentiality"
                               if facts["hl7_code"] else
                               "prose value — compare against U/L/M/N/R/V display names"))),
        ev.text("De-identification statement", ev.clip(facts["deidentified"])),
        ev.text("Personal/sensitive information statement",
                ev.clip(facts["sensitive"])),
    ]


def estimate_4d(facts):
    if facts["hl7_code"]:
        return ev.estimate("2", "confidentiality level is an HL7 "
                                f"v3-Confidentiality code ('{facts['hl7_code']}')",
                           "whether the declared level is actually ENFORCED "
                           "(v1.5 0-rule) is not verified — score 0 if "
                           "controlled data is retrievable without "
                           "authorization or authorized users are blocked")
    if facts["confidentiality"]:
        return ev.estimate("1", "confidentiality level stated in prose, not "
                                "a standard vocabulary")
    return ev.estimate("0", "no security-level metadata")
