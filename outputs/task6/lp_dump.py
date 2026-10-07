"""Task 6: play an agent on one Full dev episode up to week W and print the chip LP's plan at W."""
import sys
from pathlib import Path
import numpy as np
from shockbench_flow.dynamics.env import rollout
from shockbench_flow_agent.scoring import EpisodeSet, _metered_shim, _policy_seed, _world
from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
from shockbench_flow_agent.shim import load_agent_class

task, ep, agent, W = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
es = EpisodeSet.build(task, "dev", entropy=0, n_jobs=1)
_t, entropy, regime, reps, cache = es._spec
inst, omega, marks, fallback = _world(task, entropy, ep, reps, cache)
root = str(Path(agent).resolve())
cls = load_agent_class(root, f"submission_{Path(root).stem}")
holder = {}


class Stop(Exception):
    pass


class Wrap(cls):
    def __init__(self, config):
        super().__init__(config)
        holder["a"] = self

    def act(self, obs):
        a = super().act(obs)
        if int(obs["week"][0]) == W:
            import copy
            holder["debug"] = copy.deepcopy(getattr(self.chips, "debug", None))
        return a


try:
    rollout(inst, _metered_shim(Wrap, None), omega, regime, _policy_seed(entropy, ep, NO_ZIP_SHA256), marks=marks, fallback=fallback)
except Stop:
    pass
except Exception as e:
    print("rollout:", type(e), e)
a = holder["a"]; cp = a.chips; d = holder["debug"]
x, H = d["x"], d["H"]
off_I, off_d, off_f, off_o, off_s, off_m = d["off"]
nodes = inst.nodes
print("week", d["week"], "H", H)
for fi, f in enumerate(cp.fabs):
    st = x[off_f + fi * H: off_f + fi * H + H]
    print(f"{nodes[f['node']].id:20s} cap_hi={d['hi'][off_f + fi * H]:9.0f} I0_wafer={d['I0'][f['in']]:9.0f} plan={np.round(st[:12]).astype(int).tolist()}")
for q, (oi, pi) in enumerate(d["pairs"]):
    o = cp.osats[oi]
    v = x[off_o + q * H: off_o + q * H + H]
    print(f"osat {nodes[inst.osats[oi]].id if False else oi} pair {pi} thr={o['thr0']:9.0f} plan={np.round(v[:12]).astype(int).tolist()}")
for j, sk in enumerate(cp.sinks):
    sv = x[off_s + j * H: off_s + j * H + H]
    print(f"sink row {sk['row']} pi={sk['pi']:.0f} dem={np.round(d['dem'][j][:6]).astype(int).tolist()} served={np.round(sv[:12]).astype(int).tolist()}")
obs_like = None
tail = __import__("collections").defaultdict(list)
for j, ls in enumerate(cp.lp_slots):
    src = cp.pos[ls["src"]]; dst = cp.pos[ls["dst"]]
    sn, dn = nodes[src["node"]].id, nodes[dst["node"]].id
    if "us_" in sn or "us_" in dn:
        xs = x[j * H: j * H + 12]
        print(f"slot {ls['slot']:4d} {sn:18s}->{dn:12s} k={ls['k']} route={ls['route']} chk={ls['chk']} hi0={d['hi'][j*H]:9.0f} plan={np.round(xs).astype(int).tolist()}")
print("---- OSAT -> sink slots")
agg = __import__("collections").defaultdict(float); aggp = __import__("collections").defaultdict(float)
first_edge_k = __import__("collections").defaultdict(set)
for j, ls in enumerate(cp.lp_slots):
    src = cp.pos[ls["src"]]; dst = cp.pos[ls["dst"]]
    if src["kind"] == "osat" and dst["kind"] == "sink":
        key = (nodes[dst["node"]].id, ls["k"])
        agg[key] += d["hi"][j * H]; aggp[key] += x[j * H + 3]
        first_edge_k[ls["first"]].add(ls["k"])
        print(f"slot {ls['slot']:4d} {nodes[src['node']].id:8s}->{nodes[dst['node']].id:9s} k={ls['k']} route={ls['route']} hi0={d['hi'][j*H]:8.0f} plan_t3={x[j*H+3]:8.0f}")
for k in sorted(agg):
    print(k, f"sum hi {agg[k]:9.0f} plan_t3 {aggp[k]:9.0f}")
print("shared first edges:", {e: v for e, v in first_edge_k.items() if len(v) > 1})
