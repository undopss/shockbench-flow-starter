"""Task 45B rehearsal: per-episode RSS distribution of the baseline from the runner's cached rows."""
import json, sys
import numpy as np
from shockbench_flow_agent.scoring import EpisodeSet

rows = json.load(open(sys.argv[1]))
es = EpisodeSet.build("full", 20, entropy=1827351891)
ref = {r["episode"]: r for r in es.references}
out = []
for r in rows:
    f = ref[r["episode"]]
    rss = (f["J_naive_cents"] - r["J_policy_cents"]) / (f["J_naive_cents"] - f["J_oracle_cents"])
    out.append({"episode": r["episode"], "level": f["stratum"], "rss": rss, "harm_usd": f["harm_usd"],
                "gap_usd": (r["J_policy_cents"] - f["J_oracle_cents"]) / 100, "fallback_weeks": r["fallback_weeks"],
                "cpu_weeks": r["cpu_weeks"], "seconds": r["seconds"]})
print("es.rss check:", es.rss([r["J_policy_cents"] for r in rows]))
def line(name, v):
    q = np.percentile(v, [0, 10, 50, 90, 100])
    print(f"{name:8s} n={len(v):2d}  min {q[0]:.4f}  p10 {q[1]:.4f}  median {q[2]:.4f}  p90 {q[3]:.4f}  max {q[4]:.4f}  mean {np.mean(v):.4f}")
line("all", [o["rss"] for o in out])
for lv in sorted({o["level"] for o in out}):
    line(f"L{lv}", [o["rss"] for o in out if o["level"] == lv])
s = sorted(out, key=lambda o: o["rss"])
print("\nepisode level    RSS   gap to oracle USD   harm USD  play s  fallback cpu_over")
for o in s:
    print(f"{o['episode']:7d} {o['level']:5d} {o['rss']:.4f} {o['gap_usd']:18.4e} {o['harm_usd']:10.3e} {o['seconds']:6.0f} {o['fallback_weeks']:8d} {o['cpu_weeks']:8d}")
json.dump(out, open("outputs/task-45B/per_episode.json", "w"), indent=1)
