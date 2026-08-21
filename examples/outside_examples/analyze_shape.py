#!/usr/bin/env python3
"""Structural census of the corpus, independent of the grader.

Reports per example: whether it is a flattened @graph document, how the root
is expressed, the @type tokens present, and which of the field names the
grader looks for actually occur.
"""
import json, pathlib, collections, sys

# fields aireadiness_evidence.crate looks for, plus the spellings it does not
GRADER_FIELDS = ["contentUrl", "format", "md5", "sha256", "generatedBy",
                 "usedByComputation", "usedSoftware", "usedDataset",
                 "EVI:Schema", "hasSummaryStatistics"]
OTHER_FIELDS = ["encodingFormat", "contentSize", "sha512", "object", "result",
                "instrument", "distribution", "recordSet", "field", "isBasedOn",
                "prov:wasGeneratedBy", "wasGeneratedBy", "wasDerivedFrom",
                "conformsTo", "variableMeasured", "measurementTechnique",
                "license", "creator", "author", "citation", "keywords"]

def walk(node, seen_types, seen_keys):
    if isinstance(node, dict):
        for t in (node.get("@type") if isinstance(node.get("@type"), list)
                  else [node.get("@type")]):
            if isinstance(t, str):
                seen_types[t] += 1
        for k, v in node.items():
            seen_keys[k] += 1
            walk(v, seen_types, seen_keys)
    elif isinstance(node, list):
        for v in node:
            walk(v, seen_types, seen_keys)

rows = []
for d in sorted(pathlib.Path(".").iterdir()):
    if not d.is_dir() or d.name == "results":
        continue
    meta = d / "ro-crate-metadata.json"
    if not meta.exists():
        continue
    doc = json.loads(meta.read_text())
    natural = meta.resolve().name
    types, keys = collections.Counter(), collections.Counter()
    walk(doc, types, keys)
    graph = doc.get("@graph")
    ctx = doc.get("@context")
    rows.append({
        "slug": d.name,
        "file": natural,
        "graph": "list" if isinstance(graph, list) else ("dict" if graph else "NONE"),
        "n_graph": len(graph) if isinstance(graph, list) else 0,
        "ctx": ("str" if isinstance(ctx, str) else
                "list" if isinstance(ctx, list) else
                "dict" if isinstance(ctx, dict) else "none"),
        "top_type": doc.get("@type"),
        "types": types,
        "keys": keys,
    })

what = sys.argv[1] if len(sys.argv) > 1 else "overview"

if what == "overview":
    print("example\tpayload file\t@graph\tn\t@context\ttop-level @type\ttop @type tokens")
    for r in rows:
        top = ", ".join(f"{t}:{n}" for t, n in r["types"].most_common(6))
        print("\t".join([r["slug"], r["file"], r["graph"], str(r["n_graph"]),
                         r["ctx"], str(r["top_type"] or "-"), top]))
elif what == "types":
    allt = collections.Counter()
    for r in rows:
        allt.update(r["types"])
    for t, n in allt.most_common(60):
        print(f"{n:7d}  {t}")
elif what == "fields":
    print("example\t" + "\t".join(GRADER_FIELDS + ["|"] + OTHER_FIELDS))
    for r in rows:
        cells = [str(r["keys"].get(f, 0) or ".") for f in GRADER_FIELDS]
        cells += ["|"] + [str(r["keys"].get(f, 0) or ".") for f in OTHER_FIELDS]
        print("\t".join([r["slug"]] + cells))
