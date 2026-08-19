"""Reference tables shared by the section extractors.

Every list here names real, published registries, vocabularies, or hosts:
  - PID schemes: the rubric's own list (0.a) — ARK, CSTR, DOI, IGSN, PURL, URN, HDL
  - HL7 confidentiality codes: http://terminology.hl7.org/ValueSet/v3-Confidentiality
  - Ontology hosts: OBO Foundry PURLs, NCBO BioPortal, EBI OLS, MeSH, Cellosaurus
  - Repositories: hosts as they appear in contentUrl/publisher fields
"""

import re

# --- Persistent identifiers (rubric 0.a / 5.a) -----------------------------

PID_PATTERNS = {
    "DOI": re.compile(r"(doi\.org/|^doi:|^10\.\d{4,9}/)", re.I),
    "ARK": re.compile(r"(^ark:|/ark:)", re.I),
    "Handle": re.compile(r"(hdl\.handle\.net/|^hdl:)", re.I),
    "PURL": re.compile(r"purl\.(org|obolibrary\.org)/", re.I),
    "w3id": re.compile(r"w3id\.org/", re.I),
    "URN": re.compile(r"^urn:", re.I),
    "IGSN": re.compile(r"igsn\.org/|^igsn:", re.I),
    "CSTR": re.compile(r"cstr\.cn/|^cstr:", re.I),
}


def detect_pid(value):
    """Return the PID scheme name for a string, or None."""
    if not isinstance(value, str):
        return None
    for scheme, pat in PID_PATTERNS.items():
        if pat.search(value):
            return scheme
    return None


# --- Repositories ----------------------------------------------------------

# Specialist (domain) repositories, keyed by hostname fragment.
SPECIALIST_REPOS = {
    "massive.ucsd.edu": "MassIVE (proteomics)",
    "massive-ftp.ucsd.edu": "MassIVE (proteomics)",
    "proteomecentral": "ProteomeXchange (proteomics)",
    "ebi.ac.uk/pride": "PRIDE (proteomics)",
    "ncbi.nlm.nih.gov/geo": "GEO (functional genomics)",
    "ncbi.nlm.nih.gov/sra": "SRA (sequence reads)",
    "trace.ncbi.nlm.nih.gov": "SRA (sequence reads)",
    "ncbi.nlm.nih.gov/gap": "dbGaP (genotype/phenotype)",
    "ebi.ac.uk/ena": "ENA (nucleotide archive)",
    "ebi.ac.uk/biostudies": "BioStudies",
    "empiar": "EMPIAR (EM imaging)",
    "proteinatlas.org": "Human Protein Atlas (imaging)",
    "physionet.org": "PhysioNet (physiologic signals)",
    "openneuro.org": "OpenNeuro (neuroimaging)",
    "idr.openmicroscopy.org": "IDR (imaging)",
    "cellosaurus": "Cellosaurus (cell lines)",
    "addgene.org": "Addgene (plasmids)",
}

# Generalist FAIR repositories.
GENERALIST_REPOS = {
    "dataverse": "Dataverse",
    "zenodo.org": "Zenodo",
    "figshare.com": "Figshare",
    "datadryad.org": "Dryad",
    "osf.io": "OSF",
    "fairhub.io": "FAIRhub",
    "dataverse.lib.virginia.edu": "University of Virginia Dataverse (LibraData)",
}

# Hosts that count as sustainable software archives (1.c score 2).
SOFTWARE_ARCHIVE_HOSTS = {
    "zenodo.org": "Zenodo",
    "softwareheritage.org": "Software Heritage",
    "archive.softwareheritage.org": "Software Heritage",
    "doi.org": "DOI-registered archive",
    "dataverse": "Dataverse",
    "pypi.org": "PyPI",
}

# Mutable code hosting (1.c score 1).
CODE_HOSTS = {
    "github.com": "GitHub",
    "gitlab.com": "GitLab",
    "bitbucket.org": "Bitbucket",
}


def match_host(url_or_name, table):
    """Return (fragment, label) for the first table entry found in the string."""
    if not isinstance(url_or_name, str):
        return None
    low = url_or_name.lower()
    for fragment, label in table.items():
        if fragment in low:
            return fragment, label
    return None


# --- Standard vocabularies / ontologies ------------------------------------

# Hostname fragments whose presence in metadata indicates a term bound to a
# published vocabulary. All are resolvable registries (OBO Foundry, MeSH,
# Cellosaurus, EBI OLS, BioPortal, identifiers.org, UniProt, Ensembl).
ONTOLOGY_HOSTS = {
    "purl.obolibrary.org": "OBO Foundry PURL",
    "meshb.nlm.nih.gov": "MeSH",
    "id.nlm.nih.gov/mesh": "MeSH",
    "cellosaurus.org": "Cellosaurus",
    "ebi.ac.uk/ols": "EBI Ontology Lookup Service",
    "bioportal.bioontology.org": "NCBO BioPortal",
    "identifiers.org": "identifiers.org",
    "uniprot.org": "UniProt",
    "ensembl.org": "Ensembl",
    "snomed.info": "SNOMED CT",
    "loinc.org": "LOINC",
    "ncithesaurus": "NCI Thesaurus",
}

# @context / conformsTo namespaces that are recognized metadata standards.
STANDARD_NAMESPACES = {
    "schema.org": "schema.org",
    "w3id.org/EVI": "EVI (Evidence Graph Ontology)",
    "w3.org/ns/prov": "W3C PROV-O",
    "w3.org/ns/dcat": "W3C DCAT",
    "purl.org/dc/": "Dublin Core",
    "w3id.org/ro/crate": "RO-Crate",
    "mlcommons.org/croissant": "Croissant",
    "bioschemas.org": "Bioschemas",
}

# conformsTo / declared-standard values for which a deterministic programmatic
# validator exists (rubric 6.a).
KNOWN_VALIDATORS = {
    "w3id.org/ro/crate": "RO-Crate profile — rocrate-validator / ro-crate-py",
    "w3id.org/EVI": "EVI — fairscape-cli `rocrate validate` (pydantic models)",
    "json-schema.org": "JSON Schema — any JSON Schema validator (e.g. python-jsonschema)",
    "mlcommons.org/croissant": "Croissant — mlcroissant validator",
    "frictionlessdata.io": "Frictionless — frictionless-py validate",
    "datapackage.org": "Frictionless Data Package — frictionless-py validate",
}

# --- Licenses --------------------------------------------------------------

LICENSE_NAMES = {
    "creativecommons.org/licenses/by/4.0": "CC BY 4.0",
    "creativecommons.org/licenses/by-sa/4.0": "CC BY-SA 4.0",
    "creativecommons.org/licenses/by-nc/4.0": "CC BY-NC 4.0",
    "creativecommons.org/licenses/by-nc-sa/4.0": "CC BY-NC-SA 4.0",
    "creativecommons.org/licenses/by-nc-nd/4.0": "CC BY-NC-ND 4.0",
    "creativecommons.org/publicdomain/zero/1.0": "CC0 1.0",
    "apache.org/licenses/license-2.0": "Apache-2.0",
    "opensource.org/licenses/mit": "MIT",
}

# --- HL7 v3 Confidentiality (rubric 4.d) -----------------------------------
# Code system: http://terminology.hl7.org/CodeSystem/v3-Confidentiality

HL7_CONFIDENTIALITY = {
    "U": "unrestricted",
    "L": "low",
    "M": "moderate",
    "N": "normal",
    "R": "restricted",
    "V": "very restricted",
}


def hl7_confidentiality_code(value):
    """Match a value against HL7 v3-Confidentiality codes or display names."""
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    for code, display in HL7_CONFIDENTIALITY.items():
        if v == code.lower() or v == display:
            return code
    return None


# --- File formats (rubric 6.c) ---------------------------------------------

# Vendor / instrument-native formats that need proprietary software.
# Matched as patterns because crates spell these many ways
# (".d", ".d directory group", "Bruker .d", "raw", ".raw").
PROPRIETARY_FORMAT_PATTERNS = [
    (re.compile(r"(^|\s)\.?d(\s|$)|bruker", re.I), "Bruker .d (mass spec, vendor)"),
    (re.compile(r"^\.?raw$|thermo", re.I), "Thermo .raw (mass spec, vendor)"),
    (re.compile(r"\.?wiff", re.I), "SCIEX .wiff (mass spec, vendor)"),
    (re.compile(r"\.?czi", re.I), "Zeiss CZI (imaging, vendor)"),
    (re.compile(r"\.?nd2", re.I), "Nikon ND2 (imaging, vendor)"),
    (re.compile(r"\.?lif$", re.I), "Leica LIF (imaging, vendor)"),
]


def classify_format(fmt):
    """Return the vendor label if `fmt` is a known proprietary format, else None."""
    for pat, label in PROPRIETARY_FORMAT_PATTERNS:
        if pat.search(fmt):
            return label
    return None
