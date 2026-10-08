"""Task 21: lost-sales value by 8-week block and by episode: agent vs capped vs avail vs free (T USD)."""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
tag = sys.argv[1] if len(sys.argv) > 1 else "nolim"
rows = json.loads((HERE / f"play_{tag}.json").read_text()); bnd = json.loads((HERE / f"bound_{tag}.json").read_text())
pi = np.array([d["pi"] for d in rows[0]["demands"]])
def lw(x): return np.asarray(x) @ pi
A = np.mean([lw(r["lost_w"]) for r in rows], axis=0)
M = {m: np.mean([lw(bnd[str(r["episode"])][m]["lost_w"]) for r in rows], axis=0) for m in ("capped", "avail", "free")}
print("weeks     agent  a-capped  a-avail  a-free   (T USD/episode)")
for b in range(0, 104, 8):
    s = slice(b, b + 8)
    print(f"{b + 1:>3}-{b + 8:<4} {A[s].sum() / 1e12:7.3f} {(A[s] - M['capped'][s]).sum() / 1e12:8.3f} {(A[s] - M['avail'][s]).sum() / 1e12:8.3f} {(A[s] - M['free'][s]).sum() / 1e12:7.3f}")
print("per episode, weeks 81-104 vs 1-80: a-avail")
for r in rows:
    a = lw(r["lost_w"]); v = lw(bnd[str(r["episode"])]["avail"]["lost_w"])
    print(f"  ep {r['episode']:>3}: 1-80 {(a[:80] - v[:80]).sum() / 1e12:.3f}  81-104 {(a[80:] - v[80:]).sum() / 1e12:.3f}")
