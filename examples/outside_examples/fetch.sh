#!/usr/bin/env bash
# Re-fetch the outside JSON-LD corpus. Run from this directory: ./fetch.sh
# Every example lands in <slug>/ with the payload under its NATURAL filename.
# Where that name is not ro-crate-metadata.json, a symlink of that name is
# added so `fairscape-evidence <slug>/` can be pointed at the directory at all.
set -u
UA="fairscape-grader-example-fetch/1.0 (+https://github.com/fairscape)"

get() {  # get <slug> <filename> <url>
  mkdir -p "$1"
  if curl -sSf -m 60 -L -A "$UA" -H "Accept: application/ld+json, application/json" \
       -o "$1/$2" "$3"; then
    printf '  ok   %-34s %8s bytes\n' "$1" "$(wc -c <"$1/$2")"
    printf '%s\n' "$3" > "$1/SOURCE.url"
    [ "$2" = "ro-crate-metadata.json" ] || \
      ln -sf "$2" "$1/ro-crate-metadata.json"
  else
    printf '  FAIL %-34s %s\n' "$1" "$3"
  fi
}

get_embedded() {  # get_embedded <slug> <filename> <page-url>  -- pull <script type=ld+json>
  mkdir -p "$1"
  curl -sSf -m 60 -L -A "$UA" "$3" | python3 -c '
import sys, re, json
html = sys.stdin.read()
blocks = re.findall(r"<script type=\"application/ld\+json\">(.*?)</script>", html, re.S)
if not blocks:
    sys.exit("no JSON-LD block")
json.dump(json.loads(blocks[0]), sys.stdout, indent=2)
' > "$1/$2" && {
    printf '  ok   %-34s %8s bytes (embedded)\n' "$1" "$(wc -c <"$1/$2")"
    printf '%s\n' "$3" > "$1/SOURCE.url"
    ln -sf "$2" "$1/ro-crate-metadata.json"
  } || printf '  FAIL %-34s %s\n' "$1" "$3"
}

RO=https://raw.githubusercontent.com/ResearchObject
WRROC=$RO/workflow-run-crate/main/docs/examples
CR=https://raw.githubusercontent.com/mlcommons/croissant/main/datasets/1.0

echo "-- RO-Crate --"
get rocrate-py-testdata          ro-crate-metadata.json "$RO/ro-crate-py/master/test/test-data/read_crate/ro-crate-metadata.json"
get rocrate-paper-2021           ro-crate-metadata.json "$RO/2021-packaging-research-artefacts-with-ro-crate/main/ro-crate-metadata.json"
get workflowhub-1078-snapatac2   ro-crate-metadata.json "https://workflowhub.eu/workflows/1078/ro_crate_metadata"
get runcrate-revsort-provenance  ro-crate-metadata.json "$RO/runcrate/main/tests/data/revsort-provenance-crate-minimal/ro-crate-metadata.json"
get wrroc-compss                 ro-crate-metadata.json "$WRROC/COMPSs/COMPSs_RO-Crate_62ac6a22-40f2-4af9-b65a-b68279ebe48e/ro-crate-metadata.json"
get wrroc-autosubmit             ro-crate-metadata.json "$WRROC/autosubmit/auto-mhm-test-domains/ro-crate-metadata.json"
get wrroc-snakemake-crcc         ro-crate-metadata.json "$WRROC/snakemake/crcc-img-convert/fair-crcc-img-convert-run/ro-crate-metadata.json"
get wrroc-wfexs-nfcore-rnaseq    ro-crate-metadata.json "$WRROC/WfExS-backend/nfcore-rnaseq_provenance/ro-crate-metadata.json"

echo "-- Croissant --"
get croissant-titanic            croissant.json "$CR/titanic/metadata.json"
get croissant-bigcode-the-stack  croissant.json "$CR/bigcode-the-stack/metadata.json"
get croissant-movielens          croissant.json "$CR/movielens/metadata.json"
get croissant-hf-mnist           croissant.json "https://huggingface.co/api/datasets/ylecun/mnist/croissant"

echo "-- schema.org / repositories --"
get datacite-dryad               schemaorg.jsonld "https://api.datacite.org/dois/10.5061/dryad.8515"
get dataverse-harvard            schemaorg.jsonld "https://dataverse.harvard.edu/api/datasets/export?exporter=schema.org&persistentId=doi:10.7910/DVN/OMV93V"
get zenodo-record-3541888        schemaorg.jsonld "https://zenodo.org/api/records/3541888"
get esip-sos-full                dataset.jsonld "https://raw.githubusercontent.com/ESIPFed/science-on-schema.org/master/examples/dataset/full.jsonld"
get esip-sos-astromaterials      dataset.jsonld "https://raw.githubusercontent.com/ESIPFed/science-on-schema.org/master/examples/dataset/variableMeasured_AstroMaterials_analysis.jsonld"

echo "-- Bioschemas / biomedical --"
get bioschemas-nanocommons       dataset.jsonld "https://raw.githubusercontent.com/BioSchemas/specifications/master/Dataset/examples/1.0-RELEASE/nanocommons.json"
get bioschemas-wikipathways      dataset.jsonld "https://raw.githubusercontent.com/BioSchemas/specifications/master/Dataset/examples/1.0-RELEASE/wikipathways.json"
get cedar-instance               cedar-instance.jsonld "https://raw.githubusercontent.com/metadatacenter/cedar-artifact-library/master/src/test/resources/instances/SimpleInstance.json"
get_embedded physionet-mimic3-demo schemaorg.jsonld "https://physionet.org/content/mimiciii-demo/1.4/"

echo "-- PROV --"
get ogc-prov-llm                 prov.jsonld "https://raw.githubusercontent.com/ogcincubator/bblock-prov-schema/master/_sources/prov/examples/example-llm.json"
get ogc-prov-entity-timeline     prov.jsonld "https://raw.githubusercontent.com/ogcincubator/bblock-prov-schema/master/_sources/prov/examples/example-entity-timeline.json"

echo "done."
