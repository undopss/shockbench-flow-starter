"""Task 13: play an agent on Full episodes exactly as outputs/cost_breakdown.py does and dump the chip-side records.

    uv run python outputs/task-13/play.py full 0 devpick:2,2,1,1 agents/mpc_pulse 4

Writes outputs/task-13/raw_<task>_<root>_<spec>_<agent>.pkl: per episode the per-week demand/served/lost (D), stock and
disposal (S), lots_started (F), packaged, and the sink-bound in-transit chips (from x and edge lead times).
"""

import pickle
import sys
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def episode(n, spec, agent_root):
    from shockbench_flow.dynamics.env import rollout, took_fallback
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _metered_shim, _policy_seed, _world
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime, reps, cache = spec
    t0 = time.perf_counter()
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
    shim = _metered_shim(load_agent_class(agent_root, f"submission_{Path(agent_root).stem}"), None)
    traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=fallback)
    unload_agent()
    R = traj.records
    chip_k = {k for k, c in enumerate(inst.commodities) if inst.commodities[k].pool == "ct"}
    xs = [{key: v for key, v in r.x.items() if key[1] in chip_k and v > 0} for r in R]
    return {
        "episode": n,
        "J_agent_cents": traj.J_cents,
        "fallback_weeks": sum(took_fallback(r) for r in R),
        "salvage": float(traj.salvage or 0.0),
        "demand": np.array([r.demand for r in R]),
        "served": np.array([r.served for r in R]),
        "lost": np.array([r.lost for r in R]),
        "stock": np.array([r.stock for r in R]),
        "disposal": np.array([r.disposal for r in R]),
        "lots_started": np.array([r.lots_started for r in R]),
        "energy": np.array([r.energy for r in R]),
        "packaged": [dict(r.packaged) for r in R],
        "x": xs,
        "shortage_cost": np.array([r.costs.shortage for r in R]),
        "seconds": round(time.perf_counter() - t0, 1),
    }


def main(task, entropy, spec, agent, n_jobs):
    from shockbench_flow_agent.scoring import EpisodeSet
    from variants import pick_episodes

    entropy, n_jobs = int(entropy), int(n_jobs)
    eps = pick_episodes(task, entropy, spec, n_jobs)
    es = EpisodeSet.build(task, eps, entropy=entropy, n_jobs=n_jobs)
    root = str(Path(agent).resolve())
    rows = Parallel(n_jobs=n_jobs, verbose=10)(delayed(episode)(int(n), es._spec, root) for n in es.episodes)
    for r, ref in zip(rows, es.references):
        r["stratum"] = ref["stratum"]
        r["J_oracle_cents"] = ref["J_oracle_cents"]
        r["J_naive_cents"] = ref["J_naive_cents"]
    out = Path(__file__).parent / f"raw_{task}_{entropy}_{spec.replace(':', '-').replace(',', '')}_{Path(agent).name}.pkl"
    out.write_bytes(pickle.dumps(rows))
    print("written", out, "RSS", es.rss([r["J_agent_cents"] for r in rows]))


if __name__ == "__main__":
    main(*sys.argv[1:])
