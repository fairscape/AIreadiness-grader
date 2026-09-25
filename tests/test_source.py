"""Non-RO-Crate inputs: Croissant and plain schema.org JSON-LD files, and the
kaggle:/hf: shortcuts, must load through the same pipeline as a crate."""

import json

from aireadiness_evidence.crate import CrateBundle, flatten_document
from aireadiness_evidence.pipeline import build_presentation
from aireadiness_evidence.source import detect_format, expand_shortcut, resolve_source

CROISSANT = {
    "@context": {"@vocab": "https://schema.org/", "cr": "http://mlcommons.org/croissant/",
                 "rai": "http://mlcommons.org/croissant/RAI/", "sc": "https://schema.org/"},
    "@type": "sc:Dataset",
    "name": "Demo",
    "description": "A demo Croissant dataset.",
    "conformsTo": "http://mlcommons.org/croissant/1.0",
    "license": "https://creativecommons.org/licenses/by/4.0/",
    "url": "https://doi.org/10.1234/demo",
    "creator": {"@type": "sc:Person", "name": "J Doe",
                "identifier": "https://orcid.org/0000-0000-0000-0000"},
    "publisher": {"@type": "sc:Organization", "name": "Kaggle", "url": "https://www.kaggle.com/"},
    "rai:dataBiases": "Cell line bias.",
    "distribution": [
        {"@type": "cr:FileObject", "@id": "data.csv", "name": "data.csv",
         "contentUrl": "https://zenodo.org/record/1/files/data.csv",
         "encodingFormat": "text/csv", "sha256": "abc"},
        {"@type": "cr:FileObject", "@id": "img.png", "name": "img.png",
         "contentUrl": "https://zenodo.org/record/1/files/img.png",
         "encodingFormat": "image/png"},
    ],
    "recordSet": [
        {"@type": "cr:RecordSet", "@id": "rs", "name": "records",
         "field": [{"@type": "cr:Field", "@id": "rs/x", "name": "x", "dataType": "sc:Float",
                    "source": {"fileObject": {"@id": "data.csv"}, "extract": {"column": "x"}}}]},
        {"@type": "cr:RecordSet", "@id": "splits", "name": "splits", "dataType": "cr:Split",
         "field": [{"@type": "cr:Field", "@id": "splits/name", "name": "name"}]},
    ],
}


def test_flatten_collects_nested_typed_nodes_without_minting_ids():
    root, graph = flatten_document(CROISSANT)
    assert root is CROISSANT
    ids = [e.get("@id") for e in graph]
    assert "data.csv" in ids and "rs" in ids and "rs/x" in ids
    assert graph[0] is CROISSANT  # the root is itself a typed node
    # nested objects are left in place, not replaced by references
    assert isinstance(CROISSANT["creator"], dict) and "@id" not in CROISSANT["creator"]


def test_detect_format():
    assert detect_format({"@graph": []}) == "ro-crate"
    assert detect_format(CROISSANT) == "croissant"
    assert detect_format({"@context": "https://schema.org/", "@type": "Dataset"}) == "jsonld"


def test_expand_shortcut():
    assert expand_shortcut("kaggle:owner/slug") == \
        "https://www.kaggle.com/datasets/owner/slug/croissant/download"
    assert expand_shortcut("https://www.kaggle.com/datasets/owner/slug") == \
        "https://www.kaggle.com/datasets/owner/slug/croissant/download"
    assert expand_shortcut("hf:org/name") == "https://huggingface.co/api/datasets/org/name/croissant"
    assert expand_shortcut("https://huggingface.co/datasets/org/name") == \
        "https://huggingface.co/api/datasets/org/name/croissant"
    assert expand_shortcut("https://example.org/x.json") == "https://example.org/x.json"


def test_croissant_file_loads_as_bundle(tmp_path):
    f = tmp_path / "metadata.json"
    f.write_text(json.dumps(CROISSANT))
    b = CrateBundle.load(f)
    assert b.format == "croissant"
    assert b.root["name"] == "Demo"
    st = b.stats
    assert st.type_counts["Dataset"] == 2       # FileObjects; the root is not counted
    assert st.schema_total == 2                  # RecordSets
    assert st.dataset_with_schema_ref == 1       # data.csv via Field.source.fileObject
    assert st.dataset_with_contenturl == 2 and st.dataset_with_remote_url == 2
    assert st.dataset_with_hash == 1
    assert st.dataset_image_total == 1           # from encodingFormat
    assert st.dataset_split_count == 1           # cr:Split recordSet
    assert st.formats["text/csv"] == 1
    # root synonyms filled in
    assert b.root["author"]["name"] == "J Doe"
    assert b.root["publisher"].startswith("Kaggle")
    assert b.root["identifier"] == "https://doi.org/10.1234/demo"
    assert [p["name"] for p in b.persons] == ["J Doe"]


def test_directory_with_single_json_file_resolves(tmp_path):
    (tmp_path / "anything.jsonld").write_text(json.dumps(CROISSANT))
    src = resolve_source(tmp_path)
    assert src.meta_path.name == "anything.jsonld" and src.format == "croissant"


def test_presentation_reads_rai_and_flags_format(tmp_path):
    f = tmp_path / "metadata.json"
    f.write_text(json.dumps(CROISSANT))
    p = build_presentation(f, network=False)
    assert p["crate"]["format"] == "croissant"
    assert p["crate"]["format_label"] == "Croissant"
    by_id = {c["id"]: c for s in p["sections"] for c in s["criteria"]}
    assert not any(c.get("error") for c in by_id.values())
    bias = next(i for i in by_id["2.d"]["evidence"] if "rai:dataBiases" in i["label"])
    assert bias["value"] == "Cell line bias."
    assert by_id["1.a"]["evidence"][0]["label"] == "Metadata format"
    assert by_id["1.a"]["estimate"]["score"] == "0"
    assert "Metadata format" not in [i["label"] for i in by_id["0.a"]["evidence"]]
    orcid = next(i for i in by_id["1.d"]["evidence"] if i["label"].startswith("Authors with PIDs"))
    assert orcid["value"] == ["J Doe (https://orcid.org/0000-0000-0000-0000)"]


def test_ro_crate_root_is_not_counted_as_a_dataset(tmp_path):
    crate = {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": [
        {"@id": "ro-crate-metadata.json", "@type": "CreativeWork", "about": {"@id": "./"}},
        {"@id": "./", "@type": "Dataset", "name": "plain crate", "hasPart": [{"@id": "a.csv"}]},
        {"@id": "a.csv", "@type": "File", "name": "a.csv", "encodingFormat": "text/csv"},
    ]}
    (tmp_path / "ro-crate-metadata.json").write_text(json.dumps(crate))
    b = CrateBundle.load(tmp_path)
    assert b.format == "ro-crate" and b.root["name"] == "plain crate"
    assert b.stats.dataset_total == 1 and b.stats.formats["text/csv"] == 1


def _prov_crate(context, dataset_types, link):
    return {"@context": context, "@graph": [
        {"@id": "ro-crate-metadata.json", "@type": "CreativeWork", "about": {"@id": "./"}},
        {"@id": "./", "@type": "Dataset", "name": "crate", "hasPart": [{"@id": "a.csv"}]},
        {"@id": "a.csv", "@type": dataset_types, "name": "a.csv", link: {"@id": "#run"}},
    ]}


def test_undeclared_prov_prefix_counts_like_evi(tmp_path):
    """`prov:` terms with no `prov` in @context still mean PROV-O, and PROV-O
    earns the same 6.a standard + validator credit as a declared EVI crate."""
    from aireadiness_evidence.sections import computability as c

    def facts_for(name, crate):
        d = tmp_path / name
        d.mkdir()
        (d / "ro-crate-metadata.json").write_text(json.dumps(crate))
        b = CrateBundle.load(d)
        raw = {"descriptor_conforms": [], "root_conforms": [], "context": b.context,
               "term_namespaces": dict(b.stats.term_namespaces), "schema_total": 0,
               "vocab_hits": {}, "formats": {}}
        return c.transform_6a(None, raw)

    ro = "https://w3id.org/ro/crate/1.2/context"
    prov = facts_for("prov", _prov_crate(ro, ["Dataset", "prov:Entity"],
                                         "prov:wasGeneratedBy"))
    evi = facts_for("evi", _prov_crate([ro, {"EVI": "https://w3id.org/EVI#"}],
                                       ["Dataset", "https://w3id.org/EVI#Dataset"],
                                       "generatedBy"))
    assert prov["used_namespaces"] == {"W3C PROV-O": 2}
    assert "W3C PROV-O" in prov["standards"]
    assert "EVI (Evidence Graph Ontology)" in evi["standards"]
    assert any(v.startswith("PROV-O") for v in prov["validators"])
    assert any(v.startswith("EVI") for v in evi["validators"])
