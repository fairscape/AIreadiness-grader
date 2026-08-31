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

from .known import ONTOLOGY_HOSTS

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
}


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


class CrateBundle:
    """Everything the section extractors need, loaded once."""

    def __init__(self, root_dir):
        self.root_dir = Path(root_dir)
        self.root = {}           # root dataset entity
        self.descriptor = {}     # ro-crate-metadata.json CreativeWork entity
        self.context = {}
        self.persons = []        # Person entities from the root graph
        self.defined_terms = []  # DefinedTerm entities from the root graph
        self.subcrates = []
        self.subcrates_referenced = 0   # stubs in the root graph naming a metadata path
        self.datasheets = []            # crate-relative html paths (root first)
        self.stats = CrateStats()
        self._seen_ids = set()

    # -- loading ------------------------------------------------------------

    @classmethod
    def load(cls, root_dir, progress=None):
        bundle = cls(root_dir)
        say = progress or (lambda msg: None)

        meta_path = bundle.root_dir / "ro-crate-metadata.json"
        doc = json.loads(meta_path.read_text())
        graph = doc.get("@graph", [])
        bundle.context = doc.get("@context", {})

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

        for e in graph:
            ctype = canonical_type(e)
            if ctype == "Person":
                bundle.persons.append(e)
            elif ctype == "DefinedTerm":
                bundle.defined_terms.append(e)

        bundle._discover_subcrates(graph)
        say(f"root graph: {len(graph)} entities, "
            f"{len(bundle.subcrates)} sub-crates found on disk "
            f"({bundle.subcrates_referenced} referenced)")

        bundle._absorb_graph(graph, raw_text=meta_path.read_text())
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

            if ctype in ("ROCrate", "CreativeWork"):
                continue
            stats.type_counts[ctype] += 1
            stats.entity_total += 1

            has_prov = has_any(e, PROV_LINK_FIELDS)
            if has_prov:
                stats.entity_with_prov_link += 1

            if ctype == "Dataset":
                self._absorb_dataset(e, has_prov)
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
            elif ctype == "Sample":
                stats.add_sample("biosample", e)
            elif ctype == "Instrument":
                stats.add_sample("instrument", e)

    def _absorb_dataset(self, e, has_prov):
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
        if has_any(e, SCHEMA_REF_FIELDS):
            stats.dataset_with_schema_ref += 1

        fmt = e.get("format")
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
