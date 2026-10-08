"""Task 27: re-print a variants.py round with another entry as the baseline (variants.py drops every params.json when
it copies an agent, so a plain {"agent": "agents/mpc_fab3sell"} plays WITHOUT its params.json).

    uv run python outputs/task-27/rebase.py outputs/variants/<round>/results.json clim_off [n_jobs]
"""
import json
import sys
from pathlib import Path

import numpy as np
from shockbench_flow_agent.scoring import LEVEL, N_BOOT, EpisodeSet, _boot_stats, _interval

sys.path.insert(0, "outputs")
from variants import pick_episodes  # noqa: E402

path, bname = sys.argv[1], sys.argv[2]
n_jobs = int(sys.argv[3]) if len(sys.argv) > 3 else 4
R = json.loads(Path(path).read_text())
task, entropy, episodes, res = R["task"], R["entropy"], R["episodes"], R["results"]
es = EpisodeSet.build(task, pick_episodes(task, entropy, episodes, n_jobs), entropy=entropy, n_jobs=n_jobs)
base = res[bname]
pooled = es.rss(base["J"]).get("pooled", True)
print(f"{task}, entropy {entropy}, {len(base['J'])} episodes ({episodes}); diff = variant - {bname}, "
      f"{int(LEVEL * 100)}% paired interval")
print(f"{'variant':24s} {'RSS':>7s} {'L1':>6s} {'L2':>6s} {'L3':>6s} {'L4':>6s} {'diff':>8s}  interval               better%")
for name, r in res.items():
    lv = r["levels"] or {}
    if name == bname:
        d, lo, hi, share = 0.0, 0.0, 0.0, float("nan")
    else:
        ba, bb = _boot_stats(es.references, [r["J"], base["J"]], pooled, N_BOOT, 0)
        diff = ba - bb
        lo, hi = _interval(diff, LEVEL) or (float("nan"), float("nan"))
        d, share = r["rss"] - base["rss"], float(np.mean(diff > 0)) * 100
    cells = " ".join(f"{lv[s]:6.3f}" if lv.get(s) is not None else "     -" for s in ("1", "2", "3", "4"))
    flag = "  <-- better" if lo > 0 else ("  <-- worse" if hi < 0 else "")
    print(f"{name:24s} {r['rss']:7.4f} {cells} {d:+8.4f}  [{lo:+.4f}, {hi:+.4f}]  {share:6.1f}%{flag}")
