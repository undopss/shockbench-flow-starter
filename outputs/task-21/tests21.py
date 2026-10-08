"""Task 21: the offline tests vs the baseline play (nolim), paired per episode: RSS and cost deltas (T USD/episode)."""
import json
from pathlib import Path
import numpy as np
from shockbench_flow_agent.scoring import EpisodeSet
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from variants import pick_episodes
es = EpisodeSet.build("full", pick_episodes("full", 0, "devpick:2,2,1,1", 4), entropy=0, n_jobs=4)
order = [int(n) for n in es.episodes]
def load(t):
    r = {x["episode"]: x for x in json.loads((HERE / f"play_{t}.json").read_text())}
    return [r[n] for n in order]
base = load("nolim")
tests = [("nolim", "baseline (mpc_fab3sell, CPU guards off)"), ("tdem", "true future demand"),
         ("tcap", "true future edge caps / open / prohibitions"), ("tsup", "true future material supply"),
         ("tfab", "true fab starts (the baseline's realized lots as fab cap)"), ("h52", "chip_H 52 instead of 24"),
         ("all", "tdem + tcap + tfab + H52"), ("kshare", "strait container throughput (kappa_ct) in the chip LP"),
         ("knet", "same, net of the queue's drain"), ("lew5", "wafer buffer cost x5 at leading-edge/memory fabs"),
         ("buf5tk", "wafer buffer 5 weeks at TW/KR fabs"), ("buf5", "wafer buffer 5 weeks everywhere"),
         ("mega", "everything above at once (+buffer 5, le x5, kappa share, true supply)"),
         ("nobuf", "no wafer buffer (reference)")]
print(f"{'test':<8} {'RSS':>7} {'dRSS':>8} {'d shortage':>11} {'d shed':>8} {'d total':>8}  min/max dRSS per ep   what")
b_rss = es.rss([r["J_agent_cents"] for r in base])["rss"]
for t, what in tests:
    try:
        rows = load(t)
    except FileNotFoundError:
        continue
    rss = es.rss([r["J_agent_cents"] for r in rows])["rss"]
    per = [es.rss([r["J_agent_cents"] if i == j else b["J_agent_cents"] for j, (r, b) in enumerate(zip(rows, base))])["rss"] - b_rss for i in range(len(rows))]
    ds = np.mean([r["cost"]["shortage"] - b["cost"]["shortage"] for r, b in zip(rows, base)]) / 1e12
    dh = np.mean([r["cost"]["shed"] - b["cost"]["shed"] for r, b in zip(rows, base)]) / 1e12
    dt = np.mean([r["J_agent_cents"] - b["J_agent_cents"] for r, b in zip(rows, base)]) / 1e14
    print(f"{t:<8} {rss:7.4f} {rss - b_rss:+8.4f} {ds:+11.4f} {dh:+8.4f} {dt:+8.4f}  {min(per):+.4f}/{max(per):+.4f}   {what}")
