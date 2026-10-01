"""Crate loading and one-pass aggregation.

A release crate can reference sub-crates whose metadata files hold tens of
thousands of entities, so extraction is a single streaming-style pass: each
sub-crate JSON is parsed, folded into `CrateStats` (counters plus a bounded
set of trimmed sample entities), and released. Criterion extractors read from
the finished `CrateBundle` and never touch the big graphs again.
"""

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .known import ONTOLOGY_HOSTS, STANDARD_NAMESPACES, TERM_PREFIXES, match_host
from .source import resolve_source

# Fields that link an entity into the provenance graph (EVI + PROV spellings).
PROV_LINK_FIELDS = [
    "generatedBy", "prov:wasGeneratedBy",
    "derivedFrom", "prov:wasDerivedFrom", "derivedTo",
    "usedByComputation", "usedBy", "usedByExperiment",
    "usedSoftware", "usedDataset", "usedSample", "usedInstrument",
    "usedTreatment", "usedStain", "usedContainer",
    "generated", "prov:used",
    "inputs", "outputs",
    "https://w3id.org/EVI#inputs", "https://w3id.org/EVI#outputs",
]

ACTIVITY_INPUT_FIELDS = [
    "usedDataset", "usedSample", "usedInstrument", "inputs",
    "https://w3id.org/EVI#inputs", "prov:used",
]
ACTIVITY_OUTPUT_FIELDS = ["generated", "outputs", "https://w3id.org/EVI#outputs"]

HASH_FIELDS = ["md5", "MD5", "sha256", "sha-256", "sha512", "checksum"]

SCHEMA_REF_FIELDS = ["EVI:Schema", "evi:Schema", "hasSchema", "dataSchema"]

SUMMARY_STATS_FIELDS = ["hasSummaryStatistics", "hasSummaryStats"]

SPLIT_NAME_RE = re.compile(r"\b(train(ing)?|test|validation|valid|holdout|hold-out|split)\b", re.I)
_IMAGE_FORMAT_RE = re.compile(r"image/|jpe?g|png|tiff?\b|gif|bmp", re.I)
EXAMPLE_NAME_RE = re.compile(r"\b(example|synthetic)\b", re.I)

_TYPE_TOKENS = {
    "Dataset": "Dataset", "Computation": "Computation", "Software": "Software",
    "Schema": "Schema", "Sample": "Sample", "Instrument": "Instrument",
    "Experiment": "Experiment", "Person": "Person", "Organization": "Organization",
    "BioChemEntity": "BioChemEntity", "Container": "Container",
    "CreativeWork": "CreativeWork", "DefinedTerm": "DefinedTerm",
    # RO-Crate / schema.org / Croissant spellings of "a file of data"
    "File": "Dataset", "DataDownload": "Dataset",
    "FileObject": "Dataset", "FileSet": "Dataset",
    # Croissant's data dictionary: a RecordSet of typed Fields is a schema
    "RecordSet": "Schema", "Field": "Field",
    "SoftwareSourceCode": "Software", "SoftwareApplication": "Software",
}

# Croissant Field.source links a RecordSet back to the file(s) it describes.
CROISSANT_SOURCE_FIELDS = ["fileObject", "fileSet", "distribution"]


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def ids_of(value):
    """@id strings from a ref or list of refs (dicts or bare strings)."""
    out = []
    for v in as_list(value):
        if isinstance(v, dict) and "@id" in v:
            out.append(v["@id"])
        elif isinstance(v, str):
            out.append(v)
    return out


def flatten_document(doc):
    """(root, graph) for any JSON-LD dialect.

    RO-Crate documents already carry a flat ``@graph``; the root is found by
    the caller through the metadata descriptor. Croissant and plain schema.org
    JSON-LD are a single top-level node with nested objects (``distribution``,
    ``recordSet``, ``creator``, ``license`` …). Those nested objects are
    collected into a graph list in document order, without minting ``@id``s
    or rewriting the parents, so the same one-pass aggregation applies.
    """
    graph = doc.get("@graph")
    if isinstance(graph, list):
        return None, graph
    nodes = []

    def walk(value):
        if isinstance(value, dict):
            if "@type" in value:
                nodes.append(value)
            for key, child in value.items():
                if not key.startswith("@"):
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(doc)
    return doc, nodes


def normalize_root(root):
    """Fill the property names the extractors read from their schema.org /
    Croissant synonyms. Only missing values are filled; nothing is removed."""
    if not root.get("author") and root.get("creator"):
        root["author"] = root["creator"]
    pub = root.get("publisher")
    if isinstance(pub, dict):
        root["publisher"] = " ".join(
            str(pub[k]) for k in ("name", "url", "@id") if pub.get(k)) or pub
    if not root.get("identifier"):
        for key in ("@id", "sameAs", "url"):
            for v in ids_of(root.get(key)):
                if re.search(r"doi\.org/|ark:|hdl\.handle\.net|purl\.|w3id\.org|^urn:", v, re.I):
                    root["identifier"] = v
                    break
            if root.get("identifier"):
                break
    return root


def canonical_type(entity):
    """Map an entity's @type (any EVI/prov spelling) to one canonical name."""
    types = [str(t) for t in as_list(entity.get("@type"))]
    if any("ROCrate" in t for t in types):
        return "ROCrate"
    for t in types:
        token = re.split(r"[#/:]", t)[-1]
        if token in _TYPE_TOKENS:
            return _TYPE_TOKENS[token]
    extra = entity.get("additionalType")
    if isinstance(extra, str) and extra in _TYPE_TOKENS:
        return _TYPE_TOKENS[extra]
    return "Other"


def subject_terms(root, graph):
    """Subject terms for the dataset: the root's ``about`` entries plus every
    DefinedTerm entity in the graph, de-duplicated by IRI.

    An ``about`` entry counts when it is (or resolves to) a DefinedTerm, or
    when its IRI is on a recognised ontology host. That covers bare IRIs
    (``"about": "http://id.nlm.nih.gov/mesh/D002477"``), references to graph
    entities, and inline DefinedTerm objects, which an RO-Crate's flat
    ``@graph`` never lists as entities of their own. ``about`` references to
    other local entities (a Dataset, a Person) are not subject terms.
    """
    by_id = {e.get("@id"): e for e in graph if isinstance(e, dict) and e.get("@id")}
    terms, seen = [], set()

    def add(iri, name, source):
        key = iri or name
        if not key or key in seen:
            return
        seen.add(key)
        hit = match_host(iri, ONTOLOGY_HOSTS)
        terms.append({"@id": iri, "name": name, "source": source,
                      "ontology": ONTOLOGY_HOSTS[hit[0]] if hit else None})

    for v in as_list(root.get("about")):
        if isinstance(v, dict):
            iri = v.get("@id") or v.get("identifier") or v.get("url")
            target = {**by_id.get(iri, {}), **v}
        elif isinstance(v, str):
            iri, target = v, by_id.get(v, {})
        else:
            continue
        iri = iri if isinstance(iri, str) else None
        if canonical_type(target) == "DefinedTerm" or match_host(iri, ONTOLOGY_HOSTS):
            add(iri, target.get("name"), "about")
    for e in graph:
        if canonical_type(e) == "DefinedTerm":
            add(e.get("@id"), e.get("name"), "graph")
    return terms


def has_any(entity, fields):
    return any(entity.get(f) for f in fields)


def trim_entity(entity, max_str=400, max_list=5, max_keys=40):
    """Bounded copy of an entity for use as a sample in the presentation."""
    def trim(value, depth=0):
        if isinstance(value, str):
            return value if len(value) <= max_str else value[:max_str] + "…"
        if isinstance(value, list):
            trimmed = [trim(v, depth + 1) for v in value[:max_list]]
            if len(value) > max_list:
                trimmed.append(f"…(+{len(value) - max_list} more)")
            return trimmed
        if isinstance(value, dict):
            if depth >= 2:
                return {"@id": value["@id"]} if "@id" in value else "{…}"
            out = {}
            for i, (k, v) in enumerate(value.items()):
                if i >= max_keys:
                    out["…"] = f"+{len(value) - max_keys} more keys"
                    break
                out[k] = trim(v, depth + 1)
            return out
        return value

    return trim(entity)


@dataclass
class SubCrate:
    name: str
    ark: str
    rel_dir: str            # crate-relative directory, posix
    metadata_rel: str       # crate-relative path to ro-crate-metadata.json
    root: dict = None       # trimmed root entity of the sub-crate
    entity_count: int = 0
    prov_graphs: list = field(default_factory=list)   # crate-relative html paths
    preview: str = None
    datasheets: list = field(default_factory=list)


class CrateStats:
    """Aggregates folded in from every graph. Plain counters and bounded samples."""

    SAMPLE_LIMIT = 5

    def __init__(self):
        self.type_counts = Counter()
        self.entity_total = 0
        self.entity_with_prov_link = 0

        self.dataset_total = 0
        self.dataset_with_prov = 0
        self.dataset_with_contenturl = 0
        self.dataset_embargoed = 0
        self.dataset_with_hash = 0
        self.dataset_with_schema_ref = 0
        self.summary_stats_total = 0
        self.summary_stats_entities = []
        self.summary_stats_ids = set()
        self.dataset_split_names = []          # bounded
        self.dataset_split_count = 0
        self.dataset_image_total = 0           # image-format datasets

        self.software_total = 0
        self.software_with_hash = 0
        self.software_entities = []            # trimmed, bounded

        self.activity_total = 0                # Computation + Experiment
        self.computation_with_software = 0
        self.activity_with_io = 0
        self.activity_with_container = 0
        self.computation_total = 0
        self.experiment_total = 0

        self.dataset_with_remote_url = 0       # http/ftp/s3-style contentUrl
        self.schema_total = 0
        self.formats = Counter()
        self.hosts = Counter()                 # contentUrl "scheme://host" buckets
        self.url_schemes = Counter()           # contentUrl scheme -> dataset count
        self.vocab_hits = Counter()            # ontology-host -> occurrence count
        self.term_namespaces = Counter()       # standard namespace -> terms using it

        self.samples = {}                      # category -> [trimmed entities]

    def add_sample(self, category, entity, limit=None):
        bucket = self.samples.setdefault(category, [])
        if len(bucket) < (limit or self.SAMPLE_LIMIT):
            bucket.append(trim_entity(entity))

    def sample(self, category):
        bucket = self.samples.get(category) or []
        return bucket[0] if bucket else None


_VOCAB_RE = re.compile("|".join(re.escape(h) for h in ONTOLOGY_HOSTS), re.I)
_URL_RE = re.compile(r"^([a-z][a-z0-9+.-]*)://([^/]+)", re.I)


def term_namespace(term):
    """STANDARD_NAMESPACES key for a type or property name written as a full
    IRI (`https://w3id.org/EVI#Dataset`) or a compact one (`prov:Entity`,
    `EVI:Schema`), declared in @context or not. None for bare terms."""
    if not isinstance(term, str) or ":" not in term:
        return None
    if "://" in term:
        hit = match_host(term, STANDARD_NAMESPACES)
        return hit[0] if hit else None
    return TERM_PREFIXES.get(term.split(":", 1)[0].lower())


def _count_term_namespaces(entity, counter):
    for term in [*as_list(entity.get("@type")), *entity]:
        ns = term_namespace(term)
        if ns:
            counter[ns] += 1


class CrateBundle:
    """Everything the section extractors need, loaded once."""

    def __init__(self, root_dir):
        self.root_dir = Path(root_dir)
        self.source = None       # what was loaded (path or URL), for the header
        self.format = "ro-crate"  # ro-crate | croissant | jsonld
        self.meta_path = None
        self.root = {}           # root dataset entity
        self.descriptor = {}     # ro-crate-metadata.json CreativeWork entity
        self.context = {}
        self.persons = []        # Person entities from the root graph
        self.defined_terms = []  # DefinedTerm entities from the root graph
        self.subject_terms = []  # root `about` + DefinedTerms (see subject_terms)
        self.subcrates = []
        self.subcrates_referenced = 0   # stubs in the root graph naming a metadata path
        self.datasheets = []            # crate-relative html paths (root first)
        self.stats = CrateStats()
        self._seen_ids = set()

    # -- loading ------------------------------------------------------------

    @classmethod
    def load(cls, source, progress=None, cache_dir=None):
        """`source` is a crate directory, a metadata file, an http(s) URL, or
        a ``kaggle:``/``hf:`` shortcut (see ``source.resolve_source``)."""
        src = resolve_source(source, cache_dir=cache_dir)
        bundle = cls(src.root_dir)
        bundle.source = src.label
        bundle.format = src.format
        bundle.meta_path = src.meta_path
        say = progress or (lambda msg: None)

        meta_path = src.meta_path
        doc = src.doc
        top, graph = flatten_document(doc)
        bundle.context = doc.get("@context", {})

        if top is None:
            for e in graph:
                types = [str(t) for t in as_list(e.get("@type"))]
                if "CreativeWork" in types and e.get("@id", "").endswith("ro-crate-metadata.json"):
                    bundle.descriptor = e
                    break
            root_id = ids_of(bundle.descriptor.get("about"))
            bundle.root = next(
                (e for e in graph if e.get("@id") in root_id),
                next((e for e in graph if "ROCrate" in str(e.get("@type"))), {}),
            )
        else:
            bundle.root = top
        normalize_root(bundle.root)

        for e in graph:
            ctype = canonical_type(e)
            if ctype == "Person":
                bundle.persons.append(e)
            elif ctype == "DefinedTerm":
                bundle.defined_terms.append(e)
        bundle.subject_terms = subject_terms(bundle.root, graph)

        bundle._discover_subcrates(graph)
        say(f"{src.format} document: {len(graph)} entities, "
            f"{len(bundle.subcrates)} sub-crates found on disk "
            f"({bundle.subcrates_referenced} referenced)")

        bundle._absorb_graph(graph, raw_text=meta_path.read_text(encoding="utf-8"))
        for sub in bundle.subcrates:
            sub_path = bundle.root_dir / sub.metadata_rel
            raw = sub_path.read_text()
            sub_graph = json.loads(raw).get("@graph", [])
            sub.entity_count = len(sub_graph)
            for e in sub_graph:
                if canonical_type(e) == "ROCrate":
                    sub.root = trim_entity(e)
                    break
            bundle._absorb_graph(sub_graph, raw_text=raw)
            say(f"  {sub.rel_dir}: {sub.entity_count} entities")

        bundle._discover_html()
        return bundle

    def _discover_subcrates(self, graph):
        seen_paths = set()
        for e in graph:
            if canonical_type(e) != "ROCrate" or e.get("@id") == self.root.get("@id"):
                continue
            rel = e.get("ro-crate-metadata")
            if not rel:
                continue
            self.subcrates_referenced += 1
            path = (self.root_dir / rel).resolve()
            if not path.exists() or path in seen_paths:
                continue
            seen_paths.add(path)
            rel_posix = Path(rel).as_posix()
            self.subcrates.append(SubCrate(
                name=e.get("name", rel_posix),
                ark=e.get("@id", ""),
                rel_dir=str(Path(rel_posix).parent),
                metadata_rel=rel_posix,
            ))

    def _discover_html(self):
        def rel_globs(directory, pattern):
            return sorted(
                p.relative_to(self.root_dir).as_posix()
                for p in directory.glob(pattern)
            )

        self.datasheets = rel_globs(self.root_dir, "*datasheet*.html")
        for sub in self.subcrates:
            sub_dir = self.root_dir / sub.rel_dir
            sub.datasheets = rel_globs(sub_dir, "*datasheet*.html")
            sub.prov_graphs = (
                rel_globs(sub_dir, "*prov-graph*.html")
                + rel_globs(sub_dir, "*evidence-graph*.html")
            )
            previews = rel_globs(sub_dir, "ro-crate-preview.html")
            sub.preview = previews[0] if previews else None
            self.datasheets += sub.datasheets

    # -- aggregation --------------------------------------------------------

    def _absorb_graph(self, graph, raw_text=None):
        stats = self.stats
        if raw_text:
            for m in _VOCAB_RE.finditer(raw_text):
                stats.vocab_hits[m.group(0).lower()] += 1

        # Croissant links data dictionaries to files from the RecordSet side
        # (Field.source.fileObject), the reverse of EVI's dataset -> Schema.
        schema_covered = set()
        for e in graph:
            if canonical_type(e) == "Schema":
                for f in as_list(e.get("field")):
                    src = f.get("source") if isinstance(f, dict) else None
                    if isinstance(src, dict):
                        for key in CROISSANT_SOURCE_FIELDS:
                            schema_covered.update(ids_of(src.get(key)))

        for e in graph:
            eid = e.get("@id")
            ctype = canonical_type(e)

            # Summary-statistics links are located on every entity type, root
            # ROCrate entities included. This runs before the duplicate-id
            # skip below: a parent crate embeds its own copy of each sub-crate
            # root, and that copy can be a stale snapshot missing the link, so
            # whichever copy actually carries it has to be the one that counts.
            if has_any(e, SUMMARY_STATS_FIELDS):
                key = eid or id(e)
                if key not in stats.summary_stats_ids:
                    stats.summary_stats_ids.add(key)
                    stats.summary_stats_total += 1
                    stats.add_sample("summary_stats", e)
                    if len(stats.summary_stats_entities) < 25:
                        target = next(
                            (ids_of(e.get(f))[0] for f in SUMMARY_STATS_FIELDS
                             if ids_of(e.get(f))), None)
                        stats.summary_stats_entities.append({
                            "@id": eid,
                            "name": e.get("name"),
                            "type": ctype,
                            "target": target,
                        })

            if eid and eid in self._seen_ids:
                continue
            if eid:
                self._seen_ids.add(eid)

            _count_term_namespaces(e, stats.term_namespaces)

            if ctype in ("ROCrate", "CreativeWork") or e is self.root:
                continue
            stats.type_counts[ctype] += 1
            stats.entity_total += 1

            has_prov = has_any(e, PROV_LINK_FIELDS)
            if has_prov:
                stats.entity_with_prov_link += 1

            if ctype == "Dataset":
                self._absorb_dataset(e, has_prov, schema_covered)
            elif ctype in ("Computation", "Experiment"):
                self._absorb_activity(e, ctype)
            elif ctype == "Software":
                stats.software_total += 1
                if has_any(e, HASH_FIELDS):
                    stats.software_with_hash += 1
                    stats.add_sample("hashed_entity", e)
                if len(stats.software_entities) < 15:
                    stats.software_entities.append(trim_entity(e))
            elif ctype == "Schema":
                stats.schema_total += 1
                stats.add_sample("schema", e)
                # a Croissant RecordSet typed cr:Split enumerates the splits
                if any("Split" in str(t) for t in as_list(e.get("dataType"))):
                    stats.dataset_split_count += 1
                    if len(stats.dataset_split_names) < 8:
                        stats.dataset_split_names.append(str(e.get("name", eid)))
            elif ctype == "Sample":
                stats.add_sample("biosample", e)
            elif ctype == "Instrument":
                stats.add_sample("instrument", e)

    def _absorb_dataset(self, e, has_prov, schema_covered=()):
        stats = self.stats
        stats.dataset_total += 1
        if has_prov:
            stats.dataset_with_prov += 1
            stats.add_sample("dataset_with_prov", e)
        if e.get("usedByComputation"):
            stats.add_sample("input_dataset", e)

        url = e.get("contentUrl")
        url_str = " ".join(ids_of(url)) if url else ""
        if url_str:
            stats.dataset_with_contenturl += 1
            m = _URL_RE.match(url_str)
            scheme = m.group(1).lower() if m else \
                (url_str.split(":", 1)[0].lower() if ":" in url_str[:8] else "none")
            stats.url_schemes[scheme] += 1
            if scheme in ("http", "https", "ftp", "ftps", "s3", "gs", "drs"):
                stats.dataset_with_remote_url += 1
            if m:
                stats.hosts[f"{scheme}://{m.group(2).lower()}"] += 1
        if "embargo" in (url_str + str(e.get("description", ""))[:300]).lower():
            stats.dataset_embargoed += 1

        if has_any(e, HASH_FIELDS):
            stats.dataset_with_hash += 1
            stats.add_sample("hashed_entity", e)
        if has_any(e, SCHEMA_REF_FIELDS) or (e.get("@id") in schema_covered):
            stats.dataset_with_schema_ref += 1

        fmt = e.get("format") or e.get("encodingFormat")
        if fmt:
            fmt_strs = [str(f) for f in as_list(fmt)]
            for f in fmt_strs:
                stats.formats[f] += 1
            if any(_IMAGE_FORMAT_RE.search(f) for f in fmt_strs):
                stats.dataset_image_total += 1

        name = str(e.get("name", ""))
        if SPLIT_NAME_RE.search(name):
            stats.dataset_split_count += 1
            if len(stats.dataset_split_names) < 8:
                stats.dataset_split_names.append(name)
        if EXAMPLE_NAME_RE.search(name):
            stats.add_sample("example_dataset", e)

    def _absorb_activity(self, e, ctype):
        stats = self.stats
        stats.activity_total += 1
        if ctype == "Computation":
            stats.computation_total += 1
            stats.add_sample("computation", e)
            if e.get("usedSoftware"):
                stats.computation_with_software += 1
        else:
            stats.experiment_total += 1
            stats.add_sample("experiment", e)
        if e.get("usedContainer"):
            stats.activity_with_container += 1
        if has_any(e, ACTIVITY_INPUT_FIELDS) and has_any(e, ACTIVITY_OUTPUT_FIELDS):
            stats.activity_with_io += 1

    # -- convenience --------------------------------------------------------

    def evidence_graph_links(self):
        """(crate-relative href, display name) for every prov/evidence graph."""
        pairs = []
        for sub in self.subcrates:
            for p in sub.prov_graphs:
                pairs.append({"href": p, "text": f"{sub.name} — {Path(p).name}"})
        return pairs

    def root_text(self, *fields):
        """Concatenated string values of the given root fields."""
        parts = []
        for f in fields:
            v = self.root.get(f)
            if v:
                parts.extend(str(x) for x in as_list(v))
        return " ".join(parts)
