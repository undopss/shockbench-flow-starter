"""Task 20: why each fab makes fewer (or more) lots than the oracle, and the gap by time (gap17 JSON, any task).

    uv run python outputs/task-20/map20.py <gap17 json>

Per fab-week, the oracle's extra lots (oracle - agent, when > 0) are booked to the agent's state that week:
  cap      agent ran at >= 90% of cap0 * R (R = the episode's mean restoration factor; outages lower it)
  wafer    agent ended the week with < 5% of cap0 wafers on hand (it had nothing more to start)
  homes    the grid shed homes that week (base_first: fabs get only what is left after homes); split by
           the week's shed below / above 1% of the grid's base load
  power    no home shed, wafers on hand, but the fab got less energy than e * lots at 90% capacity
  other    none of the above (e.g. an outage week below the episode-mean R)
One lot = one raw chip; USD = lots x mean pi of its packaged product's sinks (an upper bound: not every chip sells).
"""

import json
import sys
from collections import defaultdict

import numpy as np

T12 = 1e12
rows = [r for r in json.loads(open(sys.argv[1]).read()) if r["oracle"] is not None]
meta = next(r["meta"] for r in rows if isinstance(r.get("meta"), dict) and "fabs" in r["meta"])
F, G, D = meta["fabs"], [g["id"] for g in meta["grids"]], meta["demands"]
T = len(rows[0]["detail"]["lots_w"])
n = len(rows)
pi_prod = {k: np.mean([d["pi"] for d in D if d["k"] == k]) for k in {d["k"] for d in D}}
val = np.array([pi_prod.get(m["product"].replace("_raw", ""), 0.0) for m in F])
ngap = np.mean([(r["J_naive_cents"] - r["J_oracle_cents"]) / 100 for r in rows])
gap = np.mean([(r["J_agent_cents"] - r["J_oracle_cents"]) / 100 for r in rows])
print(f"{n} episodes, T={T}: gap agent-oracle {gap/T12:.3f} T/ep, naive-oracle {ngap/T12:.3f} T/ep"
      f" -> 0.01 RSS ~ {0.01*ngap/T12:.4f} T/ep")
print("pi per product:", {k: round(v) for k, v in pi_prod.items()})

CL = ("cap", "wafer", "homes<1%", "homes>=1%", "power", "other")
YB = [g["base_load"] for g in meta["grids"]]
print("\n## Oracle's extra lots per fab (M lots/episode) by the agent's state in that week; agent's surplus lots")
print(f"{'fab':22s} {'grid':9s} {'agent':>7s} {'oracle':>7s} " + " ".join(f"{c:>9s}" for c in CL) + f" {'surplus':>8s} {'deficit $T':>10s}")
tot = defaultdict(float)
totv = defaultdict(float)
for f, m in enumerate(F):
    gi = G.index(m["grid"]) if m["grid"] in G else None
    acc = defaultdict(float)
    la = lo = 0.0
    for r in rows:
        a = np.array(r["detail"]["lots_w"])[:, f]
        o = np.array(r["oracle_detail"]["lots_w"])[:, f]
        w = np.array(r["detail"]["wafer_stock_w"])[:, f]
        e = np.array(r["detail"]["energy_w"])[:, f]
        sh = np.array(r["detail"]["shed_w"])[:, gi] if gi is not None else np.zeros(T)
        Rm = r["marks"]["R_mean"][f] if isinstance(r.get("marks"), dict) and "R_mean" in r["marks"] else 1.0
        cap = m["cap0"] * Rm
        d = np.maximum(o - a, 0.0)
        acc["surplus"] += np.maximum(a - o, 0.0).sum()
        la += a.sum(); lo += o.sum()
        st = np.full(T, "other", dtype=object)
        st[(e < 0.9 * m["e"] * cap) & (m["e"] > 0)] = "power"
        yb = YB[gi] if gi is not None else 1.0
        st[sh > 1e-6] = "homes<1%"
        st[sh >= 0.01 * yb] = "homes>=1%"
        st[w < 0.05 * m["cap0"]] = "wafer"
        st[a >= 0.9 * cap] = "cap"
        for c in CL:
            acc[c] += d[st == c].sum()
    for c in CL:
        tot[c] += acc[c] / n
        totv[c] += acc[c] / n * val[f]
    tot["surplus"] += acc["surplus"] / n
    totv["surplus"] += acc["surplus"] / n * val[f]
    dv = sum(acc[c] for c in CL) / n * val[f]
    print(f"{m['id']:22s} {str(m['grid'])[5:]:9s} {la/n/1e6:7.2f} {lo/n/1e6:7.2f} "
          + " ".join(f"{acc[c]/n/1e6:9.2f}" for c in CL) + f" {acc['surplus']/n/1e6:8.2f} {dv/T12:10.3f}")
print(f"{'TOTAL M lots':32s} {'':7s} " + " ".join(f"{tot[c]/1e6:9.2f}" for c in CL) + f" {tot['surplus']/1e6:8.2f}")
print(f"{'TOTAL T USD (lots x pi)':32s} {'':7s} " + " ".join(f"{totv[c]/T12:9.3f}" for c in CL) + f" {totv['surplus']/T12:8.3f}")

print("\n## Gap by time (agent - oracle, T USD/episode): chip lost sales and shed, quarters and the last 8 weeks")
pi = np.array([d["pi"] for d in D])
G_voll = np.array([g["voll"] for g in meta["grids"]])
qs = np.array_split(np.arange(T), 4) + [np.arange(T - 8, T)]
names = [f"wk {q[0]+1}-{q[-1]+1}" for q in qs]
print(f"{'':10s} " + " ".join(f"{s:>12s}" for s in names))
for p in sorted({d["k"] for d in D}):
    di = [i for i, d in enumerate(D) if d["k"] == p]
    out = []
    for q in qs:
        a = np.mean([(np.array(r["detail"]["lost_w"])[q][:, di] * pi[di]).sum() for r in rows])
        o = np.mean([(np.array(r["oracle_detail"]["lost_w"])[q][:, di] * pi[di]).sum() for r in rows])
        out.append((a - o) / T12)
    print(f"{p:10s} " + " ".join(f"{x:12.3f}" for x in out))
out = []
for q in qs:
    a = np.mean([(np.array(r["detail"]["shed_w"])[q] * G_voll).sum() for r in rows])
    o = np.mean([(np.array(r["oracle_detail"]["shed_w"])[q] * G_voll).sum() for r in rows])
    out.append((a - o) / T12)
print(f"{'shed':10s} " + " ".join(f"{x:12.3f}" for x in out))

print("\n## Shed gap by grid and quarter (agent - oracle, T USD/episode)")
for g in range(len(G)):
    out = []
    for q in qs[:4]:
        a = np.mean([np.array(r["detail"]["shed_w"])[q][:, g].sum() * G_voll[g] for r in rows])
        o = np.mean([np.array(r["oracle_detail"]["shed_w"])[q][:, g].sum() * G_voll[g] for r in rows])
        out.append((a - o) / T12)
    if max(abs(x) for x in out) > 1e-3:
        print(f"{G[g]:10s} " + " ".join(f"{x:8.3f}" for x in out))

print("\n## Late lots (started in the last 8 weeks; tau 6-8 weeks, so they rarely reach a sink): agent vs oracle, M")
for p in sorted({m["product"] for m in F}):
    fi = [f for f, m in enumerate(F) if m["product"] == p]
    a = np.mean([np.array(r["detail"]["lots_w"])[-8:, fi].sum() for r in rows])
    o = np.mean([np.array(r["oracle_detail"]["lots_w"])[-8:, fi].sum() for r in rows])
    print(f"  {p:14s} agent {a/1e6:6.2f}  oracle {o/1e6:6.2f}")

print("\n## Chips: end stock and disposal (M units/episode), agent vs oracle")
slots = rows[0]["detail"]["slots"]
end, da, do = defaultdict(float), defaultdict(float), defaultdict(float)
for r in rows:
    for s, (node, k) in enumerate(slots):
        if k.startswith("chip"):
            end[k] += r["detail"]["stock_end"][s] / n
            da[k] += r["detail"]["disposal"][s] / n
            do[k] += r["oracle_detail"]["O"][s] / n
for k in sorted(end):
    print(f"  {k:14s} end stock {end[k]/1e6:6.2f}  disposed agent {da[k]/1e6:6.2f}  oracle {do[k]/1e6:6.2f}")
