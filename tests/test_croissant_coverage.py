"""Croissant-specific evidence: what dataset authors actually write (SPDX
license ids, RAI fields, MeSH keywords, typed Fields, files inside a repo)
must reach the criteria that ask for it."""

import copy
import json

from aireadiness_evidence.crate import CrateBundle
from aireadiness_evidence.known import spdx_license
from aireadiness_evidence.sections import (
    characterization, ethics, explainability, fairness, provenance,
)

BASE = {
    "@context": {"@vocab": "https://schema.org/", "cr": "http://mlcommons.org/croissant/",
                 "rai": "http://mlcommons.org/croissant/RAI/", "sc": "https://schema.org/"},
    "@type": "sc:Dataset",
    "name": "Demo",
    "description": "A demo Croissant dataset.",
    "conformsTo": "http://mlcommons.org/croissant/1.0",
    "distribution": [
        {"@type": "cr:FileObject", "@id": "repo", "name": "repo",
         "contentUrl": "https://github.com/org/repo/", "encodingFormat": "git+https",
         "sha256": "abc"},
        {"@type": "cr:FileSet", "@id": "csvs", "name": "csvs", "containedIn": {"@id": "repo"},
         "encodingFormat": "text/csv", "includes": "data/*.csv"},
    ],
    "recordSet": [{"@type": "cr:RecordSet", "@id": "empty", "name": "empty"}],
}


def load(tmp_path, **changes):
    doc = copy.deepcopy(BASE)
    doc.update(changes)
    f = tmp_path / "metadata.json"
    f.write_text(json.dumps(doc))
    return CrateBundle.load(f)


class Ctx:
    """The slice of the pipeline context the extractors touch, offline."""

    class Net:
        def __getattr__(self, name):
            return lambda *a, **k: {"checked": False, "matches": []}

    def __init__(self, bundle):
        self.bundle = bundle
        self.net = self.Net()


def run(module, cid, bundle):
    key = cid.replace(".", "")
    ctx = Ctx(bundle)
    facts = getattr(module, f"transform_{key}")(ctx, getattr(module, f"extract_{key}")(ctx))
    return facts, getattr(module, f"estimate_{key}")(facts)


def test_spdx_license_ids():
    assert spdx_license("cc-by-sa-4.0") == (
        "CC-BY-SA-4.0", "https://spdx.org/licenses/CC-BY-SA-4.0.html")
    assert spdx_license("CC BY 4.0")[0] == "CC-BY-4.0"
    assert spdx_license("mit")[0] == "MIT"
    assert spdx_license("odc-by")[0] == "ODC-By-1.0"
    assert spdx_license("other") is None
    assert spdx_license("Mixed, per record") is None


def test_spdx_license_is_machine_readable(tmp_path):
    facts, est = run(fairness, "0.d", load(tmp_path, license="cc-by-sa-4.0"))
    assert facts["license_machine_readable"] and facts["license_spdx"] == "CC-BY-SA-4.0"
    assert est["score"] == "2"
    _, est = run(fairness, "0.d", load(tmp_path, license="other"))
    assert est["score"] == "1"


def test_empty_recordset_is_not_a_schema(tmp_path):
    b = load(tmp_path)
    assert b.stats.schema_total == 0 and b.stats.empty_recordsets == 1
    assert run(characterization, "2.c", b)[1]["score"] == "0"


def test_typed_fields_count_as_schema_and_bindings(tmp_path):
    fields = [{"@type": "cr:Field", "@id": "rs/a", "name": "a", "dataType": "sc:Text"},
              {"@type": "cr:Field", "@id": "rs/g", "name": "g", "dataType": "wd:Q48277"}]
    rs = [{"@type": "cr:RecordSet", "@id": "rs", "name": "rs", "field": fields}]
    b = load(tmp_path, recordSet=rs)
    assert b.stats.schema_total == 1 and b.stats.field_total == 2
    assert dict(b.stats.field_bindings) == {"Wikidata": 1}
    assert run(characterization, "2.c", b)[1]["score"] == "2"

    rs[0]["field"] = fields[:1]
    assert run(characterization, "2.c", load(tmp_path, recordSet=rs))[1]["score"] == "1"


def test_mesh_keyword_is_a_subject_term_but_not_a_field_binding(tmp_path):
    rs = [{"@type": "cr:RecordSet", "@id": "rs", "name": "rs",
           "field": [{"@type": "cr:Field", "@id": "rs/a", "name": "a", "dataType": "sc:Text"}]}]
    b = load(tmp_path, recordSet=rs,
             keywords=["safety", "http://id.nlm.nih.gov/mesh/D012449", "MeSH:D001185"])
    iris = {t["@id"] for t in b.subject_terms}
    assert iris == {"http://id.nlm.nih.gov/mesh/D012449", "http://id.nlm.nih.gov/mesh/D001185"}
    assert run(characterization, "2.a", b)[1]["score"] == "2"
    # a dataset-level keyword describes the dataset, not a data element
    assert run(characterization, "2.c", b)[1]["score"] == "1"


def test_fileset_inherits_url_and_hash_from_its_container(tmp_path):
    st = load(tmp_path).stats
    assert st.dataset_with_contenturl == 2 and st.dataset_url_inherited == 1
    assert st.dataset_with_hash == 2 and st.dataset_hash_inherited == 1


def test_rai_key_spellings_are_normalized(tmp_path):
    b = load(tmp_path, **{"rai:dataCollectionTimeFrame": "2022",
                          "cr:RAI/dataBiases": "Rater pool skews young."})
    assert b.root["rai:dataCollectionTimeframe"] == "2022"
    assert b.root["rai:dataBiases"] == "Rater pool skews young."


def test_rai_annotation_and_processing_fields_reach_criteria(tmp_path):
    steps = "Raw dialogs were deduplicated, then each item was rated by 123 raters " * 2
    b = load(tmp_path, **{
        "rai:dataCollectionRawData": "Sampled from an 8K-conversation corpus.",
        "rai:dataAnnotationProtocol": steps,
        "rai:dataAnnotationAnalysis": "19 raters were filtered out for low quality.",
        "rai:annotatorDemographics": "57 women, 47 men.",
        "rai:dataAnnotationPlatform": "Crowdworkers with a task-specific UI.",
        "rai:dataNotIntendedUseCases": "Not for training a classifier.",
        "rai:dataUseCases": "Safety evaluation benchmark.",
        "rai:personalSensitiveInformation": "Rater gender, race and age group, keyed by a numeric id.",
    })
    assert run(provenance, "1.a", b)[1]["score"] == "1"
    assert run(provenance, "1.b", b)[1]["score"] == "1"
    facts, _ = run(characterization, "2.e", b)
    assert "Annotation analysis" in facts["qc_fields"] and "filtered" in facts["qc_hits"]
    facts, _ = run(characterization, "2.d", b)
    assert facts["annotators"]
    facts, _ = run(explainability, "3.a", b)
    assert {"Annotation"} <= set(facts["populated"])
    assert run(explainability, "3.b", b)[1]["score"] == "2"
    assert run(ethics, "4.d", b)[1]["score"] == "1"


def test_ror_ids_and_citeas_authors(tmp_path):
    cite = "@article{x,\n  title={T},\n  author={Aroyo, Lora and Serapio-Garc{\\'\\i}a, Gregory},\n  year={2024}\n}"
    b = load(tmp_path, creator=[{"@type": "sc:Organization", "@id": "https://ror.org/00njsd438",
                                 "name": "Google"}], citeAs=cite)
    facts, est = run(provenance, "1.d", b)
    assert facts["with_pid"] and not facts["free_text"] and est["score"] == "2"
    assert facts["cite_authors"] == ["Lora Aroyo", "Gregory Serapio-Garcia"]
    _, est = run(provenance, "1.d", load(tmp_path, citeAs=cite))
    assert est["score"] == "1"
