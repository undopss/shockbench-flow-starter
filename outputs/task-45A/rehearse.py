"""Task 45A rehearsal: per-episode RSS of the baseline (mpc_final) from the variants run, by level."""
import json, sys
import numpy as np
from shockbench_flow_agent.scoring import EpisodeSet

r = json.load(open(sys.argv[1]))
es = EpisodeSet.build(r["task"], int(r["episodes"]), entropy=r["entropy"], n_jobs=1)
J = r["results"]["final"]["J"]
rows = []
for ref, j in zip(es.references, J):
    n, o = ref["J_naive_cents"], ref["J_oracle_cents"]
    rss = None if (o is None or ref["excluded"]) else (n - j) / (n - o)
    rows.append((ref["episode"], ref["stratum"], rss, n / 100, o / 100 if o else None, j / 100, ref["harm_usd"]))
def q(v):
    v = np.array(v); return f"n={len(v):2d} min {v.min():.3f} p10 {np.percentile(v,10):.3f} med {np.median(v):.3f} p90 {np.percentile(v,90):.3f} max {v.max():.3f} mean {v.mean():.3f}"
ok = [x for x in rows if x[2] is not None]
print("per-episode RSS of mpc_final (baseline), full", r["entropy"])
print("all  ", q([x[2] for x in ok]))
for s in (1, 2, 3, 4):
    v = [x[2] for x in ok if x[1] == s]
    if v: print(f"L{s}   ", q(v))
print("excluded:", [x[0] for x in rows if x[2] is None])
print("\nep  L   RSS     naive USD      oracle USD     agent USD      gap-to-oracle USD   harm USD")
for x in sorted(ok, key=lambda x: x[2]):
    print(f"{x[0]:2d}  {x[1]}  {x[2]:.4f}  {x[3]:14.4g} {x[4]:14.4g} {x[5]:14.4g} {x[5]-x[4]:14.4g} {x[6]:14.4g}")
