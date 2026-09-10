"""The form catalogue: which properties the improve page edits, and which
AI-Ready criteria each one feeds.

Every entry is a single property on an entity that already exists in the
crate: no new entities, no new graph links. ``entity`` is
``"root"`` (the crate's root Dataset) or ``"software"`` (one column in the
Software-entities table).

Field keys
----------
prop      JSON-LD property name written verbatim
label     short human label
type      text | textarea | list | idlist | bool | select | number
          list   -> one value per line, written as a JSON array of strings
          idlist -> one IRI per line, written as [{"@id": ...}, ...]
          bool   -> tri-state (unset / true / false)
criteria  criterion ids this property feeds; the first is where the field
          is rendered, the rest show a jump link from their card
win       True when filling it moves a rubric score mechanically (the
          evidence extractor decides without a human read)
help      one-line hint shown under the input
options   for select: [(value, label)]; for list/text: datalist suggestions
"""

HL7_CONFIDENTIALITY = [
    ("unrestricted", "unrestricted (U) — no confidentiality requirement"),
    ("low", "low (L) — minimal sensitivity"),
    ("moderate", "moderate (M)"),
    ("normal", "normal (N) — standard healthcare data"),
    ("restricted", "restricted (R) — restricted access required"),
    ("very restricted", "very restricted (V) — strictest controls"),
]

LICENSES = [
    "https://creativecommons.org/licenses/by/4.0/",
    "https://creativecommons.org/licenses/by-sa/4.0/",
    "https://creativecommons.org/licenses/by-nc/4.0/",
    "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    "https://creativecommons.org/publicdomain/zero/1.0/",
    "https://www.apache.org/licenses/LICENSE-2.0",
    "https://opensource.org/licenses/MIT",
    "https://spdx.org/licenses/Apache-2.0",
    "https://spdx.org/licenses/MIT",
]

DATA_COLLECTION_TYPES = [
    "Surveys", "Secondary Data Analysis", "Physical Data Collection",
    "Direct Measurement", "Document Analysis", "Manual Human Curator",
    "Software Collection", "Experiments", "Web Scraping", "Web API",
    "Focus Groups", "Self-Reporting", "Customer Feedback Data",
    "User-Generated Content", "Passive Data Collection", "Others",
]

SENSITIVE_TYPES = [
    "None", "Gender", "Socio-economic status", "Geography", "Language",
    "Age", "Culture", "Experience or Seniority", "Race or ethnicity",
    "Health status", "Biometrics", "Genomic data",
]

# Vocabularies the ontology-term editor offers: name, IRI template shown as a
# placeholder, search page (the term label is appended), and the host the
# grader's known.py recognises. Ordered by how often biomedical crates use them.
VOCABS = [
    dict(name="OBO Foundry (CL, UBERON, GO, OBI, NCIT, PATO, …)",
         iri="http://purl.obolibrary.org/obo/CL_0000000",
         search="https://www.ebi.ac.uk/ols4/search?q=", host="purl.obolibrary.org"),
    dict(name="MeSH", iri="http://id.nlm.nih.gov/mesh/D002477",
         search="https://meshb.nlm.nih.gov/search?searchInField=termDescriptor&query=",
         host="id.nlm.nih.gov/mesh"),
    dict(name="NCI Thesaurus", iri="http://purl.obolibrary.org/obo/NCIT_C12508",
         search="https://www.ebi.ac.uk/ols4/search?ontology=ncit&q=", host="purl.obolibrary.org"),
    dict(name="Cellosaurus (cell lines)", iri="https://www.cellosaurus.org/CVCL_0042",
         search="https://www.cellosaurus.org/search?input=", host="cellosaurus.org"),
    dict(name="UniProt (proteins)", iri="https://www.uniprot.org/uniprotkb/P04637",
         search="https://www.uniprot.org/uniprotkb?query=", host="uniprot.org"),
    dict(name="Ensembl (genes)", iri="https://www.ensembl.org/id/ENSG00000141510",
         search="https://www.ensembl.org/Multi/Search/Results?q=", host="ensembl.org"),
    dict(name="identifiers.org (compact IDs)", iri="https://identifiers.org/taxonomy:9606",
         search="https://identifiers.org/", host="identifiers.org"),
    dict(name="SNOMED CT", iri="http://snomed.info/id/254837009",
         search="https://browser.ihtsdotools.org/?perspective=full&q=", host="snomed.info"),
    dict(name="LOINC", iri="https://loinc.org/2345-7",
         search="https://loinc.org/search/?t=1&s=", host="loinc.org"),
]

PROFILES = [
    "https://w3id.org/ro/crate/1.2",
    "https://w3id.org/fairscape/profile/0.1",
    "http://mlcommons.org/croissant/1.0",
]

FIELDS = [
    # ---------------------------------------------------------------- 0.a
    dict(prop="identifier", label="External persistent identifier (DOI)",
         type="text", criteria=["0.a", "0.b", "5.a"], win=True,
         help="A resolvable PID for the deposit — a DOI is best "
              "(https://doi.org/10.…). The crate's own ark: @id counts as a PID "
              "already; a DOI from the repository you deposit in lifts 0.a/5.a.",
         placeholder="https://doi.org/10.5281/zenodo.1234567"),
    dict(prop="publisher", label="Publisher / repository",
         type="text", criteria=["0.a", "5.a", "5.b", "1.d", "6.b"], win=True,
         help="Name the repository the dataset is deposited in and include its "
              "URL — the grader recognises sustainable repositories by host "
              "(zenodo.org, datadryad.org, massive.ucsd.edu, physionet.org, …).",
         options=["Zenodo — https://zenodo.org", "Dataverse — https://dataverse.org",
                  "Dryad — https://datadryad.org", "Figshare — https://figshare.com",
                  "OSF — https://osf.io", "ICPSR — https://www.icpsr.umich.edu",
                  "Mendeley Data — https://data.mendeley.com",
                  "MassIVE — https://massive.ucsd.edu", "PRIDE — https://www.ebi.ac.uk/pride",
                  "GEO — https://www.ncbi.nlm.nih.gov/geo", "SRA — https://www.ncbi.nlm.nih.gov/sra",
                  "dbGaP — https://www.ncbi.nlm.nih.gov/gap", "ENA — https://www.ebi.ac.uk/ena",
                  "BioStudies — https://www.ebi.ac.uk/biostudies", "EMPIAR — https://www.ebi.ac.uk/empiar",
                  "PhysioNet — https://physionet.org", "OpenNeuro — https://openneuro.org",
                  "IDR — https://idr.openmicroscopy.org"]),
    dict(prop="url", label="Landing page URL",
         type="text", criteria=["0.b", "6.b"], win=False,
         help="Canonical web page for the dataset (repository record).",
         placeholder="https://…"),
    # ---------------------------------------------------------------- 0.d
    dict(prop="license", label="License (URL)",
         type="text", criteria=["0.d", "4.c", "3.a", "5.c"], win=True,
         help="A bare, resolvable license IRI with no trailing prose — "
              "that is what counts as machine-readable.",
         options=LICENSES, placeholder="https://creativecommons.org/licenses/by/4.0/"),
    dict(prop="conditionsOfAccess", label="Conditions of access / DUA terms",
         type="textarea", criteria=["0.d", "4.c", "3.a", "6.b"], win=False,
         help="Access terms: open, registration, DUA, controlled access and "
              "how to request it. Mention whether AI/ML reuse is permitted."),
    dict(prop="usageInfo", label="Usage information",
         type="textarea", criteria=["0.d", "3.b", "6.c"], win=False,
         help="How to use / reproduce with the data (commands, environment, "
              "entry points)."),
    # ---------------------------------------------------------------- 1.x
    dict(prop="rai:dataCollectionRawData", label="Raw data source (ground truth)",
         type="textarea", criteria=["1.a", "5.a"], win=False,
         help="Name the exact upstream artifacts: the specific dataset, "
              "instrument run, EHR extract, or lab and sample set the data "
              "was derived from, and where the raw copy is archived."),
    dict(prop="completeness", label="Completeness / known provenance gaps",
         type="textarea", criteria=["1.b", "2.d"], win=False,
         help="State whether the provenance record is complete; disclose any "
              "chain-of-custody gaps or missing collection circumstances."),
    dict(prop="author", label="Authors",
         type="list", criteria=["1.d"], win=False,
         help="One per line. Include an ORCID URL after the name where you "
              "have one, e.g. 'Jane Doe https://orcid.org/0000-0002-1825-0097'."),
    dict(prop="principalInvestigator", label="Principal investigator",
         type="text", criteria=["1.d", "5.c"], win=False,
         help="Person responsible for the dataset; add their ORCID URL."),
    dict(prop="funder", label="Funder / grant",
         type="text", criteria=["1.d"], win=False,
         help="Funding organisation and grant number (shown in the datasheet)."),
    # ---------------------------------------------------------------- 2.x
    dict(prop="description", label="Description / abstract",
         type="textarea", criteria=["2.a", "1.b", "2.e"], win=False,
         help="A substantive abstract: what the data is, how it was produced, "
              "what it is for. Nextflow crates usually ship a one-liner here."),
    dict(prop="keywords", label="Keywords",
         type="list", criteria=["2.a"], win=False,
         help="One per line. Free-text keywords score 1; add controlled "
              "vocabulary terms below to reach 2."),
    dict(prop="about", label="Ontology terms the dataset is about",
         type="terms", criteria=["0.c", "2.a", "2.c", "6.a"], win=True,
         help="One row per term: the ontology IRI plus its label. Written as "
              "schema.org DefinedTerm objects under `about`. A recognised "
              "ontology IRI (OBO Foundry, MeSH, NCIt, Cellosaurus, UniProt, "
              "SNOMED, LOINC, identifiers.org) anywhere in the crate lifts 0.c, "
              "2.c and 6.a; 2.a additionally wants DefinedTerm graph entities.",
         options=VOCABS),
    dict(prop="contentSize", label="Total content size",
         type="text", criteria=["2.b"], win=False,
         help="Human-readable size such as '1.7 GB'.", placeholder="1.7 GB"),
    dict(prop="rai:dataCollectionMissingData", label="Missing data & encoding convention",
         type="textarea", criteria=["2.b", "2.e", "2.d", "6.d"], win=False,
         help="How missing values are represented (one documented convention) "
              "and why data is missing. Non-tabular data: dropped/failed "
              "items, absent channels, omitted slices."),
    dict(prop="rai:dataBiases", label="Known biases & assumptions",
         type="textarea", criteria=["2.d", "3.a"], win=False,
         help="Specific, dataset-grounded sources of bias (cell lines vs "
              "tissue, antibody availability, site selection, cohort gaps). "
              "'No known bias' scores 0."),
    dict(prop="rai:dataLimitations", label="Limitations",
         type="textarea", criteria=["2.d", "3.b", "3.a"], win=False,
         help="What the data cannot support; scale, stochasticity, "
              "representativeness limits."),
    dict(prop="rai:dataCollection", label="Data collection & QC procedure",
         type="textarea", criteria=["2.e", "4.a", "3.a", "1.b"], win=False,
         help="How the data was collected/derived and what quality control was "
              "applied. Include a link to the QC protocol or software; a dead "
              "link here forces 2.e to 0."),
    dict(prop="rai:dataPreprocessingProtocol", label="Preprocessing steps",
         type="list", criteria=["2.e", "6.d"], win=False,
         help="One step per line: filtering, normalisation, tokenisation, "
              "thresholds applied."),
    dict(prop="rai:dataManipulationProtocol", label="Cleaning / manipulation protocol",
         type="textarea", criteria=["2.e"], win=False,
         help="Removal of instances, handling of outliers, de-duplication."),
    # ---------------------------------------------------------------- 3.x
    dict(prop="rai:dataUseCases", label="Intended / appropriate uses",
         type="textarea", criteria=["3.b", "3.a", "4.c"], win=True,
         help="What the dataset is suitable for. Together with limitations or "
              "prohibited uses this completes 3.b."),
    dict(prop="prohibitedUses", label="Prohibited / inappropriate uses",
         type="textarea", criteria=["3.b", "4.c"], win=True,
         help="Explicit no-go uses (clinical decisions, re-identification, …)."),
    dict(prop="associatedPublication", label="Associated publications",
         type="list", criteria=["3.b"], win=False,
         help="One per line; include the DOI URL so it is linkable."),
    dict(prop="citation", label="Preferred citation",
         type="textarea", criteria=["3.b"], win=False,
         help="How to cite this dataset."),
    # ---------------------------------------------------------------- 4.x
    dict(prop="humanSubjectResearch", label="Human subjects involvement",
         type="text", criteria=["4.a"], win=False,
         help="'No' with the reason, or 'Yes' plus a short description "
              "of the population.",
         placeholder="No. Derived from commercially available de-identified cell lines."),
    dict(prop="ethicalReview", label="Ethical review",
         type="textarea", criteria=["4.a", "4.b"], win=False,
         help="Which IRB/REC or committee reviewed the work, when, and what "
              "was approved — or why no review was required."),
    dict(prop="irb", label="IRB / ethics committee",
         type="text", criteria=["4.a"], win=False,
         help="Name of the reviewing board.", placeholder="University of X IRB-HSR"),
    dict(prop="irbProtocolId", label="IRB protocol ID",
         type="text", criteria=["4.a"], win=False,
         help="Protocol / approval number.", placeholder="IRB-2023-04521"),
    dict(prop="humanSubjectExemption", label="Exemption / waiver basis",
         type="textarea", criteria=["4.a"], win=False,
         help="For retrospective or secondary use: the documented waiver, "
              "exemption category, or why the work is not human-subjects research."),
    dict(prop="d4d:informedConsent", label="Informed consent",
         type="textarea", criteria=["4.a"], win=False,
         help="Consent type and scope; state whether consent covers downstream "
              "AI/ML training and commercialisation."),
    dict(prop="d4d:atRiskPopulations", label="At-risk populations",
         type="text", criteria=["4.a"], win=False,
         help="Children, prisoners, indigenous communities, … or 'none'."),
    dict(prop="fdaRegulated", label="FDA regulated",
         type="bool", criteria=["4.a"], win=False,
         help="Clinical-trial or medical-device data subject to FDA rules."),
    dict(prop="dataGovernanceCommittee", label="Data governance committee / steward",
         type="text", criteria=["4.b", "5.c"], win=False,
         help="Committee name or the person responsible for oversight and access "
              "decisions."),
    dict(prop="rai:personalSensitiveInformation", label="Sensitive attributes present",
         type="list", criteria=["4.b", "4.d", "4.c"], win=False,
         help="One per line, or 'None' with a short justification.",
         options=SENSITIVE_TYPES),
    dict(prop="d4d:participantPrivacy", label="Privacy protection",
         type="textarea", criteria=["4.b"], win=False,
         help="Anonymisation / de-identification method, access controls, any "
              "privacy impact assessment and re-identification risk reassessment plan."),
    dict(prop="contactEmail", label="Contact / data access committee email",
         type="text", criteria=["4.c", "1.d", "5.c"], win=False,
         help="Active contact for questions and access requests.",
         placeholder="name@institution.edu"),
    dict(prop="confidentialityLevel", label="Confidentiality level (HL7)",
         type="select", criteria=["4.d", "4.b"], win=True,
         help="Must be one of the HL7 v3-Confidentiality codes to score 2; any "
              "other wording scores 1.", options=HL7_CONFIDENTIALITY),
    dict(prop="deidentified", label="De-identified",
         type="bool", criteria=["4.d"], win=False,
         help="Has personally identifiable information been removed?"),
    # ---------------------------------------------------------------- 5.x
    dict(prop="rai:dataReleaseMaintenancePlan", label="Maintenance / governance plan",
         type="textarea", criteria=["5.c", "4.a", "4.b", "3.a", "5.b"], win=False,
         help="Who maintains the dataset, update cadence, retention and "
              "long-term stewardship, policy-change handling. A linked DMP URL "
              "is best."),
    dict(prop="rai:dataCollectionType", label="Data collection type(s)",
         type="list", criteria=["5.b"], win=False,
         help="One per line from the Croissant RAI recommended values.",
         options=DATA_COLLECTION_TYPES),
    # ---------------------------------------------------------------- 6.x
    dict(prop="conformsTo", label="Profiles / standards the crate conforms to",
         type="idlist", criteria=["6.a"], win=False,
         help="One IRI per line. RO-Crate and FAIRSCAPE profiles are recognised "
              "as having deterministic validators.", options=PROFILES),
    dict(prop="d4d:samplingStrategies", label="Splits, sampling & withheld data",
         type="textarea", criteria=["6.d"], win=False,
         help="Train/validation/test splits with strategy and seed (or why "
              "none are needed); how any sample was drawn; any withheld, "
              "redacted, censored or blinded data."),
    # -------------------------------------------------- Software entities
    dict(prop="description", label="Description", entity="software",
         type="text", criteria=["6.c", "1.c"], win=False,
         help="What the software does and the environment it ran in "
              "(language, versions, GPU). The grader reads these descriptions "
              "as 6.c evidence."),
    dict(prop="contentUrl", label="Source location", entity="software",
         type="text", criteria=["1.c"], win=True,
         help="Where the code lives (GitHub scores 1; an archived, "
              "PID-bearing release scores 2)."),
    dict(prop="codeRepository", label="Archived release (DOI / Software Heritage)",
         entity="software", type="text", criteria=["1.c"], win=True,
         help="Zenodo DOI, Software Heritage SWHID URL, or PyPI release of the "
              "exact version used.",
         placeholder="https://doi.org/10.5281/zenodo.…"),
    dict(prop="version", label="Version", entity="software",
         type="text", criteria=["1.c"], win=False,
         help="Exact version / tag / commit that was run."),
    dict(prop="containerImage", label="Container image", entity="software",
         type="text", criteria=["6.c"], win=True,
         help="Docker/Singularity reference, ideally with a digest.",
         placeholder="docker.io/idekerlab/cellmaps:1.6.0@sha256:…"),
    dict(prop="softwareRequirements", label="Software requirements", entity="software",
         type="text", criteria=["6.c"], win=False,
         help="Path to environment.yml / requirements.txt in the crate, or "
              "name==version pairs."),
    dict(prop="hardwareRequirements", label="Hardware requirements", entity="software",
         type="text", criteria=["6.c"], win=False,
         help="GPU model, RAM floor, OS.", placeholder="1× NVIDIA GPU ≥ 8 GB, 32 GB RAM"),
]

# Criteria that no form field can move (they need new entities, file hashes,
# or on-disk artifacts). The page explains what would move them.
OUT_OF_SCOPE_NOTES = {
    "1.a": "Score 2 needs Sample, Instrument and Experiment entities describing the "
           "ground truth — that is entity creation, out of scope here. The raw-data "
           "field below gets the source named in a structured field (score 1).",
    "1.b": "Computation steps and their software links come from the workflow "
           "recorder (nf-fairscape / fairscape-cli). Disclose provenance gaps below.",
    "2.b": "Per-variable summary statistics need SummaryStats entities: run "
           "`fairscape-cli augment summary-stats` on tabular files. Document the "
           "missing-value convention below.",
    "2.c": "Schemas are EVI:Schema entities (nf-fairscape `schemas = true`, or "
           "`fairscape-cli schema infer`). Vocabulary bindings can be added as "
           "subject-term IRIs in 2.a.",
    "3.c": "Checksums are computed from the files: nf-fairscape `checksums = true` "
           "or `fairscape-cli augment` / the hash-coverage skill.",
    "5.d": "Scored from hasPart, sub-crate presence on disk and provenance links — "
           "nothing to type here.",
    "6.b": "Scored from Dataset contentUrl hosts (http/s3/gs/drs). Root fields only "
           "add context.",
    "6.c": "The mechanical estimate counts Computations with a usedContainer link "
           "(a Container entity — out of scope here). The grader also reads "
           "Software descriptions, so describe the environment on each Software "
           "entity in the table below and in usageInfo.",
}


# How much work a field is, for the checklist view (1 = a value you already
# know or can paste, 2 = a sentence or two, 3 = a paragraph that needs thought).
# Software columns are keyed "software:<prop>". Anything unlisted is 2.
EFFORT = {
    1: ["identifier", "publisher", "url", "license", "contactEmail",
        "principalInvestigator", "funder", "contentSize", "confidentialityLevel",
        "deidentified", "fdaRegulated", "humanSubjectResearch", "irb",
        "irbProtocolId", "dataGovernanceCommittee", "citation",
        "associatedPublication", "keywords", "author", "rai:dataCollectionType",
        "conformsTo", "software:contentUrl", "software:version",
        "software:codeRepository", "software:containerImage"],
    3: ["rai:dataBiases", "rai:dataLimitations", "rai:dataCollection",
        "rai:dataCollectionMissingData", "rai:dataCollectionRawData",
        "completeness", "rai:dataPreprocessingProtocol",
        "rai:dataManipulationProtocol", "d4d:informedConsent",
        "d4d:participantPrivacy", "rai:dataReleaseMaintenancePlan",
        "d4d:samplingStrategies", "software:hardwareRequirements",
        "software:softwareRequirements", "software:description"],
}
EFFORT_LABELS = {
    1: "Quick",
    2: "A sentence or two",
    3: "In depth",
}


def catalogue():
    """Fields with defaults filled in, ready for JSON serialisation."""
    effort_of = {}
    for level, props in EFFORT.items():
        for p in props:
            effort_of[p] = level
    out = []
    for f in FIELDS:
        entry = {"entity": "root", "win": False,
                 "placeholder": "", "options": None}
        entry.update(f)
        key = ("software:" if entry["entity"] == "software" else "") + entry["prop"]
        entry["effort"] = effort_of.get(key, 2)
        if entry["type"] == "select":
            entry["options"] = [list(o) for o in entry["options"]]
        out.append(entry)
    return out


def props_for_criterion(cid, fields=None):
    """(primary_fields, related_fields) for a criterion id."""
    fields = fields or catalogue()
    primary = [f for f in fields if f["criteria"][0] == cid]
    related = [f for f in fields if cid in f["criteria"][1:]]
    return primary, related
