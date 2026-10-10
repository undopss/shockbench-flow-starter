"""Task 41: the score-weighted gap map. Every component of (J_agent - J_oracle) is converted to RSS points:

    1 - RSS = sum_s p_s mean_{e in s}(J_a,e - J_o,e) / sum_s p_s mean_{e in s}(J_n,e - J_o,e)      (rss.py (56))
    points(component c, episode e) = p_s / n_s * gap_c,e / DEN,   DEN = sum_s p_s Dbar_s

    uv run python outputs/task-41/map41.py outputs/task-17/gap17v2_full_0_dev_mpc_best.json

Prints, per level and pooled: USD/ep and RSS points of every component, shed per grid, chip lost-sales split
(not made / disposed / rest, end stock), then the per-episode RSS points lost, ranked.
"""

import json
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, "outputs/task-34")
P = {1: 0.50, 2: 0.30, 3: 0.15, 4: 0.05}
T12 = 1e12

rows = sorted((r for r in json.loads(open(sys.argv[1]).read()) if r["oracle"] is not None), key=lambda r: r["episode"])
meta = next(r["meta"] for r in rows if isinstance(r.get("meta"), dict) and "fabs" in r["meta"])
F, G, D = meta["fabs"], [g["id"] for g in meta["grids"]], meta["demands"]
G_voll = np.array([g["voll"] for g in meta["grids"]])
pi = np.array([d["pi"] for d in D])
prods = sorted({d["k"] for d in D})
pi_prod = {k: float(np.mean([d["pi"] for d in D if d["k"] == k])) for k in prods}

lev = defaultdict(list)
for r in rows:
    lev[r["stratum"]].append(r)
levels = sorted(lev)
Dbar = {s: np.mean([(r["J_naive_cached"] - r["J_oracle_cached"]) / 100 for r in lev[s]]) for s in levels}
DEN = sum(P[s] * Dbar[s] for s in levels) / sum(P[s] for s in levels)  # renormalised if a level is missing
W = {s: P[s] / sum(P[t] for t in levels) / len(lev[s]) for s in levels}  # weight of one episode of level s


def pts(r, usd):
    return W[r["stratum"]] * usd / DEN


def items(r):
    """{name: USD gap agent - oracle} for one episode; the leaves add up to the J gap (+ residual)."""
    a, o = r["agent"], r["oracle"]
    out = {}
    for k in ("freight", "war_risk", "tariff", "holding", "queue_holding", "disposal", "salvage_credit"):
        out[k] = a.get(k, 0.0) - o.get(k, 0.0)
    sa = np.array(r["detail"]["shed_w"]).sum(axis=0) * G_voll
    so = np.array(r["oracle_detail"]["shed_w"]).sum(axis=0) * G_voll
    for g, gid in enumerate(G):
        out["shed/" + gid.replace("grid_", "")] = sa[g] - so[g]
    out["shed/(rest)"] = (a["shed"] - o["shed"]) - (sa - so).sum()
    slots = r["detail"]["slots"]
    chip_tot = 0.0
    for p in prods:
        di = [i for i, d in enumerate(D) if d["k"] == p]
        fi = [i for i, m in enumerate(F) if m["product"] == p + "_raw"]
        si = [s for s, (node, k) in enumerate(slots) if k in (p, p + "_raw")]
        lost_v = sum((r["detail"]["lost"][i] - r["oracle_detail"]["lost"][i]) * pi[i] for i in di)
        lots = sum(r["oracle_detail"]["lots_started"][i] - r["detail"]["lots_started"][i] for i in fi)
        disp = sum(r["detail"]["disposal"][s] - r["oracle_detail"]["O"][s] for s in si)
        end = sum(r["detail"]["stock_end"][s] for s in si)
        sa_, sb = lots * pi_prod[p], disp * pi_prod[p]
        nm = p.replace("chip_", "")
        out[f"short/{nm}/a_notmade"] = sa_
        out[f"short/{nm}/b_disposed"] = sb
        out[f"short/{nm}/c_endstock"] = end * pi_prod[p]
        out[f"short/{nm}/c_rest"] = lost_v - sa_ - sb - end * pi_prod[p]
        chip_tot += lost_v
    out["short/(other)"] = (a["shortage"] - o["shortage"]) - chip_tot
    out["(residual)"] = (r["J_agent_cents"] - r["J_oracle_cached"]) / 100 - sum(out.values())
    return out


allk = list(items(rows[0]))
per = {r["episode"]: items(r) for r in rows}

rss_official = None
try:
    from shockbench_flow.scoring.rss import rss_pooled
    rss_official = rss_pooled([r["J_agent_cents"] for r in rows], [r["J_naive_cached"] for r in rows],
                              [r["J_oracle_cached"] for r in rows], [r["stratum"] for r in rows])
except Exception as e:  # noqa: BLE001
    print("official rss failed:", e)
tot_pts = sum(pts(r, (r["J_agent_cents"] - r["J_oracle_cached"]) / 100) for r in rows)
print(f"{len(rows)} episodes; levels {[(s, len(lev[s])) for s in levels]}; DEN = sum p_s Dbar_s = {DEN/T12:.4f} T")
print(f"official pooled RSS {rss_official:.5f}; 1 - RSS = {1 - rss_official:.5f}; sum of RSS points = {tot_pts:.5f}")
print(f"one USD in an L1 episode is worth {W[1]/W[levels[-1]]:.1f}x one USD in an L{levels[-1]} episode")
print("\nRSS points (x100 = 'points of RSS') and USD gap per episode (T), per level; sorted by pooled points")
hdr = f"{'component':24s} {'pooled pts':>10s} " + " ".join(f"{'L%d pts' % s:>8s}" for s in levels) + "   " + \
    " ".join(f"{'L%d T/ep' % s:>8s}" for s in levels) + f" {'all T/ep':>9s}"
print(hdr)
tab = []
for k in allk:
    lp = {s: sum(pts(r, per[r["episode"]][k]) for r in lev[s]) for s in levels}
    lu = {s: np.mean([per[r["episode"]][k] for r in lev[s]]) / T12 for s in levels}
    tab.append((sum(lp.values()), k, lp, lu, np.mean([per[r["episode"]][k] for r in rows]) / T12))
for tp, k, lp, lu, au in sorted(tab, key=lambda x: -x[0]):
    print(f"{k:24s} {tp*100:10.3f} " + " ".join(f"{lp[s]*100:8.3f}" for s in levels) + "   "
          + " ".join(f"{lu[s]:8.4f}" for s in levels) + f" {au:9.4f}")
tp = sum(t[0] for t in tab)
print(f"{'TOTAL':24s} {tp*100:10.3f} " + " ".join(f"{sum(t[2][s] for t in tab)*100:8.3f}" for s in levels) + "   "
      + " ".join(f"{sum(t[3][s] for t in tab):8.4f}" for s in levels) + f" {sum(t[4] for t in tab):9.4f}")

print("\nGroups (RSS points x100):")
groups = defaultdict(lambda: defaultdict(float))
for _, k, lp, _, _ in tab:
    g = k.split("/")[0] + ("/" + k.split("/")[1] if k.startswith("short/") else "")
    for s in levels:
        groups[g][s] += lp[s]
for g, d in sorted(groups.items(), key=lambda x: -sum(x[1].values())):
    print(f"  {g:22s} {sum(d.values())*100:8.3f}   " + " ".join(f"L{s} {d[s]*100:7.3f}" for s in levels))

print("\nPer-episode: RSS points lost (x100), episode RSS, J gap T, top 4 items (T)")
eprow = []
for r in rows:
    gap = (r["J_agent_cents"] - r["J_oracle_cached"]) / 100
    rss_e = (r["J_naive_cached"] - r["J_agent_cents"]) / (r["J_naive_cached"] - r["J_oracle_cached"])
    eprow.append((pts(r, gap), r, rss_e, gap))
for p_, r, rss_e, gap in sorted(eprow, key=lambda x: -x[0]):
    top = sorted(per[r["episode"]].items(), key=lambda x: -abs(x[1]))[:4]
    print(f"  ep{r['episode']:3d} L{r['stratum']} pts {p_*100:6.3f} RSS_e {rss_e:.3f} gap {gap/T12:.3f}  "
          + ", ".join(f"{k} {v/T12:+.3f}" for k, v in top))
