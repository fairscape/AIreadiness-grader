# Outside examples

Third-party JSON-LD fetched from the public web, to test how far
`aireadiness_evidence` gets on metadata that nobody wrote for FAIRSCAPE.

Nothing here is ours. Every directory holds one upstream document under its
natural filename plus a `SOURCE.url` recording where it came from. Where the
natural name is not `ro-crate-metadata.json`, a symlink of that name sits next
to it — the loader hard-codes that filename, so without the symlink the CLI
refuses to start (see NOTES.md, break #0).

## Corpus

| Directory | Family | What it is |
| --- | --- | --- |
| `rocrate-py-testdata` | RO-Crate 1.2 | ro-crate-py's own test crate; `File` + `Dataset` + `ComputationalWorkflow` |
| `rocrate-paper-2021` | RO-Crate 1.1 | crate accompanying the RO-Crate paper; 200 entities, `@base`, SPAR/pso `DefinedTerm`s, `Role` reification |
| `workflowhub-1078-snapatac2` | Workflow RO-Crate 1.3 | live WorkflowHub export, Galaxy workflow, Bioschemas `ComputationalWorkflow` + `FormalParameter` |
| `runcrate-revsort-provenance` | Provenance Run Crate | runcrate's minimal cwltool crate; 3 `CreateAction`s |
| `wrroc-compss` | Workflow Run Crate | COMPSs run on MareNostrum4; 610 `File`s, 55 `SoftwareSourceCode` |
| `wrroc-autosubmit` | Workflow Run Crate | Autosubmit hydrology run; 67 `File`s, 24 `FormalParameter` |
| `wrroc-snakemake-crcc` | Workflow Run Crate | Snakemake image-conversion run (fair-crcc) |
| `wrroc-wfexs-nfcore-rnaseq` | Provenance Run Crate | WfExS run of nf-core/rnaseq; 856 entities, 279 `sha256`, 66 `ContainerImage` |
| `croissant-titanic` | Croissant 1.0 | CSV table, 3 `RecordSet`s / 19 `Field`s |
| `croissant-movielens` | Croissant 1.0 | multi-file with joins across 7 `FileObject`s |
| `croissant-bigcode-the-stack` | Croissant 1.0 + RAI | carries the RAI extension: `rai:dataCollection`, `rai:dataBiases`, `rai:dataLimitations`, `rai:personalSensitiveInformation`, … |
| `croissant-hf-mnist` | Croissant 1.0 | live Hugging Face `/croissant` API output |
| `datacite-dryad` | schema.org | DataCite content negotiation on a Dryad DOI |
| `dataverse-harvard` | schema.org | Harvard Dataverse `exporter=schema.org`; 3 `DataDownload` |
| `zenodo-record-3541888` | schema.org | Zenodo `application/ld+json`; typed `ScholarlyArticle`, not `Dataset` |
| `esip-sos-full` | schema.org + PROV | science-on-schema.org reference doc; `prov:wasGeneratedBy`, `spdx:Checksum` |
| `esip-sos-astromaterials` | schema.org + QUDT | 20 `PropertyValue` under `variableMeasured`, QUDT units, ODM2 `DefinedTerm`s |
| `bioschemas-nanocommons` | Bioschemas Dataset 1.0 | profile-conformant release example |
| `bioschemas-wikipathways` | Bioschemas Dataset 1.0 | minimal release example |
| `physionet-mimic3-demo` | schema.org (medical) | JSON-LD scraped from the MIMIC-III Demo landing page |
| `cedar-instance` | CEDAR | CEDAR template instance; PAV/OSLC `@context`, no `@type` on the instance |
| `ogc-prov-llm` | PROV-O | OGC building-block example: an LLM inference activity |
| `ogc-prov-entity-timeline` | PROV-O | OGC building-block example: entity revision chain |

## Reproducing

```sh
./fetch.sh            # re-download everything (network)
./run_grader.sh       # run fairscape-evidence over each; writes results/
python3 summarize.py --detail   # per-example outcome table
python3 analyze_shape.py overview|types|fields   # structural census, grader-independent
python3 probe_wrap.py # diagnostic for break #1 (see NOTES.md)
```

`results/` is regenerable output, not source data.
