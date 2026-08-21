#!/usr/bin/env python3
"""Diagnostic: how much would a root-detection fallback recover?

The grader only reads doc["@graph"]. For each example that has no @graph, this
wraps the document in a minimal RO-Crate envelope (descriptor -> about -> the
document itself as root, plus any nested typed objects hoisted into the graph)
in a scratch dir, runs the grader again, and diffs the estimate totals.
Nothing in the grader or in the example dirs is modified.
"""
import json, pathlib, subprocess, sys, shutil, collections

SCRATCH = pathlib.Path("/tmp/claude-1000/-home-oj-fairscape/"
                       "72af41ed-3bbb-48bd-bb24-d84ea1e5e45a/scratchpad/wrapped")
ROOT = pathlib.Path("../..").resolve()


def hoist(node, out, counter):
    """Flatten nested typed objects into a graph list, minting ids as needed."""
    if isinstance(node, dict):
        for v in node.values():
            hoist(v, out, counter)
        if node.get("@type") and node is not out[0]:
            if "@id" not in node:
                counter[0] += 1
                node["@id"] = f"#hoisted-{counter[0]}"
            out.append(node)
    elif isinstance(node, list):
        for v in node:
            hoist(v, out, counter)


def totals(pres_path):
    d = json.loads(pres_path.read_text())
    crits = [c for s in d["sections"] for c in s["criteria"]]
    num = [int(c["estimate"]["score"]) for c in crits
           if c.get("estimate") and str(c["estimate"]["score"]).isdigit()]
    return d["inventory"]["entities"], sum(num), 2 * len(num)


shutil.rmtree(SCRATCH, ignore_errors=True)
SCRATCH.mkdir(parents=True)
print("example\tas-fetched (ents, pts)\twrapped (ents, pts)")
for d in sorted(pathlib.Path(".").iterdir()):
    m = d / "ro-crate-metadata.json"
    if not d.is_dir() or d.name == "results" or not m.exists():
        continue
    doc = json.loads(m.read_text())
    if isinstance(doc.get("@graph"), list):
        continue                       # already flattened; nothing to test

    root = dict(doc)
    ctx = root.pop("@context", None)
    root.setdefault("@id", "./")
    graph = [root]
    hoist(root, graph, [0])
    wrapped = {
        "@context": ctx or "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "ro-crate-metadata.json", "@type": "CreativeWork",
                    "about": {"@id": root["@id"]}}] + graph,
    }
    wdir = SCRATCH / d.name
    wdir.mkdir()
    (wdir / "ro-crate-metadata.json").write_text(json.dumps(wrapped, indent=1))

    out = wdir / "out"
    subprocess.run([sys.executable, "-m", "aireadiness_evidence.cli", str(wdir),
                    "-o", str(out), "--no-network", "--json-only", "-q"],
                   cwd=ROOT, capture_output=True)
    before = totals(pathlib.Path("results") / d.name / "ai-ready-presentation.json")
    after = totals(out / "ai-ready-presentation.json")
    print(f"{d.name}\t{before[0]} ents, {before[1]}/{before[2]}"
          f"\t{after[0]} ents, {after[1]}/{after[2]}")
