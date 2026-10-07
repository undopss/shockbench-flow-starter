"""Why the fab-grids lose lots: weekly power vs wafer limits, agent vs oracle (gap17v2 JSON)."""
import json, sys
from collections import defaultdict
import numpy as np

rows = [r for r in json.loads(open(sys.argv[1]).read()) if r["oracle"] is not None]
meta = rows[0]["meta"]; F = meta["fabs"]; G = [g["id"] for g in meta["grids"]]
T = len(rows[0]["detail"]["lots_w"])
print("## Per fab-grid, weeks (summed over 20 episodes): agent fab state, and where the oracle's fab energy goes")
print(f"{'grid':9s} {'wk shed>0':>9s} {'agent: fab<5%cap & shed>0':>26s} {'fab<5% & wafers<1wk':>20s} {'fab<5% other':>12s}"
      f" {'oracle E in its shed weeks':>27s} {'oracle E in agent-shed wks':>26s}")
for g in ("grid_cn", "grid_jp", "grid_sea", "grid_kr", "grid_tw", "grid_eu", "grid_us"):
    gi = G.index(g)
    fi = [f for f, m in enumerate(F) if m["grid"] == g]
    cap = np.array([F[f]["cap0"] for f in fi])
    a = defaultdict(int); oE_shed = oE = oE_ash = 0.0
    for r in rows:
        sh = np.array(r["detail"]["shed_w"])[:, gi]
        osh = np.array(r["oracle_detail"]["shed_w"])[:, gi]
        lots = np.array(r["detail"]["lots_w"])[:, fi].sum(1)
        wst = np.array(r["detail"]["wafer_stock_w"])[:, fi].sum(1)
        oe = np.array(r["oracle_detail"]["energy_w"])[:, fi].sum(1)
        low = lots < 0.05 * cap.sum()
        a["shed"] += int((sh > 1e-6).sum())
        a["low_shed"] += int((low & (sh > 1e-6)).sum())
        a["low_waf"] += int((low & (sh <= 1e-6) & (wst < cap.sum())).sum())
        a["low_other"] += int((low & (sh <= 1e-6) & (wst >= cap.sum())).sum())
        oE += oe.sum(); oE_shed += oe[osh > 1e-6].sum(); oE_ash += oe[sh > 1e-6].sum()
    n = len(rows) * T
    print(f"{g:9s} {a['shed']/n:9.1%} {a['low_shed']/n:26.1%} {a['low_waf']/n:20.1%} {a['low_other']/n:12.1%}"
          f" {oE_shed/max(oE,1e-9):27.1%} {oE_ash/max(oE,1e-9):26.1%}")
print("(share of all episode-weeks; 'oracle E in its shed weeks' = share of the oracle's fab energy at that grid delivered"
      " in weeks where the oracle itself sheds homes there, i.e. only possible through the base_first relaxation"
      " unless fuel is moved between weeks)")

print("\n## CN: per episode, weeks with shed > 0 (agent / oracle), mean weekly shed as % of base load, agent CN lots")
gi = G.index("grid_cn"); fi = [f for f, m in enumerate(F) if m["grid"] == "grid_cn"]
yb = meta["grids"][gi]["base_load"]
for r in rows:
    sh = np.array(r["detail"]["shed_w"])[:, gi]; osh = np.array(r["oracle_detail"]["shed_w"])[:, gi]
    print(f"ep {r['episode']:3d}: shed weeks {int((sh>1e-6).sum()):3d}/{int((osh>1e-6).sum()):3d}, median shed in shed weeks"
          f" {np.median(sh[sh>1e-6])/yb if (sh>1e-6).any() else 0:6.1%} of base load,"
          f" agent lots {np.array(r['detail']['lots_w'])[:, fi].sum()/1e6:5.1f}M, oracle {np.array(r['oracle_detail']['lots_w'])[:, fi].sum()/1e6:5.1f}M")

print("\n## OSAT packaging per episode (M units, mean): agent vs oracle")
pk_a, pk_o = defaultdict(float), defaultdict(float)
for r in rows:
    for k, v in r["detail"]["packaged"].items():
        pk_a[k] += v / len(rows)
    for k, v in r["oracle_detail"]["xi"].items():
        pk_o[k] += v / len(rows)
for k in sorted(set(pk_a) | set(pk_o), key=lambda k: -pk_o.get(k, 0)):
    print(f"  {k:10s} agent {pk_a.get(k,0)/1e6:7.2f}  oracle {pk_o.get(k,0)/1e6:7.2f}")

print("\n## chip stock left at the end (agent, M units, mean) and chip disposal agent vs oracle")
slots = rows[0]["detail"]["slots"]
end, da, do = defaultdict(float), defaultdict(float), defaultdict(float)
for r in rows:
    for s, (node, k) in enumerate(slots):
        if k.startswith("chip"):
            end[k] += r["detail"]["stock_end"][s] / len(rows)
            da[k] += r["detail"]["disposal"][s] / len(rows)
            do[k] += r["oracle_detail"]["O"][s] / len(rows)
for k in sorted(end):
    print(f"  {k:14s} end stock {end[k]/1e6:6.2f}  disposed agent {da[k]/1e6:6.2f}  oracle {do[k]/1e6:6.2f}")
