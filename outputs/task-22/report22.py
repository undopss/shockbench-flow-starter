"""Task 22 report: per component, shed per grid, lots per fab, lost USD per product x sink region, for every player in
gap22's JSON next to the oracle (means over the episodes, T USD = 1e12).

    uv run python outputs/task-22/report22.py outputs/task-22/gap22_full_0_2-5-0-1-53-26.json
"""
import json
import sys
from collections import defaultdict

import numpy as np

COMP = ("freight", "war_risk", "tariff", "holding", "queue_holding", "shortage", "disposal", "shed", "salvage_credit")
d = json.load(open(sys.argv[1]))
rows = d["rows"]
meta = next(r["meta"] for r in rows if r["player"] == "oracle")
players = ["oracle"] + list(dict.fromkeys(r["player"] for r in rows if r["player"] != "oracle"))
short = {p: p.replace("policy:", "").replace("agents/", "") for p in players}
eps = sorted({r["episode"] for r in rows})
by = {(r["player"], r["episode"]): r for r in rows}
P = [p for p in players if all((p, e) in by for e in eps)]


def mean(p, f):
    return np.mean([f(by[(p, e)]) for e in eps], axis=0)


def head(title):
    print(f"\n## {title}")
    print(f"{'':26s}" + "".join(f"{short[p][:16]:>17s}" for p in P))


head(f"Cost per component, T USD per episode (mean of {len(eps)} episodes {eps})")
for c in COMP + ("TOTAL",):
    vals = [mean(p, lambda r: sum(r["costs"].values()) if c == "TOTAL" else r["costs"][c]) / 1e12 for p in P]
    print(f"{c:26s}" + "".join(f"{v:17.4f}" for v in vals))
print("gap to oracle (T):", "  ".join(f"{short[p]} {(mean(p, lambda r: sum(r['costs'].values())) - mean('oracle', lambda r: sum(r['costs'].values()))) / 1e12:.3f}" for p in P[1:]))

head("Shed per grid, T USD per episode (energy shed x VoLL)")
for g, gm in enumerate(meta["grids"]):
    vals = [mean(p, lambda r: r["detail"]["shed"][g]) * gm["voll"] / 1e12 for p in P]
    print(f"{gm['id']:26s}" + "".join(f"{v:17.4f}" for v in vals))

head("Fab lots started per episode (millions)")
for f, fm in enumerate(meta["fabs"]):
    vals = [mean(p, lambda r: r["detail"]["lots_started"][f]) / 1e6 for p in P]
    print(f"{fm['id']:26s}" + "".join(f"{v:17.2f}" for v in vals))
print(f"{'TOTAL':26s}" + "".join(f"{mean(p, lambda r: sum(r['detail']['lots_started'])) / 1e6:17.2f}" for p in P))

head("Lost sales, T USD per episode, by product x sink")
agg = defaultdict(lambda: np.zeros(len(P)))
for i, dm in enumerate(meta["demands"]):
    key = f"{dm['k']}@{dm['node'].replace('sink_', '')}"
    agg[key] += np.array([mean(p, lambda r: r["detail"]["lost"][i]) * dm["pi"] / 1e12 for p in P])
for key, v in sorted(agg.items(), key=lambda kv: -kv[1].max()):
    if v.max() > 0.005:
        print(f"{key[:26]:26s}" + "".join(f"{x:17.4f}" for x in v))
tot = sum(agg.values())
print(f"{'TOTAL lost USD':26s}" + "".join(f"{x:17.4f}" for x in tot))

head("Per episode RSS-like: total cost T USD")
for e in eps:
    print(f"ep {e:<23d}" + "".join(f"{sum(by[(p, e)]['costs'].values()) / 1e12:17.3f}" for p in P))
