"""Task 21: per episode, fab lots the avail-LP starts beyond the agent in weeks the agent's fab had too few wafers
(wafer-limited) vs enough wafers (power-limited), by 13-week block (M lots), and the value at pi-ish (le 50k, mat 10k)."""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
tag = sys.argv[1] if len(sys.argv) > 1 else "nolim"; mode = sys.argv[2] if len(sys.argv) > 2 else "avail"
rows = json.loads((HERE / f"play_{tag}.json").read_text()); bnd = json.loads((HERE / f"bound_{tag}.json").read_text())
fabs = rows[0]["fabs"]
for r in rows:
    al = np.asarray(r["lots_w"]); ol = np.asarray(bnd[str(r["episode"])][mode]["lots_w"]); wf = np.asarray(r["wafer_w"])
    wprev = np.vstack([np.full((1, al.shape[1]), 1e18), wf[:-1]])
    d = np.maximum(ol - al, 0); wl = d * (wprev < ol * 0.999)
    tot = wl.sum(0)
    top = [i for i in np.argsort(-tot) if tot[i] > 1e5][:4]
    print(f"ep {r['episode']}: wafer-limited deficit {wl.sum() / 1e6:.2f}M lots, power-limited {(d - wl).sum() / 1e6:.2f}M")
    for i in top:
        print(f"   {fabs[i]:<18} " + " ".join(f"{wl[b:b + 13, i].sum() / 1e6:5.2f}" for b in range(0, 104, 13)))
