"""Can the routes physically bring more fuel to the grids that power chip fabs? python outputs/fuel_limits.py full 0 dev agents/mpc_pulse 3

Per episode and per fab grid / fuel, summed over the episode:
  need    = sum_t zeta_k G-bar^t (the fuel segment at full load: homes + fabs)
  maxflow = the most fuel output the network can deliver to ALL fab grids together (oracle LP rows = physics,
            edge caps, straits, supply, rationing line; objective = maximise fab grids' fuel output G)
  oracle  = G in the clairvoyant cost-optimal plan
  agent   = G the agent actually got
plus fab energy E (agent / oracle / maxflow plan) and shed per grid. Writes outputs/fuel_limits_<task>_<root>_<eps>.json.
"""

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed


def episode(n, spec, agent_root):
    from scipy.optimize import linprog
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow.oracle.lp import ORACLE_METHOD, build_lp, solve_oracle
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _metered_shim, _policy_seed, _world
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime, reps, cache = spec
    t0 = time.perf_counter()
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    gname = [inst.nodes[g].id for g in inst.grids]
    fab_grid = {}
    for fo, f in enumerate(inst.fabs):
        g = inst.nodes[f].fab.grid
        if g is not None:
            fab_grid[fo] = inst.grids.index(g)
    fgrids = sorted(set(fab_grid.values()))

    shim = _metered_shim(load_agent_class(agent_root, f"submission_{Path(agent_root).stem}"), None)
    traj = rollout(inst, shim, omega, regime, _policy_seed(entropy, n, NO_ZIP_SHA256), marks=marks, fallback=fallback)
    unload_agent()
    agentG, agentE, agentShed = defaultdict(float), defaultdict(float), defaultdict(float)
    for r in traj.records:
        for (go, k), v in r.segment.items():
            agentG[(go, k)] += float(v)
        for fo, go in fab_grid.items():
            agentE[go] += float(r.energy[fo])
        for go in range(len(gname)):
            agentShed[go] += float(r.shed[go])

    gotT = defaultdict(float)
    for t, r in enumerate(traj.records):
        for (go, k), v in r.segment.items():
            gotT[(t, go)] += float(v)
    model = build_lp(inst, marks)
    keys = model.keys
    need, Gcols, needT = defaultdict(float), [], defaultdict(float)
    for j, key in enumerate(keys):
        if key[0] == "G" and key[2] in fgrids:
            need[(key[2], key[3])] += float(model.ub[j])
            needT[(key[1], key[2])] += float(model.ub[j])
            if key[3] is not None:
                Gcols.append(j)

    def sums(x):
        G, E, sh = defaultdict(float), defaultdict(float), defaultdict(float)
        for j, key in enumerate(keys):
            if key[0] == "G":
                G[(key[2], key[3])] += x[j]
            elif key[0] == "E" and key[2] in fab_grid:
                E[fab_grid[key[2]]] += x[j]
            elif key[0] == "ysh":
                sh[key[2]] += x[j]
        return G, E, sh

    res = solve_oracle(model, method=ORACLE_METHOD)
    oG, oE, oSh = sums(res.x) if res.x is not None else ({}, {}, {})

    c = np.zeros(len(keys))
    c[Gcols] = -1.0
    mf = linprog(c, A_ub=model.A_ub, b_ub=model.b_ub, A_eq=model.A_eq, b_eq=model.b_eq,
                 bounds=np.column_stack([model.lb, model.ub]), method="highs")
    mG, mE, mSh = sums(mf.x) if mf.x is not None else ({}, {}, {})
    mG_T = defaultdict(float)
    if mf.x is not None:
        for j, key in enumerate(keys):
            if key[0] == "G":
                mG_T[(key[1], key[2])] += mf.x[j]

    rows = []
    for (go, k) in sorted(need, key=lambda t: (t[0], str(t[1]))):
        rows.append({"grid": gname[go], "fuel": None if k is None else str(inst.commodities[k].id if hasattr(inst, "commodities") else k),
                     "k": k, "need": need[(go, k)], "maxflow": mG.get((go, k)), "oracle": oG.get((go, k)),
                     "agent": agentG.get((go, k), 0.0)})
    grids = [{"grid": gname[go], "fabE_agent": agentE[go], "fabE_oracle": oE.get(go), "fabE_maxflow": mE.get(go),
              "shed_agent": agentShed[go],
              "full_weeks_agent": sum(gotT[(t, g2)] >= 0.9999 * v for (t, g2), v in needT.items() if g2 == go),
              "full_weeks_maxflow": sum(mG_T[(t, g2)] >= 0.9999 * v for (t, g2), v in needT.items() if g2 == go), "shed_oracle": oSh.get(go)} for go in fgrids]
    return {"episode": n, "rows": rows, "grids": grids, "maxflow_status": mf.status, "oracle_ok": res.x is not None,
            "seconds": round(time.perf_counter() - t0, 1)}


def main(task, entropy, eps, agent, n_jobs):
    from shockbench_flow_agent.scoring import EpisodeSet
    es = EpisodeSet.build(task, eps if eps == "dev" else int(eps), entropy=int(entropy), n_jobs=int(n_jobs))
    ns = [int(n) for n in es.episodes]
    out = Parallel(n_jobs=int(n_jobs), verbose=10)(delayed(episode)(n, es._spec, agent) for n in ns)
    Path(f"outputs/fuel_limits_{task}_{entropy}_{eps}.json").write_text(json.dumps(out, default=str))
    tot = defaultdict(lambda: np.zeros(4))
    for e in out:
        for r in e["rows"]:
            tot[(r["grid"], r["fuel"])] += [r["need"], r["maxflow"] or 0, r["oracle"] or 0, r["agent"]]
    print(f"{'grid':16} {'fuel':10} {'need':>12} {'maxflow':>12} {'oracle':>12} {'agent':>12}  max/need agent/max")
    for (g, f), v in sorted(tot.items(), key=lambda t: str(t[0])):
        v = v / len(out)
        print(f"{g:16} {str(f):10} {v[0]:12.4g} {v[1]:12.4g} {v[2]:12.4g} {v[3]:12.4g}  {v[1]/max(v[0],1e-9):7.2f} {v[3]/max(v[1],1e-9):7.2f}")
    gt = defaultdict(lambda: np.zeros(7))
    for e in out:
        for r in e["grids"]:
            gt[r["grid"]] += [r["fabE_agent"], r["fabE_oracle"] or 0, r["fabE_maxflow"] or 0, r["shed_agent"],
                              r["shed_oracle"] or 0, r["full_weeks_agent"], r["full_weeks_maxflow"]]
    print(f"
{'grid':16} {'fabE_agent':>11} {'fabE_oracle':>11} {'fabE_maxfl':>11} {'shed_agent':>11} {'shed_oracle':>11} fullwk_agent fullwk_maxflow")
    for g, v in sorted(gt.items()):
        v = v / len(out)
        print(f"{g:16} {v[0]:11.4g} {v[1]:11.4g} {v[2]:11.4g} {v[3]:11.4g} {v[4]:11.4g} {v[5]:12.1f} {v[6]:12.1f}")


if __name__ == "__main__":
    main(*sys.argv[1:])
