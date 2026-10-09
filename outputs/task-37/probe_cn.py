"""Ep 0 (Full dev): why does osat_cn dispose chip_mat while sink_sea loses mature sales? Per week: requested / executed
on osat_cn's chip_mat slots, edge use, sink_sea chip_mat demand / lost, chk_taiwan open/queue."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shockbench_flow.dynamics.env import rollout
from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
from shockbench_flow_agent.scoring import EpisodeSet, _metered_shim, _policy_seed, _world
from shockbench_flow_agent.shim import load_agent_class

ep = int(sys.argv[1]) if len(sys.argv) > 1 else 0
es = EpisodeSet.build("full", [ep], entropy=0, n_jobs=1)
task, entropy, regime, reps, cache = es._spec
inst, omega, marks, fb = _world(task, entropy, ep, reps, cache)
cls = load_agent_class(str(Path("agents/mpc_nodisp").resolve()), "submission_x")
traj = rollout(inst, _metered_shim(cls, None), omega, regime, _policy_seed(entropy, ep, NO_ZIP_SHA256), marks=marks, fallback=fb)
N, K, E = inst.nodes, inst.commodities, inst.edges
nid = {n.id: i for i, n in enumerate(N)}
kid = {c.id: i for i, c in enumerate(K)}
oc, km = nid["osat_cn"], kid["chip_mat"]
oute = [e for e, ed in enumerate(E) if ed.tail == oc and km in ed.K]
print("out-edges", [(e, N[E[e].head].id, round(float(marks.u[0, e]))) for e in oute])
dj = [j for j, d in enumerate(inst.demands) if d.k == km]
u = np.asarray(marks.u)
for t, r in enumerate(traj.records[:50]):
    fl = {}
    for (e, k, l), v in r.x.items():
        if e in oute and k == km:
            fl[(N[E[e].head].id, l)] = round(v / 1e3)
    s = inst.stock_slots.index(next(sl for sl in inst.stock_slots if sl.node == oc and sl.k == km)) if False else None
    lost = {N[inst.demands[j].node].id: round(r.lost[j] / 1e3) for j in dj if r.lost[j] > 1}
    use = {N[E[e].head].id: f"{sum(v for (ee,k,l),v in r.x.items() if ee==e)/1e3:.0f}/{u[t,e]/1e3:.0f}" for e in oute}
    print(t + 1, "flows", fl, "use", use, "lost_k", lost)
Z = np.asarray(marks.prohibited)
print("prohibited osat_cn->sink_us chip_mat weeks:", int(Z[:, 331, km].sum()), "of", Z.shape[0])
e97 = next(e for e, ed in enumerate(E) if N[ed.tail].id == "chk_taiwan" and N[ed.head].id == "sink_sea")
print("chk_taiwan->sink_sea use", [f"{sum(v for (ee,k,l),v in r.x.items() if ee==e97)/1e3:.0f}/{u[t,e97]/1e3:.0f}" for t, r in enumerate(traj.records[:45])])
cfg_slots = [(s, e, k, l) for s, (e, k, l) in enumerate(inst.action_slots)] if hasattr(inst, "action_slots") else None
print(type(inst.action_slots[0]) if hasattr(inst, "action_slots") else dir(inst)[:80])
print(inst.action_slots[0])
sl = [s for s, a in enumerate(inst.action_slots) if a[1] == km and a[2] in (53, 54, 55, 56)]
print("slots", [(s, inst.action_slots[s]) for s in sl])
for t, r in enumerate(traj.records[:12]):
    print(t + 1, {s: (round(r.requested.get(s, 0) / 1e3, 1), round(r.executed.get(s, 0) / 1e3, 1)) for s in sl})
for li in (53, 54, 55, 56):
    l = inst.lanes[li]
    print(li, l.id, [(e, N[E[e].tail].id, N[E[e].head].id, round(float(u[5, e])), [K[k].id for k in E[e].K], E[e].mode) for e in l.edges])
for e, ed in enumerate(E):
    if N[ed.tail].id == "chk_taiwan" and N[ed.head].id == "sink_sea":
        print("edge", e, round(float(u[5, e])), [K[k].id for k in ed.K], ed.mode, "flow wk6", sum(v for (ee,k,l2),v in traj.records[5].x.items() if ee==e))
ci = list(inst.chokepoints).index(nid["chk_taiwan"])
print("o_now chk_taiwan wk1-40", np.round(np.asarray(marks.o_now)[:40, ci], 2).tolist())
print("kappa_now ct chk_taiwan", np.round(np.asarray(marks.kappa_now)[:40:4, ci, :] / 1e3).tolist())
print("queue at chk_taiwan (k)", [round(sum(v for (c, k, l), v in r.queue.items() if c == nid["chk_taiwan"]) / 1e3) for r in traj.records[:40]])
print("released total out of chk_taiwan per wk", [round(sum(v for (e, k, l), v in r.x.items() if E[e].tail == nid["chk_taiwan"]) / 1e3) for r in traj.records[:40]])
