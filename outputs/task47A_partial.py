"""Print the paired table from a (possibly partial) variants.py results.json: uv run python outputs/task47A_partial.py <results.json>"""
import json, sys
import numpy as np
from shockbench_flow_agent.scoring import LEVEL, N_BOOT, EpisodeSet, _boot_stats, _interval
d = json.load(open(sys.argv[1])); res = d["results"]; names = list(res)
es = EpisodeSet.build(d["task"], int(d["episodes"]), entropy=d["entropy"], n_jobs=4)
base = res[names[0]]; pooled = es.rss(base["J"]).get("pooled", True)
print(f"{'variant':12s} {'RSS':>7s} {'L1':>6s} {'L2':>6s} {'L3':>6s} {'L4':>6s} {'diff':>8s}  interval  better% fallb s")
for n in names:
    r = res[n]; lv = r["levels"] or {}
    if n == names[0]: dd, lo, hi, sh = 0, 0, 0, float("nan")
    else:
        ba, bb = _boot_stats(es.references, [r["J"], base["J"]], pooled, N_BOOT, 0); df = ba - bb
        lo, hi = _interval(df, LEVEL); dd = r["rss"] - base["rss"]; sh = float(np.mean(df > 0)) * 100
    cells = " ".join(f"{lv[s]:6.3f}" if lv.get(s) is not None else "     -" for s in ("1","2","3","4"))
    print(f"{n:12s} {r['rss']:7.4f} {cells} {dd:+8.4f}  [{lo:+.4f}, {hi:+.4f}] {sh:6.1f}% {r['fallback_weeks']:5d} {r['seconds']}")
