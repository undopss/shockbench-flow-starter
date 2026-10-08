"""Per-fuel supply vs need on Full episode n: source supply, edge caps, shipped, chokepoint queues, CN/JP stocks."""
import sys
from pathlib import Path
import numpy as np
from shockbench_flow.dynamics.env import rollout
from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
from shockbench_flow_agent.scoring import EpisodeSet, _metered_shim, _policy_seed, _world
from shockbench_flow_agent.shim import load_agent_class

n = int(sys.argv[1]); fuel = sys.argv[2]; agent = sys.argv[3] if len(sys.argv) > 3 else "agents/mpc_fab3"
es = EpisodeSet.build("full", [n], entropy=0, n_jobs=1)
task, entropy, regime, reps, cache = es._spec
inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
ids = [nd.id for nd in inst.nodes]
com = [c.id for c in inst.commodities]
k = com.index(fuel)
u = np.asarray(marks.u)
pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
shim = _metered_shim(load_agent_class(str(Path(agent).resolve()), "sub_x"), None)
traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=fallback)
R = traj.records
T = len(R)
tot = {}
for r in R:
    for (e, kk, lane), q in r.x.items():
        if kk == k:
            tot[e] = tot.get(e, 0.0) + q
for i, e in enumerate(inst.edges):
    if k in (e.K or []):
        print(f"edge {i:3d} {ids[e.tail]:15s} -> {ids[e.head]:12s} u mean {u[:, i].mean():9.1f} min {u[:, i].min():9.1f} shipped/wk {tot.get(i, 0) / T:9.1f}")
sup = np.asarray(marks.supply)
for (node, kk), s in inst.slot_index.items():
    if kk == k and ids[node].startswith(("src", "chk")):
        st = np.array([r.stock[s] for r in R]); dis = np.array([r.disposal[s] for r in R])
        print(f"{ids[node]:15s} supply/wk {sup[:, s].mean():9.1f} end stock mean {st.mean():9.1f} disposal/wk {dis.mean():8.1f}")
for g in inst.grids:
    gi = inst.grids.index(g)
    sh = inst.nodes[g].grid.shares.get(k, 0)
    if sh <= 0:
        continue
    s = inst.slot_index[(g, k)]
    burn = np.array([r.segment.get((gi, k), 0) for r in R])
    print(f"{ids[g]:9s} need/wk {sh * np.asarray(marks.G_bar)[:, gi].mean():9.1f} burn/wk {burn.mean():9.1f} "
          f"grid stock mean {np.mean([r.stock[s] for r in R]):9.1f} shed/wk {np.mean([r.shed[gi] for r in R]):8.1f} "
          f"fabE/wk {np.mean([sum(r.energy[f] for f in inst.grid_fabs[gi]) for r in R]):7.1f}")
for (node, kk), s in inst.slot_index.items():
    if kk == k and ids[node].startswith("term"):
        print(f"{ids[node]:10s} terminal stock mean {np.mean([r.stock[s] for r in R]):9.1f} disposal/wk {np.mean([r.disposal[s] for r in R]):8.1f}")
