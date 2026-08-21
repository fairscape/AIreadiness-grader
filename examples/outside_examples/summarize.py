#!/usr/bin/env python3
"""Summarise what the grader made of each outside example.

Reads results/<slug>/ai-ready-presentation.json and reports, per example:
root entity found, entity/type counts, criteria that raised, criteria with no
evidence at all, and the distribution of mechanical estimates.
"""
import json, pathlib, sys

rows = []
for out in sorted(pathlib.Path("results").iterdir()):
    if not out.is_dir():
        continue
    p = out / "ai-ready-presentation.json"
    if not p.exists():
        err = (out / "stderr.txt").read_text().strip().splitlines()
        rows.append({"slug": out.name, "status": "CRASH",
                     "note": err[-1][:100] if err else "no output"})
        continue
    d = json.loads(p.read_text())
    crits = [c for s in d["sections"] for c in s["criteria"]]
    errs = [c["id"] for c in crits if c.get("error")]
    empty = [c["id"] for c in crits if not c["evidence"]]
    ests = [str(c["estimate"]["score"]) for c in crits if c.get("estimate")]
    num = [int(e) for e in ests if e.isdigit()]
    inv = d["inventory"]
    rows.append({
        "slug": out.name,
        "status": "ran",
        "root": d["crate"]["@id"],
        "root_name": (d["crate"]["name"] or "")[:34],
        "entities": inv["entities"],
        "by_type": inv["by_type"],
        "hasPart": inv["hasPart_count"],
        "n_err": len(errs), "errs": errs,
        "n_empty": len(empty), "empty": empty,
        "n_est": len(ests), "n_na": len(ests) - len(num),
        "est_sum": sum(num), "est_max": 2 * len(num),
    })

hdr = ["example", "root@id", "root name", "ents", "types seen", "hasPart",
       "err", "no-evid", "est", "est pts"]
print("\t".join(hdr))
for r in rows:
    if r["status"] == "CRASH":
        print("\t".join([r["slug"], "CRASH", r["note"], "", "", "", "", "", "", ""]))
        continue
    types = ", ".join(f"{k}:{v}" for k, v in sorted(r["by_type"].items(),
                                                    key=lambda x: -x[1]))
    print("\t".join([r["slug"], str(r["root"]), r["root_name"], str(r["entities"]),
                     types or "-", str(r["hasPart"]), str(r["n_err"]),
                     f'{r["n_empty"]}/28', str(r["n_est"]),
                     f'{r["est_sum"]}/{r["est_max"]}']))

if "--detail" in sys.argv:
    print()
    for r in rows:
        if r.get("errs"):
            print(f'{r["slug"]}: raised on {", ".join(r["errs"])}')
    print()
    for r in rows:
        if r.get("empty"):
            print(f'{r["slug"]}: no evidence for {", ".join(r["empty"])}')
