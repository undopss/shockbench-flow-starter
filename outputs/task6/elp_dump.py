"""Task 6: the energy LP's plan at week W for the pools of one grid (and the sources they share)."""
import sys, copy
from pathlib import Path
import numpy as np
from shockbench_flow.dynamics.env import rollout
from shockbench_flow_agent.scoring import EpisodeSet, _metered_shim, _policy_seed, _world
from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
from shockbench_flow_agent.shim import load_agent_class

task, ep, agent, W, gname = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), sys.argv[5]
es = EpisodeSet.build(task, "dev", entropy=0, n_jobs=1)
_t, entropy, regime, reps, cache = es._spec
inst, omega, marks, fallback = _world(task, entropy, ep, reps, cache)
root = str(Path(agent).resolve())
cls = load_agent_class(root, f"submission_{Path(root).stem}")
H_ = {}


class Wrap(cls):
    def __init__(self, config):
        super().__init__(config); H_["a"] = self

    def act(self, obs):
        a = super().act(obs)
        if int(obs["week"][0]) == W:
            H_["d"] = copy.deepcopy(self.edebug); H_["obs"] = {k: np.array(v) for k, v in obs.items()}; H_["act"] = np.array(a["flows"])
        return a


rollout(inst, _metered_shim(Wrap, None), omega, regime, _policy_seed(entropy, ep, NO_ZIP_SHA256), marks=marks, fallback=fallback)
a, d = H_["a"], H_["d"]
nodes = inst.nodes; ks = [c.id for c in inst.commodities]
x, H = d["x"], d["H"]
off_b, off_I, off_r, off_o, off_q, off_sf = d["off"]
g = [i for i, n in enumerate(nodes) if n.id == gname][0]
pools = [p_i for p_i, p in enumerate(a.pools) if p["grid"] == g]
for p_i in pools:
    p = a.pools[p_i]
    print(f"pool {ks[p['k']]}: I0={d['I0'][p_i]:.0f} floor={d['floor'][p_i]:.0f} burn={d['burn'][p_i]:.0f} fixed_in={np.round(d['fixed_in'][p_i]).astype(int).tolist()}")
    print("   I  =", np.round(x[off_I + p_i * H: off_I + p_i * H + H]).astype(int).tolist())
    print("   sf =", np.round(x[off_sf + p_i * H: off_sf + p_i * H + H]).astype(int).tolist())
    srcs = set()
    for j, ls in enumerate(a.lp_slots):
        if ls["pool"] == p_i:
            srcs.add((ls["source"], ls["k"]))
            print(f"   slot {ls['slot']} {nodes[ls['source']].id}->{nodes[inst.edges[ls['route'][-1]].head].id} lead={d['lead'][j]} hi0={d['hi'][j*H]:.0f} plan={np.round(x[j*H:j*H+8]).astype(int).tolist()} act={H_['act'][ls['slot']]:.0f}")
    for (src, k) in srcs:
        js = d["by_source"].get((src, k), [])
        print(f"   source {nodes[src].id} {ks[k]}: feeds pools {sorted({nodes[a.pools[a.lp_slots[j]['pool']]['grid']].id for j in js})}")
        for j in js:
            ls = a.lp_slots[j]
            print(f"       -> {nodes[a.pools[ls['pool']]['grid']].id:9s} slot {ls['slot']} hi0={d['hi'][j*H]:.0f} plan0={x[j*H]:.0f}")
