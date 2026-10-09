"""Ep N week W: the chip LP's view of one sink (demand row, planned served, fixed arrivals) vs what happened."""
import sys
from pathlib import Path
import numpy as np
from shockbench_flow.dynamics.env import rollout
from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
from shockbench_flow_agent.scoring import EpisodeSet, _metered_shim, _policy_seed, _world
from shockbench_flow_agent.shim import load_agent_class

ep, sink, kname = int(sys.argv[1]), sys.argv[2], sys.argv[3]
es = EpisodeSet.build("full", [ep], entropy=0, n_jobs=1)
task, entropy, regime, reps, cache = es._spec
inst, omega, marks, fb = _world(task, entropy, ep, reps, cache)
cls = load_agent_class(str(Path("agents/mpc_nodisp").resolve()), "submission_x")
mod = sys.modules[cls.__module__]
CP = mod._chips.ChipPlanner
plans, P = {}, []
orig = CP.plan
def plan(self, obs):
    out = orig(self, obs)
    plans[int(obs["week"][0])] = dict(self.last)
    if not P: P.append(self)
    return out
CP.plan = plan
traj = rollout(inst, _metered_shim(cls, None), omega, regime, _policy_seed(entropy, ep, NO_ZIP_SHA256), marks=marks, fallback=fb)
N, K = inst.nodes, inst.commodities
pl = P[0]
node = next(i for i, n in enumerate(N) if n.id == sink); k = next(i for i, c in enumerate(K) if c.id == kname)
p = pl.pos_index[(node, k)]
j = next(j for j, s in enumerate(pl.sinks) if s["pos"] == p)
dj = next(i for i, d in enumerate(inst.demands) if d.node == node and d.k == k)
print("storage", pl.pos[p]["cap"], "hold", pl.pos[p]["hold"])
for w in sorted(plans)[:30]:
    L = plans[w]; H = L["H"]
    sv = L["x"][L["off_s"] + j * H: L["off_s"] + j * H + 8]
    r = traj.records[w - 1]
    inflow = [ (ls["slot"], round(L["x"][jj * H] / 1e3, 1)) for jj, ls in enumerate(pl.lp_slots) if ls["dst"] == p and L["x"][jj * H] > 1]
    print(w, "dem LP", np.round(L["dem"][j, :8] / 1e3).tolist(), "served LP", np.round(sv / 1e3).tolist(), "fixed", np.round(L["fixed"][p, :8] / 1e3).tolist(),
          "| real dem", round(r.demand[dj] / 1e3), "served", round(r.served[dj] / 1e3), "lost", round(r.lost[dj] / 1e3), "ship t0", inflow)
L = plans[6]
print("u97 obs", L["u"][97], "eload97", np.round(L["eload"].get(97, np.zeros(1))[:8] / 1e3, 1), "u330", L["u"][330], "eload330", np.round(L["eload"].get(330, np.zeros(1))[:8] / 1e3, 1))
jj = next(jj for jj, ls in enumerate(pl.lp_slots) if ls["slot"] == 334)
print("hi slot334", L["hi"][jj * L["H"]: jj * L["H"] + 4], "lead", L["lead"][jj])
others = [(ls["slot"], [N[inst.edges[e].tail].id + ">" + N[inst.edges[e].head].id for e in ls["route"]], round(L["x"][j2 * L["H"]] / 1e3, 1)) for j2, ls in enumerate(pl.lp_slots) if 97 in ls["route"]]
print("LP slots using edge 97:", others)
