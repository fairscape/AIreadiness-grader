"""Build metadata-standard-max.json: the authors' security-gym-v4 Croissant
extended as far as schema.org, Croissant RAI and W3C PROV-O allow, on top of
the Croissant 1.1 format (MeSH, Wikidata, DDI-CDI and HL7 terms appear only as
values). Nothing FAIRSCAPE/EVI-specific is used.

Every added value is a fact from the Zenodo / PyPI / GitHub records, the
30-day stream itself (exp_30d_heavy_v4.db, sha256-verified), or the original
file, except the HL7 confidentiality code, which only the authors can assign
(see README).

    python build_standard_max.py metadata.json metadata-standard-max.json examples-30d.json
"""
import copy
import json
import sys

src, out = sys.argv[1:3]
d = json.load(open(src))
new = copy.deepcopy(d)

ctx = new["@context"]
ctx.update({
    "wd": "http://www.wikidata.org/entity/",
    "ddi-stats": "http://rdf-vocabulary.ddialliance.org/cv/SummaryStatisticType/2.1.2/",
    "annotation": "cr:annotation",
    "equivalentProperty": "cr:equivalentProperty",
    "examples": {"@id": "cr:examples", "@type": "@json"},
})
new["conformsTo"] = "http://mlcommons.org/croissant/1.1"

# --- FAIRness -------------------------------------------------------------
new["identifier"] = "https://doi.org/10.5281/zenodo.21763493"   # v4.1 version DOI
new["publisher"] = {"@type": "sc:Organization", "name": "Zenodo", "url": "https://zenodo.org"}
new["keywords"] = d["keywords"] + [
    "http://id.nlm.nih.gov/mesh/D016494",       # Computer Security
    "http://id.nlm.nih.gov/mesh/D000069550",    # Machine Learning
]

# --- key actors -------------------------------------------------------------
UMD = {"@type": "sc:Organization", "@id": "https://ror.org/035wtm547",
       "name": "University of Michigan-Dearborn"}
LAWSON = {"@type": ["sc:Person", "prov:Person"], "@id": "https://orcid.org/0009-0008-7536-1122",
          "name": "Keith Lawson", "affiliation": UMD}
new["creator"] = [
    LAWSON,
    # the ORCID registry has several "Hafiz Malik" records, none with this
    # affiliation, so no identifier is asserted
    {"@type": "sc:Person", "name": "Hafiz Malik", "affiliation": UMD},
]

# --- datasheet --------------------------------------------------------------
new["subjectOf"] = [
    {"@type": "sc:CreativeWork", "name": "Security-Gym dataset README (datasheet)",
     "url": "https://zenodo.org/records/21763493/files/DATASET_README.md",
     "encodingFormat": "text/markdown"},
    {"@type": "sc:CreativeWork", "name": "Hugging Face dataset card",
     "url": "https://huggingface.co/datasets/j-klawson/security-gym-v4/blob/main/README.md",
     "encodingFormat": "text/markdown"},
]

# --- RAI (facts measured on exp_30d_heavy_v4.db) ----------------------------
new["rai:dataCollectionMissingData"] = (
    "Measured on the 30-day stream (21,511,208 rows): campaign_id, attack_type, "
    "attack_stage and severity are NULL on exactly the 20,901,688 benign rows and "
    "populated on all 609,520 malicious rows; is_malicious, timestamp, source, raw_line "
    "and parsed are never NULL. src_ip is NULL on 20,112,710 rows (93.5%), session_id on "
    "20,476,710, username on 21,504,142 and service on 21,474,130, because most events "
    "(eBPF file/process records, syslog daemon messages) have no client address, session "
    "or user. NULL is the only missing-value marker; no empty strings are used.")
new["rai:personalSensitiveInformation"] = (
    "Server hostnames, domains and addresses are mapped to one synthetic target identity "
    "(isildur / 192.168.2.201), and attack traffic uses lab-private 192.168.2.x addresses. "
    "Benign web-access and SSH log lines keep the remote client's source IP: in the "
    "30-day stream 860,529 benign rows carry one of 11,413 distinct public IPv4 addresses "
    "(crawlers, scanners and other visitors), in both src_ip and raw_line.")
# HL7 v3-Confidentiality as a usage condition: Croissant 1.1 puts usage
# conditions in sc:usageInfo as DefinedTerms. "M" (moderate) is an
# illustrative choice given the public IPs above; the authors must assign it.
new["usageInfo"] = {
    "@type": "sc:DefinedTerm", "name": "moderate", "termCode": "M",
    "url": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality#M",
    "inDefinedTermSet": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality"}

# --- provenance (PROV-O, as Croissant 1.1 recommends) -----------------------
SOFTWARE = {
    "@type": ["prov:SoftwareAgent", "sc:SoftwareApplication"],
    "@id": "https://pypi.org/project/security-gym/0.4.2/",
    "name": "security-gym 0.4.2",
    "softwareVersion": "0.4.2",
    "codeRepository": "https://github.com/j-klawson/security-gym/tree/v0.4.2",
    "downloadUrl": "https://files.pythonhosted.org/packages/c2/f1/803771d161d1df84ca8c72e877055715e2da506c48c885204ab7b758d565/security_gym-0.4.2-py3-none-any.whl",
    "sha256": "c6eb41d6421350a403f31499109721cba8aad59fa1732aef6ed242b903c5efd4",
    "softwareRequirements": "https://github.com/j-klawson/security-gym/blob/v0.4.2/pyproject.toml",
    "license": "https://www.apache.org/licenses/LICENSE-2.0",
}
TAG = "https://github.com/j-klawson/security-gym/blob/v0.4.2/"
MODULES = {
    "activity/generate-attacks": ["attacks/orchestrator.py"],
    "activity/label": ["attacks/collection/labeler.py"],
    "activity/compose": ["scripts/scrub_benign_db.py", "src/security_gym/data/composer.py"],
    "activity/validate": ["scripts/validate_labels.py"],
}
ids = {
    "Benign telemetry collection": "activity/collect-benign",
    "Synthetic attack-event generation": "activity/generate-attacks",
    "Automated labelling and benign-baseline filtering": "activity/label",
    "PII scrubbing, compression, and stream composition": "activity/compose",
    "Automated validation of released streams": "activity/validate",
}
STREAMS = ["exp_7d_brute_v4.db.zst", "exp_30d_heavy_v4.db.zst",
           "exp_90d_v4.db.zst", "exp_365d_realistic_v4.db.zst"]
activities = []
for a in d["prov:wasGeneratedBy"]:
    a = copy.deepcopy(a)
    a["@id"] = ids[a["name"]]
    if a["@id"] == "activity/collect-benign":
        a["prov:wasAssociatedWith"] = {**LAWSON, "@type": ["prov:Person", "sc:Person"]}
    else:
        # the module that ran this step, at the v0.4.2 tag; only the composer
        # ships in the PyPI 0.4.2 wheel, the others exist only in the GitHub repo
        agent = a["prov:wasAssociatedWith"]
        agent["codeRepository"] = [TAG + p for p in MODULES[a["@id"]]]
        if a["@id"] == "activity/compose":
            a["prov:wasAssociatedWith"] = [agent, SOFTWARE]
    if a["@id"] == "activity/compose":
        # recorded in exp_30d_heavy_v4's own composition_meta table
        a["description"] += (
            " The 30-day stream was composed with seed 99 over 2,592,000 s at 10 "
            "campaigns/day with a uniform 0.2 mix of discovery, brute_force, "
            "web_exploit, credential_stuffing and execution (2026-03-23T00:20:59Z).")
        a["prov:used"] = [{"@id": "benign_v4.db.zst"}, {"@id": "campaigns_v2.db.zst"}]
        # outputs are stated from the file side (prov:wasGeneratedBy below);
        # stating both directions makes a cycle mlcroissant cannot expand
    if a["@id"] == "activity/validate":
        a["prov:used"] = [{"@id": s} for s in STREAMS]
    activities.append(a)
new["prov:wasGeneratedBy"] = activities

for f in new["distribution"]:
    if f["@id"] in STREAMS:
        f["prov:wasGeneratedBy"] = {"@id": "activity/compose"}
        f["prov:wasDerivedFrom"] = [{"@id": "benign_v4.db.zst"}, {"@id": "campaigns_v2.db.zst"}]
    elif f["@id"] == "benign_v4.db.zst":
        f["prov:wasGeneratedBy"] = {"@id": "activity/collect-benign"}
    elif f["@id"] == "campaigns_v2.db.zst":
        f["prov:wasGeneratedBy"] = [{"@id": "activity/generate-attacks"},
                                    {"@id": "activity/label"}]

# The authors typed their sources sc:Dataset; mlcroissant then takes the
# first nested sc:Dataset as the Croissant root and finds no record sets.
# Typed as prov:Entity (as in the Croissant 1.1 PROV examples) they stay
# descriptions of sources.
for src_entity in new["prov:wasDerivedFrom"]:
    src_entity["@type"] = "prov:Entity"

# --- record set: bindings, statistics, examples ----------------------------
rs = new["recordSet"][0]
fields = {f["@id"]: f for f in rs["field"]}
fields["events/src_ip"]["dataType"] = ["sc:Text", "wd:Q11135"]        # IP address
fields["events/is_malicious"]["dataType"] = ["sc:Integer", "cr:Label"]
fields["events/timestamp"]["dataType"] = "sc:DateTime"
fields["events/parsed"]["description"] = (
    "JSON-encoded parsed fields. Never NULL in the 30-day stream.")
fields["events/severity"]["description"] = (
    "Threat severity on a 1-5 scale (1-3 occur in the 30-day stream). NULL for benign events.")
fields["events/is_malicious"]["annotation"] = [{
    "@type": "cr:Field", "@id": "events/is_malicious/mean", "name": "mean",
    "description": "Share of malicious events in exp_30d_heavy_v4.",
    "value": 0.028335,
    "dataType": {"@type": "sc:DefinedTerm", "@id": "ddi-stats:7975ed0",
                 "termCode": "ArithmeticMean", "name": "Arithmetic Mean",
                 "inDefinedTermSet": "http://rdf-vocabulary.ddialliance.org/cv/SummaryStatisticType/2.1.2/"},
}]
fields["events/severity"]["annotation"] = [
    {"@type": "cr:Field", "@id": "events/severity/min", "name": "min", "value": 1,
     "equivalentProperty": "sc:minValue"},
    {"@type": "cr:Field", "@id": "events/severity/max", "name": "max", "value": 3,
     "dataType": "ddi-stats:8321e79", "equivalentProperty": "sc:maxValue"},
    {"@type": "cr:Field", "@id": "events/severity/mean", "name": "mean", "value": 2.2757,
     "dataType": "ddi-stats:7975ed0"},
]
rs["annotation"] = [
    {"@type": "cr:Field", "@id": "events/count", "name": "count",
     "description": "Rows in exp_30d_heavy_v4.", "value": 21511208,
     "dataType": "wd:Q4049983"},
    {"@type": "cr:Field", "@id": "events/malicious_count", "name": "malicious count",
     "description": "Rows with is_malicious = 1 in exp_30d_heavy_v4.", "value": 609520,
     "dataType": "wd:Q4049983"},
]
# four real rows of exp_30d_heavy_v4 (ids 6, 137999, 171163 and the first
# benign syslog row), chosen to avoid third-party public IPs
rs["examples"] = json.load(open(sys.argv[3]))

json.dump(new, open(out, "w"), indent=2, ensure_ascii=False)
