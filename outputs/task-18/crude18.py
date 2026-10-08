"""Crude to grid_sea/jp/cn: lane capacities, source supply, what the agent ships (Full ep 0)."""
import sys
from pathlib import Path
import numpy as np
from shockbench_flow.dynamics.env import rollout
from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
from shockbench_flow_agent.scoring import EpisodeSet, _metered_shim, _policy_seed, _world
from shockbench_flow_agent.shim import load_agent_class

n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
es = EpisodeSet.build("full", [n], entropy=0, n_jobs=1)
task, entropy, regime, reps, cache = es._spec
inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
ids = [nd.id for nd in inst.nodes]
com = [c.id for c in inst.commodities]
print("marks fields", [f for f in dir(marks) if not f.startswith("_")])
crude = com.index("crude")
E = [(i, ids[e.tail], ids[e.head]) for i, e in enumerate(inst.edges) if crude in (e.K or [])]
for name in ("u", "open", "c", "tau"):
    if hasattr(marks, name):
        arr = np.asarray(getattr(marks, name))
        print(name, arr.shape)
for i, a, b in E:
    print(f"edge {i:3d} {a:15s} -> {b:12s} u mean {np.asarray(marks.u)[:, i].mean():9.1f} min {np.asarray(marks.u)[:, i].min():9.1f}")
for s, (node, k) in enumerate(inst.slot_keys if hasattr(inst, "slot_keys") else []):
    pass
supply = np.asarray(marks.supply)
for (node, k), s in inst.slot_index.items():
    if k == crude and ids[node].startswith("src"):
        print("supply", ids[node], supply[:, s].mean(), supply[:, s].min())
pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
shim = _metered_shim(load_agent_class(str(Path("agents/mpc_fab3").resolve()), "sub_fab3"), None)
traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=fallback)
R = traj.records
tot = {}
for r in R:
    for (e, k, lane), q in r.x.items():
        if k == crude:
            tot[e] = tot.get(e, 0.0) + q
for i, a, b in E:
    print(f"edge {i:3d} {a:15s} -> {b:12s} shipped/wk {tot.get(i, 0.0) / len(R):9.1f}")
for g in ("grid_sea", "grid_jp", "grid_cn", "grid_kr", "grid_tw", "grid_in", "grid_us", "grid_eu"):
    gi = inst.grids.index(ids.index(g))
    sh = inst.nodes[ids.index(g)].grid.shares.get(crude, 0)
    print(g, "crude need/wk", sh * np.asarray(marks.G_bar)[:, gi].mean(), "shed/wk", np.mean([r.shed[gi] for r in R]))
