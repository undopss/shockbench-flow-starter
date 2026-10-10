"""Task 41: where the chips go in the worst calm episodes: disposal by slot (agent vs oracle), lots by fab, sales by sink.
    uv run python outputs/task-41/disp41.py outputs/task-41/gap17v2_full_0_dev_mpc_best.json 7,14,10,2,6,0
"""
import json, sys
import numpy as np
rows = {r["episode"]: r for r in json.loads(open(sys.argv[1]).read())}
meta = next(r["meta"] for r in rows.values() if isinstance(r.get("meta"), dict) and "fabs" in r["meta"])
F, D = meta["fabs"], meta["demands"]
pi = np.array([d["pi"] for d in D])
pip = {"chip_le": 50460, "chip_mat": 10335}
eps = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else sorted(rows)
agg = {}
for e in eps:
    r = rows[e]
    slots = r["detail"]["slots"]
    print(f"\n=== ep {e} L{r['stratum']}  gap {(r['J_agent_cents']-r['J_oracle_cached'])/1e14:.3f} T")
    rows_ = []
    for s, (node, k) in enumerate(slots):
        if not k.startswith("chip"):
            continue
        a, o = r["detail"]["disposal"][s], r["oracle_detail"]["O"][s]
        end = r["detail"]["stock_end"][s]
        v = pip[k.replace("_raw", "")]
        if abs(a - o) * v > 2e9 or end * v > 5e9:
            rows_.append(((a - o) * v, node, k, a, o, end))
        agg[(node, k)] = agg.get((node, k), 0) + (a - o) * v
    for dv, node, k, a, o, end in sorted(rows_, key=lambda x: -x[0])[:10]:
        print(f"  disp {node:22s} {k:13s} agent {a/1e6:6.2f} M oracle {o/1e6:6.2f} M  ({dv/1e12:+.3f} T)  end stock {end/1e6:5.2f} M")
    print("  lots (agent-oracle, M): " + ", ".join(f"{m['id'].replace('fab_','')} {(r['detail']['lots_started'][i]-r['oracle_detail']['lots_started'][i])/1e6:+.1f}"
          for i, m in enumerate(F) if abs(r['detail']['lots_started'][i]-r['oracle_detail']['lots_started'][i]) > 0.5e6))
    print("  lost-sales gap by sink (T): " + ", ".join(f"{D[i]['node'].replace('sink_','')}/{D[i]['k'][5:]} {(r['detail']['lost'][i]-r['oracle_detail']['lost'][i])*pi[i]/1e12:+.3f}"
          for i in np.argsort([-(r['detail']['lost'][i]-r['oracle_detail']['lost'][i])*pi[i] for i in range(len(D))]) if abs((r['detail']['lost'][i]-r['oracle_detail']['lost'][i])*pi[i]) > 0.01e12))
    print("  served agent/oracle/demand (M): " + ", ".join(f"{D[i]['node'].replace('sink_','')}/{D[i]['k'][5:]} {r['detail']['served'][i]/1e6:.1f}/{r['oracle_detail']['served'][i]/1e6:.1f}/{r['detail']['demand'][i]/1e6:.1f}" for i in range(len(D))))
print("\n=== all listed episodes: disposal gap by slot (T, summed)")
for (node, k), v in sorted(agg.items(), key=lambda x: -x[1])[:12]:
    print(f"  {node:22s} {k:13s} {v/1e12:+.3f}")
