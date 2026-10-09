"""Task 30: what the clairvoyant oracle LP does at the fab grids, fuel by fuel (Full devpick).

Solves shockbench_flow.oracle.lp on each episode and records per grid and week: each fuel segment's output G vs
share * G-bar, fuel arriving at the grid and its terminals (x into them), grid and terminal stocks, fab energy, home
shed; per crude/LNG source: lift vs supply.

    uv run python outputs/task-30/oracle30.py full 0 devpick:2,2,1,1 4
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
GRIDS = ("grid_jp", "grid_sea", "grid_cn", "grid_eu", "grid_kr", "grid_tw")


def episode(n, spec):
    from scipy.optimize import linprog
    from shockbench_flow.oracle.lp import build_lp
    from shockbench_flow.disruption.sampler import sample_omega
    from shockbench_flow.hosting.tasks import task_generator
    from shockbench_flow.marks import compute_marks
    from shockbench_flow_agent.scoring import _label

    task, entropy, regime, reps, cache = spec
    t0 = time.time()
    inst, gparams = task_generator(task)
    omega = sample_omega(inst, gparams, entropy, n, _label(entropy))
    marks = compute_marks(inst, omega)
    model = build_lp(inst, marks)
    lp = linprog(model.objective(), A_ub=model.A_ub, b_ub=model.b_ub, A_eq=model.A_eq, b_eq=model.b_eq,
                 bounds=np.column_stack([model.lb, model.ub]), method="highs")
    x = lp.x
    N, K, E = inst.nodes, inst.commodities, inst.edges
    ids = [nd.id for nd in N]
    T = model.T
    out = {"episode": n, "obj": float(lp.fun), "sec": round(time.time() - t0), "grids": {}, "src": {}}
    gord = {g: i for i, g in enumerate(inst.grids)}
    agg = defaultdict(lambda: np.zeros(T))
    t_min = min(k[1] for k in model.keys)
    for j, key in enumerate(model.keys):
        v = float(x[j])
        if v == 0.0:
            continue
        tag, t = key[0], key[1] - t_min
        if tag == "G":
            agg[("G", key[2], key[3])][t] += v
        elif tag == "E":
            f = inst.fabs[key[2]]
            g = N[f].fab.grid
            agg[("E", gord[g])][t] += v
        elif tag == "ysh":
            agg[("ysh", key[2])][t] += v
        elif tag == "I":
            sl = inst.stock_slots[key[2]]
            agg[("I", sl.node, sl.k)][t] += v
        elif tag == "O":
            sl = inst.stock_slots[key[2]]
            agg[("O", sl.node, sl.k)][t] += v
        elif tag == "lift":
            sl = inst.stock_slots[key[2]]
            agg[("lift", sl.node, sl.k)][t] += v
        elif tag == "x":
            e, k = key[2], key[3]
            agg[("xin", E[e].head, k)][t] += v
    for gi, g in enumerate(inst.grids):
        if ids[g] not in GRIDS:
            continue
        grid = N[g].grid
        terms = sorted({E[e].tail for e in range(len(E)) if E[e].head == g
                        and getattr(N[E[e].tail], "type", "") == "terminal"})
        fu = {}
        for k, sh in grid.shares.items():
            if k is None:
                continue
            capw = sh * np.asarray(marks.G_bar)[:, gi]
            fu[K[k].id] = {"cap": capw.tolist(), "G": agg[("G", gi, k)].tolist(),
                           "Igrid": agg[("I", g, k)].tolist(),
                           "Iterm": sum((agg[("I", tm, k)] for tm in terms), np.zeros(T)).tolist(),
                           "in_term": sum((agg[("xin", tm, k)] for tm in terms), np.zeros(T)).tolist(),
                           "in_grid_direct": agg[("xin", g, k)].tolist()}
        out["grids"][ids[g]] = {"fuels": fu, "fabE": agg[("E", gi)].tolist(), "ysh": agg[("ysh", gi)].tolist()}
    for s, sl in enumerate(inst.stock_slots):
        if sl.node in inst.supply_nodes and K[sl.k].id in ("crude", "lng"):
            sup = np.asarray(marks.supply)[:, s]
            out["src"][f"{ids[sl.node]}/{K[sl.k].id}"] = [float(sup.mean()), float(agg[("lift", sl.node, sl.k)].mean())]
    return out


def main(task, entropy, eps, n_jobs):
    from shockbench_flow_agent.scoring import EpisodeSet
    from variants import pick_episodes
    sel = pick_episodes(task, int(entropy), eps, int(n_jobs))
    es = EpisodeSet.build(task, sel, entropy=int(entropy), n_jobs=int(n_jobs))
    rows = Parallel(n_jobs=int(n_jobs))(delayed(episode)(int(n), es._spec) for n in es.episodes)
    Path(f"outputs/task-30/oracle_{task}_{entropy}.json").write_text(json.dumps(rows))
    print("solved", [(r["episode"], r["sec"]) for r in rows])


if __name__ == "__main__":
    main(*sys.argv[1:])
