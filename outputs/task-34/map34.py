"""Task 34: the gap map of several agents side by side on the same episodes (gap17 JSONs), plus the per-episode list.

    uv run python outputs/task-34/map34.py name=gap17.json [name=gap17.json ...]

1. Cost gap to the clairvoyant plan (T USD/episode) by component; shed by grid.
2. Chip lost sales (agent - oracle, T USD/ep) per product, split by a unit balance (both start from the same stocks):
     served_o - served_a = (lots_o - lots_a) + (disposed_a - disposed_o) + (end_a - end_o) + rest
   (a) not made   = (lots_o - lots_a) x mean pi of the product (net over fabs; the gross per-fab deficit is map20's)
   (b) disposed   = (disposed_a - disposed_o) x pi (raw + packaged slots of the product)
   (c) the rest   = lost-sales gap - (a) - (b): chips made and not disposed that were not sold in time: left in stock
       or in transit at the end (end stock shown separately; oracle's end stock is not recorded, counted as 0),
       sold late, or sold at a cheaper sink (the sink-mix part is value gap - units gap x mean pi)
3. Per-episode RSS of the LAST agent, sorted, with what dominates each of the 5 worst episodes.
"""

import json
import sys
from collections import defaultdict

import numpy as np

T12 = 1e12
runs = {}
for arg in sys.argv[1:]:
    name, path = arg.split("=", 1)
    runs[name] = sorted((r for r in json.loads(open(path).read()) if r["oracle"] is not None), key=lambda r: r["episode"])
names = list(runs)
rows0 = runs[names[0]]
meta = next(r["meta"] for r in rows0 if isinstance(r.get("meta"), dict) and "fabs" in r["meta"])
F, G, D = meta["fabs"], [g["id"] for g in meta["grids"]], meta["demands"]
G_voll = np.array([g["voll"] for g in meta["grids"]])
pi = np.array([d["pi"] for d in D])
prods = sorted({d["k"] for d in D})
pi_prod = {k: float(np.mean([d["pi"] for d in D if d["k"] == k])) for k in prods}
for nm in names:
    assert [r["episode"] for r in runs[nm]] == [r["episode"] for r in rows0], "different episodes"


def comp(r, who):
    return r["agent" if who == "a" else "oracle"]


def chip_split(r):
    """{product: dict of T USD} for one episode."""
    out = {}
    slots = r["detail"]["slots"]
    for p in prods:
        di = [i for i, d in enumerate(D) if d["k"] == p]
        fi = [i for i, m in enumerate(F) if m["product"] == p + "_raw"]
        si = [s for s, (node, k) in enumerate(slots) if k in (p, p + "_raw")]
        lost_v = sum((r["detail"]["lost"][i] - r["oracle_detail"]["lost"][i]) * pi[i] for i in di)
        units = sum(r["oracle_detail"]["served"][i] - r["detail"]["served"][i] for i in di)
        lots = sum(r["oracle_detail"]["lots_started"][i] - r["detail"]["lots_started"][i] for i in fi)
        disp = sum(r["detail"]["disposal"][s] - r["oracle_detail"]["O"][s] for s in si)
        end = sum(r["detail"]["stock_end"][s] for s in si)
        a, b = lots * pi_prod[p], disp * pi_prod[p]
        out[p] = {"gap": lost_v, "a_notmade": a, "b_disposed": b, "c_rest": lost_v - a - b, "end_stock": end * pi_prod[p],
                  "sinkmix": lost_v - units * pi_prod[p], "units": units, "lots": lots, "disp": disp}
    return out


def shed_grid(r):
    a = np.array(r["detail"]["shed_w"]).sum(axis=0) * G_voll
    o = np.array(r["oracle_detail"]["shed_w"]).sum(axis=0) * G_voll
    return a - o


print(f"episodes: {len(rows0)} (root 0 dev); agents: {', '.join(names)}")
print("\n## 1. Gap to the clairvoyant plan, T USD/episode (agent - oracle)")
keys = list(rows0[0]["agent"])
print(f"{'component':18s}" + "".join(f"{nm:>14s}" for nm in names) + "".join(f"{'d ' + nm:>16s}" for nm in names[1:]))
tab = {}
for k in keys + ["TOTAL"]:
    vals = []
    for nm in names:
        rr = runs[nm]
        if k == "TOTAL":
            v = np.mean([(r["J_agent_cents"] - r["J_oracle_cents"]) / 100 for r in rr])
        else:
            v = np.mean([comp(r, "a")[k] - comp(r, "o")[k] for r in rr])
        vals.append(v / T12)
    tab[k] = vals
    print(f"{k:18s}" + "".join(f"{v:14.4f}" for v in vals) + "".join(f"{v - vals[0]:16.4f}" for v in vals[1:]))
print("\nshed by grid:")
for g, gid in enumerate(G):
    vals = [np.mean([shed_grid(r)[g] for r in runs[nm]]) / T12 for nm in names]
    print(f"  {gid:16s}" + "".join(f"{v:14.4f}" for v in vals) + "".join(f"{v - vals[0]:16.4f}" for v in vals[1:]))

print("\n## 2. Chip lost sales split (T USD/episode; units M)")
for nm in names:
    sp = [chip_split(r) for r in runs[nm]]
    print(f"{nm}:")
    for p in prods:
        m = {k: np.mean([s[p][k] for s in sp]) for k in sp[0][p]}
        print(f"  {p:9s} gap {m['gap']/T12:7.4f} = (a) not made {m['a_notmade']/T12:7.4f} [{m['lots']/1e6:+6.2f} M lots]"
              f" + (b) disposed {m['b_disposed']/T12:7.4f} [{m['disp']/1e6:+6.2f} M] + (c) rest {m['c_rest']/T12:7.4f}"
              f"   | end stock {m['end_stock']/T12:6.4f}, sink-mix part {m['sinkmix']/T12:+7.4f}")
    print("  by sink (lost-sales gap T): " + ", ".join(
        f"{D[i]['node'].replace('sink_', '')}/{D[i]['k'].replace('chip_', '')} "
        f"{np.mean([(r['detail']['lost'][i] - r['oracle_detail']['lost'][i]) * pi[i] for r in runs[nm]]) / T12:.3f}"
        for i in np.argsort([-np.mean([(r['detail']['lost'][i] - r['oracle_detail']['lost'][i]) * pi[i]
                                       for r in runs[nm]]) for i in range(len(D))])[:8]))

nm = names[-1]
rr = runs[nm]
print(f"\n## 3. Per-episode RSS of {nm}, sorted (RSS_e = (J_naive - J_agent) / (J_naive - J_oracle))")
eps = []
for r in rr:
    rss = (r["J_naive_cents"] - r["J_agent_cents"]) / (r["J_naive_cents"] - r["J_oracle_cents"])
    eps.append((rss, r))
eps.sort(key=lambda x: x[0])
print("  " + "  ".join(f"ep{r['episode']}(L{r['stratum']}) {s:.3f}" for s, r in eps))
print("\n5 worst:")
for s, r in eps[:5]:
    gap = (r["J_agent_cents"] - r["J_oracle_cents"]) / 100
    sp = chip_split(r)
    sg = shed_grid(r)
    top_g = np.argsort(-sg)[:2]
    other = sum(comp(r, "a")[k] - comp(r, "o")[k] for k in keys if k not in ("shortage", "shed"))
    ev = defaultdict(int)
    for e in r["events"]:
        ev[e["type"]] += 1
    T = len(r["detail"]["lots_w"])
    inside = [e for e in r["events"] if 0 <= e["onset"] < T]  # shocks that start during the episode
    big = sorted(inside, key=lambda e: -e["severity"] * min(e["duration"], T - e["onset"]))[:4]
    print(f"  ep {r['episode']:3d} L{r['stratum']} RSS {s:.3f}: gap {gap/T12:.3f} T = chip_le {sp['chip_le']['gap']/T12:.3f} "
          f"(a {sp['chip_le']['a_notmade']/T12:.3f} b {sp['chip_le']['b_disposed']/T12:.3f} c {sp['chip_le']['c_rest']/T12:.3f})"
          f" + chip_mat {sp['chip_mat']['gap']/T12:.3f} + shed {sg.sum()/T12:.3f} "
          f"({', '.join(f'{G[g]} {sg[g]/T12:.3f}' for g in top_g)}) + other {other/T12:.3f}")
    lots_def = {m["id"]: r["oracle_detail"]["lots_started"][i] - r["detail"]["lots_started"][i] for i, m in enumerate(F)}
    worst_f = sorted(lots_def.items(), key=lambda x: -x[1])[:3]
    print(f"      fab lot deficits (M): " + ", ".join(f"{f} {v/1e6:+.2f}" for f, v in worst_f)
          + f"; {len(inside)} shocks start in the episode, biggest: " + ", ".join(f"{e['type']}@{e['target'] or e['region']} wk{e['onset']:.0f}+{e['duration']:.0f} sev{e['severity']:.2f}"
                                             for e in big))
