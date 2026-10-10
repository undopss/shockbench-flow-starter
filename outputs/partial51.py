"""Partial paired table from a variants round's results.json (for variants already played)."""
import json, sys
import numpy as np
from shockbench_flow_agent.scoring import LEVEL, N_BOOT, EpisodeSet, _boot_stats, _interval
d = json.load(open(sys.argv[1]))
es = EpisodeSet.build(d["task"], int(d["episodes"]) if str(d["episodes"]).isdigit() else d["episodes"], entropy=d["entropy"], n_jobs=1)
res = d["results"]; names = list(res); base = res[names[0]]
pooled = es.rss(base["J"]).get("pooled", True)
print(f"PARTIAL {d['task']}, entropy {d['entropy']}, {len(base['J'])} episodes; diff = variant - {names[0]}")
for n in names:
    r = res[n]; lv = r["levels"] or {}
    if n == names[0]: d0, lo, hi, sh = 0.0, 0.0, 0.0, float("nan")
    else:
        ba, bb = _boot_stats(es.references, [r["J"], base["J"]], pooled, N_BOOT, 0); diff = ba - bb
        lo, hi = _interval(diff, LEVEL); d0 = r["rss"] - base["rss"]; sh = float(np.mean(diff > 0)) * 100
    cells = " ".join(f"{lv[s]:6.3f}" if lv.get(s) is not None else "     -" for s in ("1", "2", "3", "4"))
    print(f"{n:24s} {r['rss']:7.4f} {cells} {d0:+8.4f}  [{lo:+.4f}, {hi:+.4f}]  {sh:6.1f}%  {r['fallback_weeks']:5d}")
