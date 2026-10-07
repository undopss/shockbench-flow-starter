"""How much of the clairvoyant plan is reachable when the homes-first rule is enforced? python outputs/reachable_bound.py full 0 devpick:2,2,1,1 all 900 3

The oracle LP relaxes base_first (fabs may get power while homes are shed). Here a binary z[t, g] per grid-week is
added for base_first grids that power fabs: E_f,t <= M_t z (fabs get power only in a z-week) and y_t >= y-bar_t z
(in a z-week homes are fully served). Everything else stays the oracle's relaxation, so the MILP's DUAL bound is an
upper bound on what any real agent can reach (still optimistic: perfect foresight, other relaxations kept).

grids: "all" (every such grid at once) or a comma list of grid ids (e.g. grid_jp) — the others stay relaxed.
Per episode: J naive / agent (cached refs or a mpc_pulse rollout is NOT done here; agent J from cost_breakdown json if
present) / oracle LP / MILP primal and dual bound, all in USD. Writes outputs/reachable_<task>_<root>_<eps>_<grids>.json.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed


def episode(n, spec, grids_arg, time_limit):
    from scipy.optimize import Bounds, LinearConstraint, linprog, milp
    from scipy.sparse import coo_matrix, csr_matrix, hstack, vstack
    from shockbench_flow.oracle.lp import build_lp
    from shockbench_flow_agent.scoring import _world

    task, entropy, regime, reps, cache = spec
    t0 = time.perf_counter()
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    model = build_lp(inst, marks)
    keys = model.keys
    gid = [inst.nodes[g].id for g in inst.grids]
    fab_grid = {}
    for fo, f in enumerate(inst.fabs):
        g = inst.nodes[f].fab.grid
        if g is not None:
            fab_grid[fo] = inst.grids.index(g)
    targets = sorted({go for go in fab_grid.values() if inst.nodes[inst.grids[go]].grid.priority == "base_first"})
    if grids_arg != "all":
        want = set(grids_arg.split(","))
        targets = [go for go in targets if gid[go] in want]

    c = model.objective()
    n0 = len(c)
    jE, jy, Gub = {}, {}, {}
    for j, key in enumerate(keys):
        if key[0] == "E" and key[2] in fab_grid:
            jE.setdefault((key[1], fab_grid[key[2]]), []).append(j)
        elif key[0] == "y":
            jy[(key[1], key[2])] = j
        elif key[0] == "G":
            Gub[(key[1], key[2])] = Gub.get((key[1], key[2]), 0.0) + float(model.ub[j])
    ybar = marks.y_bar  # (T, G)
    zcols = [(t, go) for t in range(model.T) for go in targets]
    zi = {tg: n0 + i for i, tg in enumerate(zcols)}
    rows, cols, vals, rhs = [], [], [], []
    r = 0
    for (t, go), z in zi.items():
        M = Gub.get((t, go), 0.0)
        for j in jE.get((t, go), []):  # E - M z <= 0
            rows += [r, r]; cols += [j, z]; vals += [1.0, -M]; rhs.append(0.0); r += 1
        if (t, go) in jy:  # ybar z - y <= 0
            rows += [r, r]; cols += [z, jy[(t, go)]]; vals += [float(ybar[t, go]), -1.0]; rhs.append(0.0); r += 1
    N = n0 + len(zcols)
    A_add = csr_matrix(coo_matrix((vals, (rows, cols)), shape=(r, N)))
    pad = lambda A: hstack([A, csr_matrix((A.shape[0], len(zcols)))]).tocsr()
    A_ub = vstack([pad(model.A_ub), A_add]).tocsr()
    A_eq = pad(model.A_eq)
    cc = np.concatenate([c, np.zeros(len(zcols))])
    lb = np.concatenate([model.lb, np.zeros(len(zcols))])
    ub = np.concatenate([model.ub, np.ones(len(zcols))])
    integ = np.concatenate([np.zeros(n0), np.ones(len(zcols))])

    lp = linprog(c, A_ub=model.A_ub, b_ub=model.b_ub, A_eq=model.A_eq, b_eq=model.b_eq,
                 bounds=np.column_stack([model.lb, model.ub]), method="highs")
    t1 = time.perf_counter()
    res = milp(cc, integrality=integ, bounds=Bounds(lb, ub),
               constraints=[LinearConstraint(A_ub, -np.inf, np.concatenate([model.b_ub, rhs])),
                            LinearConstraint(A_eq, model.b_eq, model.b_eq)],
               options={"time_limit": float(time_limit), "disp": False})
    dual = getattr(res, "mip_dual_bound", None)

    def fabE(x):
        if x is None:
            return None
        return {gid[go]: float(sum(x[j] for (t, g2), js in jE.items() if g2 == go for j in js)) for go in targets}
    return {"episode": n, "grids": [gid[go] for go in targets], "n_binaries": len(zcols),
            "lp_obj": float(lp.fun) if lp.status == 0 else None,
            "milp_obj": float(res.fun) if res.x is not None else None, "milp_dual_bound": None if dual is None else float(dual),
            "milp_status": int(res.status), "milp_message": str(res.message), "milp_gap": getattr(res, "mip_gap", None),
            "lp_seconds": round(t1 - t0, 1), "milp_seconds": round(time.perf_counter() - t1, 1),
            "fabE_lp": fabE(lp.x if lp.status == 0 else None), "fabE_milp": fabE(res.x)}


def main(task, entropy, eps, grids="all", time_limit=900, n_jobs=3):
    from shockbench_flow_agent.scoring import EpisodeSet
    sel = eps if eps == "dev" else ([int(x) for x in eps.split(",")] if "," in eps else int(eps))
    es = EpisodeSet.build(task, sel,
                          entropy=int(entropy), n_jobs=int(n_jobs))
    ns = [int(n) for n in es.episodes]
    glist = [grids] if grids == "all" else grids.split(",")  # each grid solved on its own (the others stay relaxed)
    out = Parallel(n_jobs=int(n_jobs), verbose=10)(delayed(episode)(n, es._spec, g, time_limit) for g in glist for n in ns)
    Path(f"outputs/reachable_{task}_{entropy}_{str(eps).replace(',', '-')}_{grids.replace(',', '-')}.json").write_text(
        json.dumps(out, default=str))
    for o in out:
        lp, mo, db = o["lp_obj"], o["milp_obj"], o["milp_dual_bound"]
        print(o["episode"], o["grids"], "fabE lp", o["fabE_lp"], "milp", o["fabE_milp"], "LP", lp, "MILP", mo, "dual", db,
              "dual-LP (USD, >= reachable loss vs oracle)", None if (lp is None or db is None) else db - lp,
              o["milp_message"], o["milp_seconds"], "s")


if __name__ == "__main__":
    main(*sys.argv[1:])
