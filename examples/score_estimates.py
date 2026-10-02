"""Roll fairscape-evidence's automated estimates up with the grader's v1.8 aggregator."""
import json, sys
from aireadiness_grader.rubric_eval import _aggregate

ev = json.load(open(sys.argv[1]))
per, unestimated = [], []
for s in ev["sections"]:
    for c in s["criteria"]:
        e = c.get("estimate")
        if not e:
            unestimated.append(f'{c["id"]} {c["name"]}')
            continue
        sc = e["score"]
        sc = int(sc) if str(sc).isdigit() else sc
        per.append({"id": c["id"], "name": c["name"], "score": sc,
                    "rationale": "; ".join(e.get("basis", []))})
agg = _aggregate(per, "fairscape-evidence automated estimates (no LLM)")
agg["note"] = ("Only criteria with an automated estimate are counted; the rest need "
               "human or model judgment and are listed in unestimated_criteria.")
agg["unestimated_criteria"] = unestimated
json.dump(agg, open(sys.argv[2], "w"), indent=2)
print(json.dumps({k: v for k, v in agg.items() if k not in ("criteria",)}, indent=1)[:2500])
for c in agg["criteria"]:
    print(c["id"], c["name"], f'{c["score"]}/{c["max"]}', c["percentage"])
