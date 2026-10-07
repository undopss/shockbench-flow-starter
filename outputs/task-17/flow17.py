"""Chip flow balance and timing, agent vs oracle (from gap17's JSON).  uv run python outputs/task-17/flow17.py <json>"""
import json, sys
from collections import defaultdict
import numpy as np

sys.path.insert(0, "outputs")
from variants import pick_episodes  # noqa
from shockbench_flow_agent.scoring import EpisodeSet, _world

rows = [r for r in json.loads(open(sys.argv[1]).read()) if r["oracle"] is not None]
meta = rows[0]["meta"]
es = EpisodeSet.build("full", "dev", entropy=0, n_jobs=1)
inst = _world(*es._spec[:2], int(rows[0]["episode"]), *es._spec[3:])[0]
K = inst.commodities
slots = [(inst.nodes[s.node].id, K[s.k].id) for s in inst.stock_slots]
D = meta["demands"]; F = meta["fabs"]
T = len(rows[0]["detail"]["lots_w"])
prod = {"chip_le": ["chip_le_raw"], "chip_mat": ["chip_mat_raw"]}
print("## chip balance per episode (mean, million units)")
for p in ("chip_le", "chip_mat"):
    fi = [f for f, m in enumerate(F) if m["product"] == p + "_raw"]
    di = [d for d, m in enumerate(D) if m["k"] == p]
    for who, det in (("agent", "detail"), ("oracle", "oracle_detail")):
        lots = np.mean([sum(r[det]["lots_started"][f] for f in fi) for r in rows]) / 1e6
        served = np.mean([sum(r[det]["served"][d] for d in di) for r in rows]) / 1e6
        lost = np.mean([sum(r[det]["lost"][d] for d in di) for r in rows]) / 1e6
        # lots of the last tau weeks cannot reach a sink in time
        late = np.mean([sum(np.array(r[det]["lots_w"])[-10:, f].sum() for f in fi) for r in rows]) / 1e6
        print(f"{p:9s} {who:7s} lots {lots:7.2f}  of which in the last 10 weeks {late:5.2f}  served {served:7.2f}  lost {lost:7.2f}")
    disp = defaultdict(float)
    for r in rows:
        for s, v in enumerate(r["detail"]["disposal"]):
            if slots[s][1].startswith(p):
                disp[slots[s]] += v / len(rows)
    top = sorted(disp.items(), key=lambda kv: -kv[1])[:6]
    print(f"   agent disposal of {p}* (units/episode):", ", ".join(f"{a}/{b} {v/1e6:.2f}M" for (a, b), v in top if v > 0))
print("\n## lost-sales gap (agent - oracle, T USD/episode) by quarter of the episode")
pi = np.array([d["pi"] for d in D])
q = np.array_split(np.arange(T), 4)
for p in ("chip_le", "chip_mat"):
    di = [d for d, m in enumerate(D) if m["k"] == p]
    out = []
    for idx in q:
        a = np.mean([(np.array(r["detail"]["lost_w"])[idx][:, di] * pi[di]).sum() for r in rows])
        o = np.mean([(np.array(r["oracle_detail"]["lost_w"])[idx][:, di] * pi[di]).sum() for r in rows])
        out.append(f"wk {idx[0]+1}-{idx[-1]+1}: {(a-o)/1e12:.3f} (agent {a/1e12:.3f}, oracle {o/1e12:.3f})")
    print(f"{p:9s}", " | ".join(out))
print("\n## fab lots gap (oracle - agent, M lots) per grid by quarter")
grids = sorted({m["grid"] for m in F if m["grid"]})
for g in grids:
    fi = [f for f, m in enumerate(F) if m["grid"] == g]
    out = []
    for idx in q:
        a = np.mean([np.array(r["detail"]["lots_w"])[idx][:, fi].sum() for r in rows])
        o = np.mean([np.array(r["oracle_detail"]["lots_w"])[idx][:, fi].sum() for r in rows])
        out.append(f"{(o-a)/1e6:6.2f}")
    print(f"{g:9s}", " ".join(out))
print("\n## per episode: lots deficit (oracle - agent, M) at grids CN / JP / SEA / KR, and chip lost-sales gap T")
for r in rows:
    def lots(det, g):
        return sum(r[det]["lots_started"][f] for f, m in enumerate(F) if m["grid"] == g) / 1e6
    gaps = [lots("oracle_detail", g) - lots("detail", g) for g in ("grid_cn", "grid_jp", "grid_sea", "grid_kr", "grid_us", "grid_tw")]
    cg = (r["agent"]["shortage"] - r["oracle"]["shortage"]) / 1e12
    print(f"ep {r['episode']:3d} lvl {r['stratum']}  CN {gaps[0]:6.2f} JP {gaps[1]:6.2f} SEA {gaps[2]:6.2f} KR {gaps[3]:6.2f} US {gaps[4]:6.2f} TW {gaps[5]:6.2f}  chip gap {cg:.3f}")
