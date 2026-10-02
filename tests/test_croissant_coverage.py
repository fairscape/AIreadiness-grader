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


# --- standard-vocabulary provenance, statistics, security, datasheets ------

def test_prov_activities_count_as_steps_with_software(tmp_path):
    release = {"@type": ["prov:SoftwareAgent", "sc:SoftwareApplication"],
               "@id": "https://pypi.org/project/x/1.0/", "name": "x 1.0",
               "downloadUrl": "https://files.pythonhosted.org/x-1.0.whl"}
    acts = [
        {"@type": "prov:Activity", "@id": "act/collect", "name": "collect",
         "prov:wasAssociatedWith": {"@type": "prov:Person", "name": "A"}},
        {"@type": "prov:Activity", "@id": "act/compose", "name": "compose",
         "prov:used": [{"@id": "raw"}], "prov:wasAssociatedWith": release},
    ]
    dist = [{"@type": "cr:FileObject", "@id": "raw", "name": "raw", "sha256": "a",
             "contentUrl": "https://zenodo.org/r/1/raw", "prov:wasGeneratedBy": {"@id": "act/collect"}},
            {"@type": "cr:FileObject", "@id": "out", "name": "out", "sha256": "b",
             "contentUrl": "https://zenodo.org/r/1/out", "prov:wasGeneratedBy": {"@id": "act/compose"}}]
    b = load(tmp_path, distribution=dist, recordSet=[], **{"prov:wasGeneratedBy": acts})
    st = b.stats
    assert (st.computation_total, st.experiment_total) == (1, 1)   # software vs person
    assert st.computation_with_software == 1 and st.activity_with_io == 1
    assert st.dataset_with_prov == 2
    assert run(provenance, "1.b", b)[1]["score"] == "2"
    assert run(provenance, "1.c", b)[1]["score"] == "2"            # PyPI release
    # a provenance agent is not a file of the deposit
    assert run(explainability, "3.c", b)[1]["score"] == "2"


def test_ro_crate_style_types_win_over_prov_activity(tmp_path):
    from aireadiness_evidence.crate import canonical_type
    assert canonical_type({"@type": ["prov:Activity", "https://w3id.org/EVI#Experiment"]}) \
        == "Experiment"


def test_derived_from_sources_are_not_deposit_files(tmp_path):
    b = load(tmp_path, **{"prov:wasDerivedFrom": [
        {"@type": "sc:Dataset", "@id": "https://example.org/src", "name": "src"}]})
    assert b.stats.dataset_total == 2            # repo + csvs only
    assert run(provenance, "1.a", b)[1]["score"] == "1"


def test_croissant_statistics_annotations(tmp_path):
    field = {"@type": "cr:Field", "@id": "rs/sev", "name": "sev", "dataType": "sc:Integer",
             "annotation": [{"@type": "cr:Field", "@id": "rs/sev/max", "value": 3,
                             "equivalentProperty": "sc:maxValue"},
                            {"@id": "rs/sev/mean", "value": 2.2, "dataType": "ddi-stats:7975ed0"}]}
    rs = [{"@type": "cr:RecordSet", "@id": "rs", "name": "rs", "field": [field],
           "annotation": [{"@type": "cr:Field", "@id": "rs/count", "value": 10,
                           "dataType": "wd:Q4049983"}]}]
    b = load(tmp_path, recordSet=rs, **{"rai:dataCollectionMissingData": "NULL only."})
    assert b.stats.summary_stats_total == 3
    assert b.stats.field_total == 1 and not b.stats.field_bindings  # stats aren't bindings
    assert run(characterization, "2.b", b)[1]["score"] == "2"


def test_hl7_label_through_dct_access_rights(tmp_path):
    term = {"@id": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality#M",
            "@type": "sc:DefinedTerm", "termCode": "M"}
    facts, est = run(ethics, "4.d", load(tmp_path, **{"dct:accessRights": term}))
    assert facts["hl7_code"] == "M" and est["score"] == "2"
    _, est = run(ethics, "4.d", load(tmp_path, **{"dct:accessRights": "Open access"}))
    assert est["score"] == "1"


def test_subjectof_datasheet_link(tmp_path):
    b = load(tmp_path, subjectOf=[
        {"@type": "sc:CreativeWork", "name": "Dataset README (datasheet)",
         "url": "https://zenodo.org/records/1/files/README.md"},
        {"@type": "sc:ScholarlyArticle", "name": "Paper", "url": "https://arxiv.org/abs/1"}])
    assert b.datasheets == ["https://zenodo.org/records/1/files/README.md"]
