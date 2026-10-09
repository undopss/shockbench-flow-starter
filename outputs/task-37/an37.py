"""Tables from diag37 JSON: disposal per slot by class, LP-planned vs real disposal, fab starts planned vs real.
    uv run python outputs/task-37/an37.py outputs/task-37/diag37_....json
"""
import json, sys
from collections import defaultdict
import numpy as np

rows = json.loads(open(sys.argv[1]).read())
n = len(rows)
agg = defaultdict(lambda: defaultdict(float))
for r in rows:
    for key, s in r["slots"].items():
        d = np.array(s["disp"]); a = agg[key]
        a["pi"] = s["pi"]; a["cap"] = s["cap"]
        a["disp"] += d.sum() / n
        a["plan_d0"] += np.nansum(s["plan_d0"]) / n
        for t, x in enumerate(d):
            if x <= 0: continue
            c = s["cls"][t]; lost = s["lost"][t] > 1e-6
            a[c] += x / n
            if c == "unused":
                a["unused_lost"] += x / n if lost else 0
            a["planned_too"] += min(x, s["plan_d0"][t]) / n if np.isfinite(s["plan_d0"][t]) else 0
        a["endstock"] += s["stock"][-1] / n
tot = defaultdict(float)
print(f"{n} episodes; M units/ep. full = out-edges >=95% used that week; unused (lost) = spare out-cap and a sink of the product lost sales that week; LPplan = LP planned that disposal at t=0 itself")
print(f"{'slot':34s} {'cap':>9s} {'disp':>7s} {'full':>7s} {'unused':>7s} {'(lost)':>7s} {'blocked':>7s} {'LPplan':>7s} {'T@pi':>7s} {'end':>6s}")
for k, a in sorted(agg.items(), key=lambda kv: -kv[1]["disp"] * kv[1]["pi"]):
    if a["disp"] < 1e3: continue
    v = a["disp"] * a["pi"] / 1e12
    for c in ("disp", "full", "unused", "unused_lost", "blocked", "planned_too"):
        tot[c] += a[c]
    tot["T"] += v
    print(f"{k:34s} {a['cap']:9.0f} {a['disp']/1e6:7.3f} {a['full']/1e6:7.3f} {a['unused']/1e6:7.3f} {a['unused_lost']/1e6:7.3f} {a['blocked']/1e6:7.3f} {a['planned_too']/1e6:7.3f} {v:7.4f} {a['endstock']/1e6:6.2f}")
print("TOTAL", {k: round(v / 1e6, 3) if k != "T" else round(v, 4) for k, v in tot.items()})
print()
print("fabs: lots M/ep real vs LP-planned starts at t=0 (sum), weeks real>1.05*plan+1000, excess lots in those weeks, mean LP cap / cap0")
fa = defaultdict(lambda: defaultdict(float))
for r in rows:
    for f, s in r["fabs"].items():
        lots, ps = np.array(s["lots"]), np.array(s["plan_s0"])
        m = np.isfinite(ps)
        a = fa[f]; a["prod"] = s["product"]
        a["lots"] += lots.sum() / n
        a["plan"] += ps[m].sum() / n
        over = m & (lots > 1.05 * ps + 1000)
        a["over_w"] += over.sum() / n
        a["over_x"] += (lots - ps)[over].sum() / n
        under = m & (lots < 0.95 * ps - 1000)
        a["under_x"] += (ps - lots)[under].sum() / n
        a["capfrac"] += np.nanmean(np.array(s["plan_cap0"]) / s["cap0"]) / n
        a["energy"] += sum(s["energy"]) / n
for f, a in fa.items():
    print(f"{f:20s} {a['prod']:12s} real {a['lots']/1e6:6.2f} plan {a['plan']/1e6:6.2f} over_w {a['over_w']:5.1f} over {a['over_x']/1e6:6.2f} under {a['under_x']/1e6:6.2f} capfrac {a['capfrac']:.2f}")
lost = defaultdict(float)
for r in rows:
    for k, (q, p) in r["lost_by_k"].items():
        lost[k] += q * p / n / 1e12
print("lost sales T/ep:", {k: round(v, 3) for k, v in sorted(lost.items(), key=lambda kv: -kv[1]) if v > 0.005})
print("costs T/ep:", {c: round(sum(r['costs'][c] for r in rows) / n / 1e14, 4) for c in rows[0]['costs']}, "(J in cents -> /1e14 = T USD)")
print()
print("route-level class (M units/ep): route = some route from the slot had every edge <95% used that week and (packaged) its sink lost sales on arrival")
ra = defaultdict(lambda: defaultdict(float))
for r in rows:
    for key, s in r["slots"].items():
        for t, c in enumerate(s.get("rcls", [])):
            if c:
                ra[key][c] += s["disp"][t] / n
                if c == "route":
                    ra[key]["@" + str(s["rwhere"][t])] += s["disp"][t] / n
for k, a in sorted(ra.items(), key=lambda kv: -sum(v for c, v in kv[1].items() if not c.startswith("@"))):
    if a["route"] + a["routes_full"] < 1e4: continue
    wh = {c[1:]: round(v / 1e6, 3) for c, v in a.items() if c.startswith("@")}
    print(f"{k:34s} routes_full {a['routes_full']/1e6:7.3f} route {a['route']/1e6:7.3f} {wh}")
