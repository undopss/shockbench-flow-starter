"""Pool several single-variant results.json files (one agent) into one board-weighted score + stratified bootstrap.
uv run python outputs/task-46/pool46.py a.json b.json ..."""
import json, sys
from pathlib import Path
import numpy as np
from shockbench_flow.evaluation.results import episode_rss
from shockbench_flow_agent.scoring import EpisodeSet, _boot_stats, _interval
refs, J = [], []
for f in sys.argv[1:]:
    d = json.loads(Path(f).read_text())
    es = EpisodeSet.build(d["task"], int(d["episodes"]), entropy=int(d["entropy"]), n_jobs=4)
    refs += [dict(r) for r in es.references]; J += next(iter(d["results"].values()))["J"]
t = episode_rss([{**r, "J_policy_cents": int(j)} for r, j in zip(refs, J)])
b = _boot_stats(refs, [J], True, 2000, 0)[0]; lo, hi = _interval(b, 0.9)
print(f"pooled {len(J)} episodes: RSS {t['pooled']:.4f} 90% [{lo:.4f}, {hi:.4f}] SE {np.nanstd(b):.4f}; per level",
      {s: round(v['rss'], 4) for s, v in t['strata'].items()})
