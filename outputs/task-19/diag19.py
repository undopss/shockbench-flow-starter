"""Task 19: where does the agent make chips nobody can sell? Plays an agent exactly as outputs/cost_breakdown.py does
(agent rollout only; the oracle's per-fab lots come from task 17's JSON) and records per chip stock slot: disposal by
week, stock by week, and the requested vs executed chip shipments; per fab lots started by week.

    uv run python outputs/task-19/diag19.py full 0 devpick:2,2,1,1 agents/mpc_sell 4 [tag]
"""
import json
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
    cpu = list(getattr(shim, "cpu_weeks", []))
    R = traj.records
    N, K = inst.nodes, inst.commodities
    chip = [i for i, s in enumerate(inst.stock_slots) if "chip" in K[s.k].id or "wafer" in K[s.k].id]
    slots = [[N[inst.stock_slots[i].node].id, K[inst.stock_slots[i].k].id] for i in chip]
    disp_w = np.array([[r.disposal[i] for i in chip] for r in R])
    stock_w = np.array([[r.stock[i] for i in chip] for r in R])
    # executed chip shipments by (tail node, head node, k)
    ship = {}
    for r in R:
        for (e, k, lane), q in r.x.items():
            if "chip" in K[k].id or "wafer" in K[k].id:
                ed = inst.edges[e]
                key = f"{N[ed.tail].id}|{N[ed.head].id}|{K[k].id}"
                ship[key] = ship.get(key, 0.0) + float(q)
    pk = {}
    for r in R:
        for key, v in r.packaged.items():
            pk[str(key)] = pk.get(str(key), 0.0) + float(v)
    dem = [{"node": N[d.node].id, "k": K[d.k].id, "pi": float(d.pi)} for d in inst.demands]
    return {
        "episode": n, "J_agent_cents": traj.J_cents, "fallback_weeks": sum(took_fallback(r) for r in R),
        "cpu_max": max(cpu, default=None), "cpu_median": float(np.median(cpu)) if cpu else None,
        "slots": slots, "disp_w": disp_w.tolist(), "stock_w": stock_w.tolist(),
        "fabs": [N[f].id for f in inst.fabs], "lots_w": np.array([r.lots_started for r in R]).tolist(),
        "energy_w": np.array([r.energy for r in R]).tolist(),
        "lost_w": np.array([r.lost for r in R]).tolist(), "served_w": np.array([r.served for r in R]).tolist(),
        "demands": dem, "ship": ship, "packaged": pk,
        "cost": {c: float(sum(getattr(r.costs, c) for r in R)) for c in ("shortage", "disposal", "shed", "holding")},
        "seconds": round(time.perf_counter() - t0, 1),
    }


def main(task, entropy, neps, agent, n_jobs, tag=None):
    from shockbench_flow_agent.scoring import EpisodeSet
    from variants import pick_episodes

    entropy, n_jobs = int(entropy), int(n_jobs)
    eps = pick_episodes(task, entropy, neps, n_jobs)
    es = EpisodeSet.build(task, eps, entropy=entropy, n_jobs=n_jobs)
    ns = [int(n) for n in es.episodes]
    root = str(Path(agent).resolve())
    tag = tag or Path(agent).name
    out = Path(f"outputs/task-19/diag19_{task}_{entropy}_{neps.replace(':', '-').replace(',', '-')}_{tag}.json")
    t = time.time()
    rows = Parallel(n_jobs=n_jobs, verbose=5)(delayed(episode)(n, es._spec, root) for n in ns)
    for r, ref in zip(rows, es.references):
        r["stratum"] = ref["stratum"]
    out.write_text(json.dumps(rows))
    print(f"played in {time.time() - t:.0f} s, written {out}")
    print("RSS:", es.rss([r["J_agent_cents"] for r in rows]))
    print("fallback weeks", sum(r["fallback_weeks"] for r in rows), "cpu max", max(r["cpu_max"] for r in rows),
          "median", np.median([r["cpu_median"] for r in rows]))


if __name__ == "__main__":
    main(*sys.argv[1:])
