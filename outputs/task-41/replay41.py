"""Task 41: replay one Full dev episode with an agent; dump weekly chip disposal/stock per slot, lost/served per sink,
lots per fab, and the oracle's weekly O (disposal), U (lost), p (lots), D (served). Pickle to outputs/task-41/rep_<ep>_<agent>.pkl
    uv run python outputs/task-41/replay41.py agents/mpc_best 14 [n_jobs eps...]
"""
import pickle, sys, time
from pathlib import Path
import numpy as np
from joblib import Parallel, delayed


def one(n, spec, agent_root, tag):
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow.oracle.lp import ORACLE_METHOD, build_lp, solve_oracle
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _metered_shim, _policy_seed, _world
    from shockbench_flow_agent.shim import load_agent_class, unload_agent
    task, entropy, regime, reps, cache = spec
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
    shim = _metered_shim(load_agent_class(agent_root, f"submission_{Path(agent_root).stem}_{n}"), None)
    traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=fallback)
    unload_agent()
    R = traj.records
    out = {"J": traj.J_cents, "attrs": [a for a in dir(R[0]) if not a.startswith("_")]}
    for f in ("disposal", "stock", "lost", "served", "lots_started", "shed", "energy", "demand"):
        out[f] = np.array([getattr(r, f) for r in R])
    out["slots"] = [(inst.nodes[s.node].id, inst.commodities[s.k].id) for s in inst.stock_slots]
    out["cap"] = [getattr(inst.nodes[s.node], "storage", None) for s in inst.stock_slots]
    out["demands"] = [(inst.nodes[d.node].id, inst.commodities[d.k].id, d.pi) for d in inst.demands]
    out["fabs"] = [inst.nodes[f].id for f in inst.fabs]
    T, S, Dn, F = len(R), len(inst.stock_slots), len(inst.demands), len(inst.fabs)
    model = build_lp(inst, marks)
    res = solve_oracle(model, method=ORACLE_METHOD)
    o = {"O": np.zeros((T, S)), "U": np.zeros((T, Dn)), "D": np.zeros((T, Dn)), "p": np.zeros((T, F)), "I": np.zeros((T, S))}
    for j, key in enumerate(model.keys):
        if key[0] in o and len(key) >= 3 and isinstance(key[1], (int, np.integer)) and 1 <= key[1] <= T:
            try:
                o[key[0]][key[1] - 1, key[2]] += res.x[j]
            except Exception:
                pass
    out["oracle"] = o
    out["oracle_keys_sample"] = sorted({k[0] for k in model.keys})
    Path(f"outputs/task-41/rep_{n}_{tag}.pkl").write_bytes(pickle.dumps(out))
    return n, traj.J_cents


if __name__ == "__main__":
    from shockbench_flow_agent.scoring import EpisodeSet
    agent, nj, eps = sys.argv[1], int(sys.argv[2]), [int(x) for x in sys.argv[3].split(",")]
    tag = sys.argv[4] if len(sys.argv) > 4 else Path(agent).name
    es = EpisodeSet.build("full", "dev", entropy=0, n_jobs=nj)
    t = time.time()
    print(Parallel(n_jobs=nj)(delayed(one)(n, es._spec, str(Path(agent).resolve()), tag) for n in eps), time.time() - t)
