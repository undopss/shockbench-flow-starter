"""Task 46 analysis: score, per level, episode counts, 90% bootstrap interval of the score itself, per-episode RSS
distribution, fallback weeks.  uv run python outputs/task-46/an46.py <results.json> [variant]"""
import json, sys
from collections import Counter
from pathlib import Path
import numpy as np
from shockbench_flow_agent.scoring import EpisodeSet, _boot_stats, _interval, _kept

doc = json.loads(Path(sys.argv[1]).read_text())
name = sys.argv[2] if len(sys.argv) > 2 else next(iter(doc["results"]))
r = doc["results"][name]
ep = doc["episodes"]
ep = int(ep) if str(ep).isdigit() else ep
es = EpisodeSet.build(doc["task"], ep, entropy=int(doc["entropy"]), n_jobs=4)
J = r["J"]
t = es.rss(J)
refs = es.references
kept = set(_kept(refs))
cnt = Counter(x["stratum"] for x in refs)
cntk = Counter(refs[i]["stratum"] for i in range(len(refs)) if i in kept)
boot = _boot_stats(refs, [J], t["pooled"], 2000, 0)[0]
lo, hi = _interval(boot, 0.9)
print(f"{doc['task']} entropy {doc['entropy']} {len(J)} episodes, {name}")
print(f"RSS {t['rss']:.4f}  90% bootstrap [{lo:.4f}, {hi:.4f}]  SE {np.nanstd(boot):.4f}  (rss_all unweighted {t['rss_all']:.4f})")
print("per level:", {k: round(v, 4) if v is not None else None for k, v in t["rss_by_stratum"].items()})
print("episodes per level:", dict(sorted(cnt.items())), " kept:", dict(sorted(cntk.items())), f" excluded {len(refs) - len(kept)}")
print("fallback weeks:", r["fallback_weeks"])
print("per-episode (naive-J)/(naive-oracle), kept episodes:")
for s in sorted(cnt):
    v = np.array([(x["J_naive_cents"] - j) / (x["J_naive_cents"] - x["J_oracle_cents"])
                  for i, (x, j) in enumerate(zip(refs, J)) if i in kept and x["stratum"] == s
                  and x["J_naive_cents"] > x["J_oracle_cents"]])
    if v.size:
        q = np.quantile(v, [0, .1, .5, .9, 1])
        print(f"  L{s} n={v.size}: min {q[0]:+.3f} p10 {q[1]:+.3f} med {q[2]:+.3f} p90 {q[3]:+.3f} max {q[4]:+.3f}")
