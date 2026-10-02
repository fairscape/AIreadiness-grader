"""Build metadata-fabricated-max.json: a SCORING DEMO, not the authors' metadata.

Starts from metadata-standard-max.json (facts only) and fills every remaining
gap with invented but plausible content, to find the ceiling a Croissant can
reach using only schema.org, Croissant RAI and W3C PROV-O properties (plus the
Croissant format itself). Every value added here is FABRICATED: the IRB
determination, PIA, audit numbers, container image, governance plan, access
committee, usage terms, the second author's ORCID (ORCID's fictitious
test record) and the software DOI (DataCite test prefix 10.5072, never resolves).

    python build_fabricated_max.py metadata-standard-max.json metadata-fabricated-max.json
"""
import copy
import json
import sys

src, out = sys.argv[1:3]
d = json.load(open(src))
new = copy.deepcopy(d)
ctx = new["@context"]
ctx["odrl"] = "http://www.w3.org/ns/odrl/2/"

new["description"] = ("SCORING DEMO with fabricated metadata, not the authors' record. "
                      + d["description"])

# 1.d -- ORCID's documented fictitious researcher stands in for a real iD
new["creator"][1]["@id"] = "https://orcid.org/0000-0002-1825-0097"

# 4.c -- data license, contact, permitted/prohibited uses (ODRL in usageInfo,
# as Croissant 1.1 recommends), plus the HL7 label already present
new["license"] = "https://creativecommons.org/licenses/by/4.0/"
new["contactPoint"] = {"@type": "sc:ContactPoint", "contactType": "data access committee",
                       "email": "security-gym-dac@example.org",
                       "url": "https://github.com/j-klawson/security-gym/issues"}
new["usageInfo"] = [
    d["usageInfo"],
    {"@type": ["sc:CreativeWork", "odrl:Offer"], "name": "Security-Gym data use policy",
     "odrl:permission": {"@type": "odrl:Permission", "odrl:action": {"@id": "odrl:use"},
                         "name": "Research, teaching and benchmarking of detection and "
                                 "continual-learning methods, including AI/ML training."},
     "odrl:prohibition": [
         {"@type": "odrl:Prohibition", "odrl:action": {"@id": "odrl:use"},
          "name": "Re-identifying, contacting or profiling the holders of public IP addresses in the logs."},
         {"@type": "odrl:Prohibition", "odrl:action": {"@id": "odrl:use"},
          "name": "Using the data to plan or run attacks on the logged hosts or any third party."},
         {"@type": "odrl:Prohibition", "odrl:action": {"@id": "odrl:distribute"},
          "name": "Redistributing subsets that isolate individual visitors' activity."}]},
]

# 2.d / 2.e -- biases and QC with a link to the validation code and an audit
new["rai:dataBiases"] = d["rai:dataBiases"] + (
    " Class imbalance: 2.8% of events in the 30-day stream are malicious, so accuracy "
    "is dominated by the benign class; report per-class recall and PR-AUC. Events with "
    "no source IP are labelled by time window alone, which can mark concurrent benign "
    "daemon messages as malicious; an audit puts this at 0.3% of malicious labels. "
    "Attack timing follows a Poisson schedule, so models may learn the schedule rather "
    "than the attack content.")
new["rai:dataAnnotationAnalysis"] = d["rai:dataAnnotationAnalysis"] + (
    " The checks are implemented in "
    "https://github.com/j-klawson/security-gym/blob/v0.4.2/scripts/validate_labels.py. "
    "Two security analysts independently relabelled 2,000 randomly sampled events "
    "(1,000 benign, 1,000 malicious): agreement with the automated labels was 99.65% "
    "(Cohen's kappa 0.97); all disagreements were time-window-only matches.")

# 4.a -- ethics determination, consent basis covering AI/ML, legitimacy
new["rai:dataCollection"] = d["rai:dataCollection"] + (
    " The University of Michigan-Dearborn IRB reviewed the collection protocol "
    "(HUM-DEMO-0001) and determined it exempt under 45 CFR 46.104(d)(4) as secondary "
    "research on information collected for non-research purposes; the exemption "
    "explicitly covers release for AI/ML training and benchmarking. The servers' "
    "published privacy notice informs visitors that access logs may be used for "
    "security research. All data came from systems the author operates; no third-party "
    "systems were accessed and nothing was obtained by deception or coercion.")

# 4.b -- PIA and periodic reassessment
new["rai:personalSensitiveInformation"] = d["rai:personalSensitiveInformation"] + (
    " A privacy impact assessment by UM-Dearborn Information Security (March 2026) "
    "rated the retained public IPs low risk: they are not linked to names, accounts or "
    "content beyond the requested URL, and most belong to crawlers and scanners. "
    "Re-identification risk is reassessed annually and whenever a new linkage source "
    "(such as a public IP-to-identity dataset) appears; any address can be removed on "
    "request through the data access committee.")

# 5.c -- governance plan
new["rai:dataReleaseMaintenancePlan"] = d["rai:dataReleaseMaintenancePlan"] + (
    " Data management plan: Keith Lawson is the data steward, with UM-Dearborn Library "
    "Research Data Services as successor steward. Zenodo retains every version for at "
    "least 20 years; the maintainers commit to updates for 5 years after v4.1 "
    "(through 2031). Deprecated versions stay downloadable with a deprecation notice "
    "naming the replacement. Changes in law or repository policy, and removal requests, "
    "are reviewed by the data access committee within 30 days and recorded in the "
    "release notes. Roadmap: https://github.com/j-klawson/security-gym/blob/main/ROADMAP.md")

# 6.d -- splits and seeds
new["rai:dataPreprocessingProtocol"] = d["rai:dataPreprocessingProtocol"] + (
    " The streams are evaluated online in temporal order, so no train/validation/test "
    "split is defined; each stream's composition seed is recorded in its "
    "composition_meta table (99 for the 30-day stream). Nothing was withheld apart "
    "from the scrubbing described under personal information.")

# 1.a -- instruments and samples as structured entities the collection used
collect = next(a for a in new["prov:wasGeneratedBy"] if a["@id"] == "activity/collect-benign")
collect["prov:used"] = [
    {"@type": "prov:Entity", "additionalType": "Instrument", "@id": "instrument/ebpf-agent",
     "name": "BCC eBPF tracepoint agent", "description": "server/ebpf_collector.py"},
    *[{"@type": "prov:Entity", "additionalType": "Instrument", "@id": f"instrument/server-{i}",
       "name": f"Debian 13 server {i}"} for i in (1, 2, 3, 4)],
    *[{"@type": "prov:Entity", "additionalType": "Sample", "@id": f"sample/server-{i}-logs",
       "name": f"Raw log capture, server {i}"} for i in (1, 2, 3, 4)],
]

# 1.c / 6.c -- archived software with a container
for a in new["prov:wasGeneratedBy"]:
    for agent in a.get("prov:wasAssociatedWith") if isinstance(a.get("prov:wasAssociatedWith"), list) \
            else [a.get("prov:wasAssociatedWith")]:
        if isinstance(agent, dict) and "SoftwareAgent" in json.dumps(agent.get("@type")):
            agent["identifier"] = "https://doi.org/10.5072/zenodo.security-gym-0.4.2"
            if agent.get("name") == "security-gym 0.4.2":
                agent["softwareRequirements"] = "docker://ghcr.io/j-klawson/security-gym:0.4.2"
                agent["memoryRequirements"] = "16 GB RAM for the 30-day stream"

json.dump(new, open(out, "w"), indent=2, ensure_ascii=False)
