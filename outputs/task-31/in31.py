"""Task 31: why does grid_in shed ~1000 GWh/week for months while the oracle sheds 0? Replays one Full episode
(world without the naive fallback, as probe28.py) and prints, for one grid, per week: shed, and per fuel the segment
cap (share*G-bar, rationed), burn, grid stock, plus stocks of every node feeding it.

    uv run python outputs/task-31/in31.py full 0 7 agents/mpc_imit_room grid_in
"""
import sys
from pathlib import Path

import numpy as np


def main(task, entropy, n, agent_root, grid_id, w0=1, w1=60):
    from shockbench_flow.disruption.sampler import sample_omega
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow.hosting.tasks import task_generator
    from shockbench_flow.marks import compute_marks
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _label, _metered_shim, _policy_seed
    from shockbench_flow_agent.shim import load_agent_class, unload_agent
    from shockbench_flow.hosting.tasks import get_task

    entropy, n = int(entropy), int(n)
    inst, gparams = task_generator(task)
    omega = sample_omega(inst, gparams, entropy, n, _label(entropy))
    marks = compute_marks(inst, omega)
    pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
    regime = get_task(task).regime if hasattr(get_task(task), "regime") else "standard"
    shim = _metered_shim(load_agent_class(str(Path(agent_root).resolve()), f"submission_{Path(agent_root).stem}"), None)
    traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=None)
    unload_agent()
    R = traj.records
    N, K = inst.nodes, inst.commodities
    ids = [x.id for x in N]
    g = ids.index(grid_id)
    gi = list(inst.grids).index(g)
    grid = N[g].grid
    sidx = inst.slot_index
    print("J", traj.J_cents / 1e14, "T; fuels", [K[k].id for k in grid.fuels], "shares",
          {K[k].id: grid.shares[k] for k in grid.fuels}, "rationed", K[grid.rationed].id if grid.rationed is not None else None,
          "ibar", {K[k].id: grid.ibar.get(k) for k in grid.fuels}, "psi", inst.params.psi, "base", grid.base_load)
    # edges into the grid and into its feeders
    into = [e for e in inst.edges if e.head == g]
    feeders = sorted({e.tail for e in into})
    print("feeders:", [ids[f] for f in feeders])
    for f in feeders:
        print("  into", ids[f], ":", sorted({ids[e.tail] for e in inst.edges if e.head == f}))
    for ti in range(int(w0) - 1, min(int(w1), len(R))):
        r = R[ti]
        Gb = float(marks.G_bar[ti][gi])
        parts = [f"w{ti + 1:3d} shed {float(r.shed[gi]):7.0f} Gb {Gb:6.0f}"]
        for k in grid.fuels:
            s = sidx[(g, k)]
            parts.append(f"{K[k].id[:5]} cap {grid.shares[k] * Gb:5.0f} burn {float(r.segment.get((gi, k), 0)):5.0f}"
                         f" I {float(r.stock[s]):7.0f}")
            for f in feeders:
                if (f, k) in sidx:
                    parts.append(f"{ids[f][:8]} {float(r.stock[sidx[(f, k)]]):7.0f}")
        print(" | ".join(parts))


if __name__ == "__main__":
    main(*sys.argv[1:])
