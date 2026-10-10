"""How noisy is a 5-per-level (dev-shaped) score? Resample 5 episodes per level from a fresh run's per-episode values,
using the board weights.  uv run python outputs/task-46/dev5.py <results.json>"""
import json, sys
from pathlib import Path
import numpy as np
from shockbench_flow_agent.scoring import EpisodeSet
W = (0.5, 0.3, 0.15, 0.05)
doc = json.loads(Path(sys.argv[1]).read_text()); J = next(iter(doc["results"].values()))["J"]
es = EpisodeSet.build(doc["task"], int(doc["episodes"]), entropy=int(doc["entropy"]), n_jobs=4)
rng = np.random.default_rng(0)
by = {s: np.array([i for i, r in enumerate(es.references) if r["stratum"] == s and r["excluded"] is None]) for s in (1, 2, 3, 4)}
nv = np.array([r["J_naive_cents"] for r in es.references], float); orc = np.array([r["J_oracle_cents"] or 0 for r in es.references], float); J = np.array(J, float)
out = []
for _ in range(20000):
    num = den = 0.0
    for w, s in zip(W, (1, 2, 3, 4)):
        p = rng.choice(by[s], 5)
        num += w * (nv[p] - J[p]).mean(); den += w * (nv[p] - orc[p]).mean()
    out.append(num / den)
out = np.array(out)
print(f"dev-shaped (5/level) score from this pool: mean {out.mean():.4f} SD {out.std():.4f} 5-95% [{np.quantile(out,.05):.4f}, {np.quantile(out,.95):.4f}]; P(>=0.8076) {np.mean(out >= 0.8076):.3f}")
