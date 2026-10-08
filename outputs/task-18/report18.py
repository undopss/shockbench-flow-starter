"""Fab lots per fab and shed per grid on Full dev 20: agents vs the oracle (oracle from task 17's run on the same
episodes, outputs/task-17/gap17v2_full_0_dev_mpc_buffer.json).

    uv run python outputs/task-18/report18.py <agent folder> [<agent folder> ...]
"""
import json
import sys
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

VOLL = 4125277.26


def play(n, spec, root):
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _metered_shim, _policy_seed, _world
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime, reps, cache = spec
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    shim = _metered_shim(load_agent_class(root, f"sub_{Path(root).name}"), None)
    traj = rollout(inst, shim, omega, regime, _policy_seed(entropy, n, NO_ZIP_SHA256), marks=marks, fallback=fallback)
    unload_agent()
    R = traj.records
    return {"episode": n, "J": traj.J_cents, "lots": np.sum([r.lots_started for r in R], axis=0).tolist(),
            "shed": np.sum([r.shed for r in R], axis=0).tolist(),
            "cpu": list(getattr(shim, "cpu_weeks", []))}


def main(*agents):
    from shockbench_flow_agent.scoring import EpisodeSet

    es = EpisodeSet.build("full", "dev", entropy=0, n_jobs=4)
    ns = [int(n) for n in es.episodes]
    t17 = {r["episode"]: r for r in json.load(open("outputs/task-17/gap17v2_full_0_dev_mpc_buffer.json"))}
    meta = t17[ns[0]]["meta"]
    fabs = [f["id"] if isinstance(f, dict) else f for f in meta["fabs"]]
    grids = [g["id"] if isinstance(g, dict) else g for g in meta["grids"]]
    orc_lots = np.mean([t17[n]["oracle_detail"]["lots_started"] for n in ns], axis=0)
    orc_shed = np.mean([t17[n]["oracle_detail"]["shed"] for n in ns], axis=0)
    res = {}
    for a in agents:
        rows = Parallel(n_jobs=4)(delayed(play)(n, es._spec, str(Path(a).resolve())) for n in ns)
        res[a] = rows
        cpu = [c for r in rows for c in r["cpu"]]
        print(f"{a}: RSS {es.rss([r['J'] for r in rows])['rss']:.4f}; CPU s/week max {max(cpu, default=float('nan')):.3f}, median {np.median(cpu) if cpu else float('nan'):.3f}")
    names = [Path(a).name[:14] for a in agents]
    print("\n## Fab lots started per episode (mean over Full dev 20, millions)")
    print(f"{'fab':22s}" + "".join(f"{n:>15s}" for n in names) + f"{'oracle':>10s}")
    for i, f in enumerate(fabs):
        print(f"{f:22s}" + "".join(f"{np.mean([r['lots'][i] for r in res[a]]) / 1e6:15.2f}" for a in agents)
              + f"{orc_lots[i] / 1e6:10.2f}")
    print("\n## Shed per grid (T USD per episode, mean; VOLL 4.125 M)")
    print(f"{'grid':22s}" + "".join(f"{n:>15s}" for n in names) + f"{'oracle':>10s}")
    for i, g in enumerate(grids):
        print(f"{g:22s}" + "".join(f"{np.mean([r['shed'][i] for r in res[a]]) * VOLL / 1e12:15.4f}" for a in agents)
              + f"{orc_shed[i] * VOLL / 1e12:10.4f}")
    Path("outputs/task-18/report18.json").write_text(json.dumps({a: r for a, r in res.items()}))


if __name__ == "__main__":
    main(*sys.argv[1:])
