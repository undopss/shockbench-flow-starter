"""Task 30: crude / LNG sources and lanes into the fab grids: supply lost at the source cap, what each lane carried vs
its tightest edge capacity, chokepoint queues. Plays like diag30 (no naive fallback).

    uv run python outputs/task-30/src30.py full 0 devpick:2,2,1,1 agents/mpc_imit_room 4
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def episode(n, spec, agent_root):
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _label, _metered_shim, _policy_seed
    from shockbench_flow.disruption.sampler import sample_omega
    from shockbench_flow.hosting.tasks import task_generator
    from shockbench_flow.marks import compute_marks
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime, reps, cache = spec
    inst, gparams = task_generator(task)
    omega = sample_omega(inst, gparams, entropy, n, _label(entropy))
    marks = compute_marks(inst, omega)
    pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
    shim = _metered_shim(load_agent_class(agent_root, f"submission_{Path(agent_root).stem}"), None)
    traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=None)
    unload_agent()
    R = traj.records
    N, K, E = inst.nodes, inst.commodities, inst.edges
    ids = [nd.id for nd in N]
    T = len(R)
    out = {"episode": n, "src": {}, "lanes": {}, "xkeys": [str(k) for k in list(R[5].x)[:5]], "dest": {}}
    for s, sl in enumerate(inst.stock_slots):
        if sl.node in inst.supply_nodes and K[sl.k].id in ("crude", "lng"):
            sup = np.array([float(marks.supply[t][s]) for t in range(T)])
            lift = np.array([float(R[t].lift[s]) for t in range(T)])
            st = np.array([float(R[t].stock[s]) for t in range(T)])
            out["src"][f"{ids[sl.node]}/{K[sl.k].id}"] = [float(sup.mean()), float(lift.mean()),
                                                          float((sup - lift).mean()), float(st.mean()), sl.storage]
    flow = defaultdict(float)
    for r in R:
        for key, q in r.x.items():
            e, k, lane = key
            flow[(e, k, lane)] += float(q) / T
    for li, l in enumerate(inst.lanes):
        ks = [k for k in (inst.lane_K[li] or ()) if K[k].id in ("crude", "lng")]
        for k in ks:
            e0 = l.edges[0]
            f = flow.get((e0, k, li), 0.0) + flow.get((e0, k, l.id), 0.0)
            ucap = np.mean([min(float(marks.u[t][e]) for e in l.edges) for t in range(T)])
            opn = np.mean([min([float(marks.o[t][inst.chokepoint_ordinal[c]]) for c in l.chokepoints] or [1.0])
                           for t in range(T)])
            out["lanes"][f"{l.id}/{K[k].id}"] = [f, float(ucap), float(opn)]
    # direct edges source->grid/terminal without lane
    for e, ed in enumerate(E):
        if ed.tail in inst.supply_nodes:
            for k in ed.K or ():
                if K[k].id in ("crude", "lng"):
                    f = sum(v for (ee, kk, _l), v in flow.items() if ee == e and kk == k)
                    out["dest"][f"{ed.id}/{K[k].id}"] = [f, float(np.mean([float(marks.u[t][e]) for t in range(T)]))]
    return out


def main(task, entropy, eps, agent, n_jobs):
    from shockbench_flow_agent.scoring import EpisodeSet
    from variants import pick_episodes
    entropy, n_jobs = int(entropy), int(n_jobs)
    sel = pick_episodes(task, entropy, eps, n_jobs)
    es = EpisodeSet.build(task, sel, entropy=entropy, n_jobs=n_jobs)
    rows = Parallel(n_jobs=n_jobs)(delayed(episode)(int(n), es._spec, str(Path(agent).resolve())) for n in es.episodes)
    Path(f"outputs/task-30/src_{Path(agent).name}.json").write_text(json.dumps(rows))
    ne = len(rows)
    print("x keys sample", rows[0]["xkeys"])
    print("\nsources (mean per week over episodes): supply, lifted, lost at cap, stock, storage")
    for key in sorted(rows[0]["src"]):
        v = np.mean([r["src"][key] for r in rows], axis=0)
        print(f"  {key:28s} sup {v[0]:8.0f} lift {v[1]:8.0f} lost {v[2]:8.0f} stock {v[3]:9.0f} stor {v[4]:9.0f}")
    print("\nsource edges: flow/wk vs mean u")
    for key in sorted(rows[0]["dest"]):
        v = np.mean([r["dest"][key] for r in rows], axis=0)
        print(f"  {key:50s} flow {v[0]:8.0f} u {v[1]:9.0f}")
    print("\nlanes: flow/wk on first edge, mean tightest u, mean open")
    for key in sorted(rows[0]["lanes"]):
        v = np.mean([r["lanes"][key] for r in rows], axis=0)
        print(f"  {key:50s} flow {v[0]:8.0f} u {v[1]:9.0f} open {v[2]:.2f}")


if __name__ == "__main__":
    main(*sys.argv[1:])
