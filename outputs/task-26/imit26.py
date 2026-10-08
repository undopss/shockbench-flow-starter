"""Task 26: record the clairvoyant plan's and an agent's weekly decisions on training episodes, in one format.

    python outputs/task-26/imit26.py oracle full 2626 0-39 4
    python outputs/task-26/imit26.py agent  full 2626 0-39 4 agents/mpc_fab3sell

Writes outputs/task-26/data/<task>_<entropy>_<who>_<ep>.npz with (T, ...) arrays: stock (end-of-week I per stock slot),
lots, energy (per fab), seg (per grid segment key), shed, served_load, lost, served, demand, x (T, E, K summed over
lanes), and the marks an agent can (roughly) see: G_bar, y_bar, fabcap (alpha_bar R cap0). Plus <task>_static.pkl.
"""
import pickle
import sys
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

OUT = Path("outputs/task-26/data")


def _world_light(task, ent, n):
    from shockbench_flow.disruption.sampler import sample_omega
    from shockbench_flow.hosting.tasks import split_label, task_generator
    from shockbench_flow.marks import compute_marks
    inst, params = task_generator(task)
    omega = sample_omega(inst, params, ent, n, split_label(ent))
    return inst, omega, compute_marks(inst, omega)


def seg_keys(inst):
    keys = []
    for go, g in enumerate(inst.grids):
        ga = inst.nodes[g].grid
        for k in ga.fuels + ((None,) if None in ga.shares else ()):
            keys.append((go, k))
    return keys


def static(task):
    from shockbench_flow.hosting.tasks import task_generator
    inst, params = task_generator(task)
    st = {
        "slots": [(s.node, s.k, s.storage) for s in inst.stock_slots],
        "nodes": [(n.id, n.type) for n in inst.nodes],
        "commodities": [k.id for k in inst.commodities],
        "pi": [getattr(k, "v", None) for k in inst.commodities],
        "grids": list(inst.grids), "fabs": list(inst.fabs), "osats": list(inst.osats),
        "grid_attrs": [inst.nodes[g].grid for g in inst.grids],
        "fab_attrs": [inst.nodes[f].fab for f in inst.fabs],
        "edges": [(e.id, e.tail, e.head) for e in inst.edges],
        "demands": [(d.node, d.k, d.pi, d.backlog) for d in inst.demands],
        "psi": inst.params.psi, "seg_keys": seg_keys(inst),
    }
    return st


def marks_part(inst, marks):
    cap0 = np.array([inst.nodes[f].fab.cap0 for f in inst.fabs])
    return {"G_bar": np.asarray(marks.G_bar), "y_bar": np.asarray(marks.y_bar),
            "fabcap": np.asarray(marks.alpha_bar) * np.asarray(marks.R) * cap0, "demand": np.asarray(marks.demand),
            "G_bar_now": np.asarray(marks.G_bar_now), "u": np.asarray(marks.u)}


def oracle_ep(task, ent, n):
    from shockbench_flow.oracle.lp import ORACLE_METHOD, build_lp, solve_oracle
    f = OUT / f"{task}_{ent}_oracle_{n}.npz"
    if f.exists():
        return n, "cached"
    t0 = time.time()
    inst, omega, marks = _world_light(task, ent, n)
    model = build_lp(inst, marks)
    res = solve_oracle(model, method=ORACLE_METHOD)
    if res.x is None:
        return n, "fail"
    T, cols = model.T, model.columns
    Z = np.asarray(res.x).reshape(T, len(cols))
    ci = {c: i for i, c in enumerate(cols)}
    S, F, G, D, E, K = (len(inst.stock_slots), len(inst.fabs), len(inst.grids), len(inst.demands), len(inst.edges),
                        len(inst.commodities))
    stock = np.full((T, S), np.nan)
    disp = np.zeros((T, S))
    for s in range(S):
        if ("I", s) in ci:
            stock[:, s] = Z[:, ci[("I", s)]]
        if ("O", s) in ci:
            disp[:, s] = Z[:, ci[("O", s)]]
    lots = np.stack([Z[:, ci[("p", fo)]] for fo in range(F)], 1)
    energy = np.stack([Z[:, ci[("E", fo)]] if ("E", fo) in ci else np.zeros(T) for fo in range(F)], 1)
    sk = seg_keys(inst)
    seg = np.stack([Z[:, ci[("G", go, k)]] for go, k in sk], 1)
    shed = np.stack([Z[:, ci[("ysh", go)]] for go in range(G)], 1)
    yl = np.stack([Z[:, ci[("y", go)]] for go in range(G)], 1)
    served = np.stack([Z[:, ci[("D", do)]] for do in range(D)], 1)
    lost = np.stack([Z[:, ci[("U", do)]] if ("U", do) in ci else np.zeros(T) for do in range(D)], 1)
    x = np.zeros((T, E, K))
    for c, i in ci.items():
        if c[0] == "x":
            x[:, c[1], c[2]] += Z[:, i]
    np.savez_compressed(f, stock=stock, disposal=disp, lots=lots, energy=energy, seg=seg, shed=shed, served_load=yl,
                        served=served, lost=lost, x=x.astype(np.float32), J=res.J_cents, **marks_part(inst, marks))
    return n, round(time.time() - t0, 1)


def agent_ep(task, ent, n, agent_root):
    from shockbench_flow.dynamics.env import rollout, took_fallback
    from shockbench_flow.evaluation.cache import default_cache_dir
    from shockbench_flow.policies.naive_fq import REPLICATIONS
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _metered_shim, _policy_seed, _world
    from shockbench_flow_agent.shim import load_agent_class, unload_agent
    tag = Path(agent_root).name
    f = OUT / f"{task}_{ent}_{tag}_{n}.npz"
    if f.exists():
        return n, "cached"
    t0 = time.time()
    inst, omega, marks, fallback = _world(task, ent, n, REPLICATIONS, str(default_cache_dir()))
    pseed = _policy_seed(ent, n, NO_ZIP_SHA256)
    shim = _metered_shim(load_agent_class(agent_root, f"submission_{tag}"), None)
    traj = rollout(inst, shim, omega, "standard", pseed, marks=marks, fallback=fallback)
    unload_agent()
    cpu = list(getattr(shim, "cpu_weeks", []))
    R = traj.records
    T, E, K = len(R), len(inst.edges), len(inst.commodities)
    sk = seg_keys(inst)
    x = np.zeros((T, E, K), dtype=np.float32)
    for t, r in enumerate(R):
        for (e, k, _l), q in r.x.items():
            x[t, e, k] += q
    seg = np.array([[r.segment.get(key, 0.0) for key in sk] for r in R])
    np.savez_compressed(
        f, stock=np.array([r.stock for r in R]), disposal=np.array([r.disposal for r in R]),
        lots=np.array([r.lots_started for r in R]), energy=np.array([r.energy for r in R]), seg=seg,
        shed=np.array([r.shed for r in R]), served_load=np.array([r.served_load for r in R]),
        served=np.array([r.served for r in R]), lost=np.array([r.lost for r in R]), x=x, J=traj.J_cents,
        fallback_weeks=sum(took_fallback(r) for r in R), cpu=np.array(cpu), **marks_part(inst, marks))
    return n, round(time.time() - t0, 1)


def eps(spec):
    out = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b) + 1)) if b else [int(a)]
    return out


if __name__ == "__main__":
    who, task, ent, spec, nj = sys.argv[1:6]
    ent, nj = int(ent), int(nj)
    OUT.mkdir(parents=True, exist_ok=True)
    sf = OUT / f"{task}_static.pkl"
    if not sf.exists():
        sf.write_bytes(pickle.dumps(static(task)))
    ns = eps(spec)
    if who == "oracle":
        res = Parallel(n_jobs=nj, verbose=5)(delayed(oracle_ep)(task, ent, n) for n in ns)
    else:
        root = str(Path(sys.argv[6]).resolve())
        res = Parallel(n_jobs=nj, verbose=5)(delayed(agent_ep)(task, ent, n, root) for n in ns)
    print(res)
