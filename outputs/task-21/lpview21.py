"""Task 21: what the chip LP believes vs what happens (from play_<tag>.json logs).

    uv run python outputs/task-21/lpview21.py nolim
"""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
rows = json.loads((HERE / f"play_{sys.argv[1] if len(sys.argv) > 1 else 'nolim'}.json").read_text())
r0 = rows[0]; dem = r0["demands"]; pi = np.array([d["pi"] for d in dem]); fabs = r0["fabs"]
# planned fill over the window (LP's view) vs realized fill over the same weeks
pf, rf, pdm = np.zeros(len(dem)), np.zeros(len(dem)), np.zeros(len(dem))
cap_ratio = np.zeros(len(fabs)); start_ratio = np.zeros(len(fabs)); n = 0
for r in rows:
    S = np.asarray(r["served_w"]); D = np.asarray(r["demand_w"]); L = np.asarray(r["lots_w"])
    for e in r["log"]:
        w, H = e["week"], e["H"]
        sv, dm = np.asarray(e["serve"]), np.asarray(e["dem"])
        for j, row in enumerate(e["sink_rows"]):
            pf[row] += sv[j].sum(); pdm[row] += dm[j].sum()
            rf[row] += S[w - 1:w - 1 + H, row].sum()
        st, fc = np.asarray(e["start"]), np.asarray(e["fabcap"])
        for j, fp in enumerate(e["fab_pos"]):
            cap_ratio[fp] += fc[j, 0]; start_ratio[fp] += st[j, 0]
        n += 1
print("LP's planned fill over its window vs realized fill over the same weeks (pi-weighted per sink x product):")
for d in np.argsort(-pi * pdm):
    print(f"  {dem[d]['node']:>9} {dem[d]['k']:<9} LP plans {pf[d] / pdm[d]:6.1%}   realized {rf[d] / pdm[d]:6.1%}")
print(f"  ALL (pi-weighted)   LP plans {np.sum(pi * pf) / np.sum(pi * pdm):6.1%}   realized {np.sum(pi * rf) / np.sum(pi * pdm):6.1%}")
print("\nweek-0 fab cap in the LP vs planned starts vs realized starts (mean per week, k lots):")
for fi, f in enumerate(fabs):
    real = np.mean([np.asarray(r["lots_w"])[:, fi].mean() for r in rows])
    print(f"  {f:<20} LP cap {cap_ratio[fi] / n * len(fabs) / len(fabs) / 1e3 * 1:8.1f}  LP start {start_ratio[fi] / n / 1e3:8.1f}  realized {real / 1e3:8.1f}  nameplate {r0['fab_cap0'][fi] / 1e3:8.1f}")
