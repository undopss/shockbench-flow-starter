"""Task 21: one episode: lost value by sink x product per 8-week block, agent minus avail-LP (T USD); and the episode's events."""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
ep = int(sys.argv[1]); tag = sys.argv[2] if len(sys.argv) > 2 else "nolim"; mode = sys.argv[3] if len(sys.argv) > 3 else "avail"
rows = {r["episode"]: r for r in json.loads((HERE / f"play_{tag}.json").read_text())}
bnd = json.loads((HERE / f"bound_{tag}.json").read_text())
r = rows[ep]; dem = r["demands"]; pi = np.array([d["pi"] for d in dem])
A = np.asarray(r["lost_w"]) * pi; V = np.asarray(bnd[str(ep)][mode]["lost_w"]) * pi
d = (A - V)
top = np.argsort(-d.sum(0))[:6]
print("block   " + " ".join(f"{dem[j]['node'][5:]}/{dem[j]['k'][5:]:>4}" for j in top))
for b in range(0, 104, 8):
    print(f"{b + 1:>3}-{b + 8:<4}" + " ".join(f"{d[b:b + 8, j].sum() / 1e12:9.3f}" for j in top))
