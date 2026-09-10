"""Tests for fairscape-improve (aireadiness_improve).

Python side: the page renders, every root field in the catalogue is a real
fairscape_models field, embedded JSON is script-safe.
JS side (skipped without node): applyEdits + the schema validator
round-trip through the pydantic models.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from aireadiness_improve import cli, fields, schemas

HERE = Path(__file__).parent
CORE_JS = Path(cli.__file__).parent / "templates" / "improve.js"

CRATE = {
    "@context": {"@vocab": "https://schema.org/", "evi": "https://w3id.org/EVI#"},
    "@graph": [
        {"@id": "ro-crate-metadata.json", "@type": "CreativeWork",
         "conformsTo": {"@id": "https://w3id.org/ro/crate/1.2"},
         "about": {"@id": "ark:59853/rocrate-demo-000"}},
        {"@id": "ark:59853/rocrate-demo-000", "@type": ["Dataset", "https://w3id.org/EVI#ROCrate"],
         "name": "demo", "description": "Nextflow run", "keywords": ["demo"], "version": "1.0",
         "author": "Pipeline", "license": "https://spdx.org/licenses/MIT", "datePublished": "2026-09-03",
         "hasPart": [{"@id": "ark:59853/dataset-a"}, {"@id": "ark:59853/software-s"}, {"@id": "ark:59853/computation-c"}]},
        {"@id": "ark:59853/dataset-a", "@type": ["prov:Entity", "https://w3id.org/EVI#Dataset"],
         "name": "a.tsv", "author": "Pipeline", "description": "a tab-separated table", "datePublished": "2026-09-03",
         "keywords": ["demo"], "format": "tsv", "contentUrl": "a/a.tsv", "md5": "d41d8cd98f00b204e9800998ecf8427e",
         "generatedBy": [{"@id": "ark:59853/computation-c"}]},
        {"@id": "ark:59853/software-s", "@type": ["prov:Entity", "https://w3id.org/EVI#Software"],
         "name": "tool", "author": "Pipeline", "description": "a python script", "format": "py",
         "contentUrl": "https://github.com/example/tool"},
        {"@id": "ark:59853/computation-c", "@type": ["prov:Activity", "https://w3id.org/EVI#Computation"],
         "name": "run", "description": "ran the tool once", "runBy": "Pipeline", "dateCreated": "2026-09-03",
         "usedSoftware": [{"@id": "ark:59853/software-s"}], "generated": [{"@id": "ark:59853/dataset-a"}]},
    ],
}

fairscape_models = pytest.importorskip("fairscape_models")


def test_catalogue_props_are_model_fields():
    from fairscape_models.rocrate import ROCrateMetadataElem
    props = set(ROCrateMetadataElem.model_json_schema()["properties"])
    unknown = [f["prop"] for f in fields.catalogue() if f["entity"] == "root" and f["prop"] not in props]
    assert unknown == []


def test_every_criterion_has_fields_or_a_note():
    from aireadiness_evidence.rubric import load_rubric
    cat = fields.catalogue()
    for cid in load_rubric()["criteria"]:
        primary, related = fields.props_for_criterion(cid, cat)
        assert primary or related or cid in fields.OUT_OF_SCOPE_NOTES, cid


def test_render_generic_and_embedded(tmp_path):
    html = cli.render_improve()
    assert "AI-Ready Improvements" in html
    assert 'id="data-crate">null<' in html
    html = cli.render_improve(crate=CRATE, crate_label="x")
    assert "ark:59853/rocrate-demo-000" in html
    assert "</script>" not in json.dumps(CRATE) or "<\\/" in html
    out = tmp_path / "page.html"
    assert cli.main([str(_write_crate(tmp_path)), "-o", str(out), "-q"]) == 0
    assert out.exists() and out.stat().st_size > 100_000


def test_embed_json_is_script_safe():
    assert "</" not in str(cli._embed_json({"x": "</script><script>alert(1)</script>"}))


def test_schemas_come_from_pydantic():
    s = schemas.build_schemas()
    assert "about" in s["root"]["properties"]        # newer than json-schemas/*.json
    assert s["software"]["additionalProperties"] is True


def _write_crate(tmp_path):
    d = tmp_path / "crate"
    d.mkdir(exist_ok=True)
    (d / "ro-crate-metadata.json").write_text(json.dumps(CRATE))
    return d


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
def test_js_edits_validate_in_pydantic():
    from fairscape_models.rocrate import ROCrateV1_2, ROCrateMetadataElem
    from fairscape_models.software import Software
    s = schemas.build_schemas()
    edits = {"root": {"confidentialityLevel": "unrestricted", "about": [{"@id": "http://purl.obolibrary.org/obo/CL_0000000"}],
                      "rai:dataCollectionType": ["Secondary Data Analysis"]},
             "software": {"ark:59853/software-s": {"containerImage": "docker.io/x/y:1", "codeRepository": "https://doi.org/10.5281/zenodo.1"}}}
    script = f"""
      const I = require({json.dumps(str(CORE_JS))});
      const doc = I.applyEdits({json.dumps(CRATE)}, {json.dumps(edits)});
      const root = I.findRoot(doc['@graph']).root;
      const errs = I.validate({json.dumps(s["root"])}, root);
      const est = I.estimateAll(I.loadCrate(doc), {{}});
      console.log(JSON.stringify({{doc, errs, est4d: est['4.d'].score, est1c: est['1.c'].score, est0c: est['0.c'].score}}));
    """
    out = json.loads(subprocess.check_output(["node", "-e", script], text=True))
    assert out["errs"] == []
    assert out["est4d"] == 2 and out["est1c"] == 2 and out["est0c"] == 2
    ROCrateV1_2.model_validate(json.loads(json.dumps(out["doc"])))
    graph = out["doc"]["@graph"]
    ROCrateMetadataElem.model_validate(graph[1])
    Software.model_validate(graph[3])
    assert graph[3]["containerImage"] == "docker.io/x/y:1"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
def test_js_validator_flags_wrong_shape():
    s = schemas.build_schemas()
    script = f"""
      const I = require({json.dumps(str(CORE_JS))});
      const root = Object.assign({{}}, {json.dumps(CRATE["@graph"][1])}, {{"rai:dataCollectionType": "not a list", deidentified: "yes"}});
      console.log(JSON.stringify(I.validate({json.dumps(s["root"])}, root).map(e => e.path)));
    """
    paths = json.loads(subprocess.check_output(["node", "-e", script], text=True))
    assert "/deidentified" in paths
