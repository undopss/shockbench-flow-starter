"""Paired 90% interval of each variant vs the first, from a (partial) variants.py results.json."""
import json, sys
import numpy as np
from shockbench_flow_agent.scoring import LEVEL, N_BOOT, EpisodeSet, _boot_stats, _interval
d = json.load(open(sys.argv[1]))
eps = d["episodes"]
es = EpisodeSet.build(d["task"], eps if eps == "dev" else int(eps), entropy=int(d["entropy"]), n_jobs=1)
res = d["results"]; names = list(res); b = res[names[0]]
pooled = es.rss(b["J"]).get("pooled", True)
for n in names[1:]:
    ba, bb = _boot_stats(es.references, [res[n]["J"], b["J"]], pooled, N_BOOT, 0)
    diff = ba - bb
    lo, hi = _interval(diff, LEVEL)
    nb = sum(x < y for x, y in zip(res[n]["J"], b["J"])); ne = sum(x == y for x, y in zip(res[n]["J"], b["J"]))
    print(f"{n:16s} {res[n]['rss']:.4f} diff {res[n]['rss'] - b['rss']:+.4f} [{lo:+.4f}, {hi:+.4f}] "
          f"episodes cheaper {nb}/{len(b['J'])} equal {ne}")
