"""Task 14: what the TW/KR fuel pulse costs and buys, per grid, on Full.

    uv run python outputs/task-14/pulse_cost.py full 0 devpick:2,2,1,1 4

Plays agents/mpc_pulse (pulse on) and agents/mpc_pulse with {"pulse_weeks": 0} (= mpc_chip + fab_cap_mode observed,
the pulse off) exactly as outputs/cost_breakdown.py plays an agent (same worlds, seeds, fallback), and records per grid
and week: shed (units and VOLL USD), served load, fab energy, lots started at the grid's fabs, and the episode's cost
components. Writes outputs/task-14/pulse_cost_<task>_<root>_<eps>.json and prints per-grid totals (mean per episode).
"""

import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cost_breakdown import COMPONENTS, _sum_records  # noqa: E402
from variants import pick_episodes  # noqa: E402

VARIANTS = {"pulse": {}, "nopulse": {"pulse_weeks": 0.0}}
OUT = Path("outputs/task-14")


def episode(n, spec, agent_root):
    from shockbench_flow.dynamics.env import rollout, took_fallback
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _metered_shim, _policy_seed, _world
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime, reps, cache = spec
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
    shim = _metered_shim(load_agent_class(agent_root, f"submission_{Path(agent_root).name}"), None)
    traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=fallback)
    unload_agent()
    R = traj.records
    G = len(inst.grids)
    voll = np.array([inst.nodes[g].grid.voll for g in inst.grids])
    fab_grid = np.full(len(inst.fabs), -1)
    for gi, members in enumerate(inst.grid_fabs):
        fab_grid[list(members)] = gi
    shed = np.array([r.shed for r in R])  # (T, G)
    lots = np.array([r.lots_started for r in R])  # (T, F)
    energy = np.array([r.energy for r in R])
    lots_g = np.stack([lots[:, fab_grid == gi].sum(1) for gi in range(G)], 1)
    energy_g = np.stack([energy[:, fab_grid == gi].sum(1) for gi in range(G)], 1)
    return {
        "episode": n,
        "J_cents": traj.J_cents,
        "fallback_weeks": sum(took_fallback(r) for r in R),
        "costs": _sum_records(traj),
        "grids": [inst.nodes[g].id for g in inst.grids],
        "shed": shed.tolist(),
        "shed_usd": (shed * voll).tolist(),
        "served_load": np.array([r.served_load for r in R]).tolist(),
        "lots_g": lots_g.tolist(),
        "energy_g": energy_g.tolist(),
        "lots_f": lots.sum(0).tolist(),
        "fabs": [inst.nodes[f].id for f in inst.fabs],
        "lost": np.sum([r.lost for r in R], 0).tolist(),
    }


def main(task, entropy, eps_spec, n_jobs="4"):
    from shockbench_flow_agent.scoring import EpisodeSet

    entropy, n_jobs = int(entropy), int(n_jobs)
    eps = pick_episodes(task, entropy, eps_spec, n_jobs)
    es = EpisodeSet.build(task, eps, entropy=entropy, n_jobs=n_jobs)
    ns = [int(n) for n in es.episodes]
    strata = {int(r["episode"]): r["stratum"] for r in es.references}
    tag = f"{task}_{entropy}_{eps_spec.replace(':', '-').replace(',', '-')}"
    res = {}
    for name, params in VARIANTS.items():
        folder = OUT / "agents" / name
        if folder.exists():
            shutil.rmtree(folder)
        shutil.copytree("agents/mpc_pulse", folder, ignore=shutil.ignore_patterns("__pycache__", "params.json"))
        if params:
            (folder / "params.json").write_text(json.dumps(params))
        t = time.time()
        res[name] = Parallel(n_jobs=n_jobs, verbose=5)(delayed(episode)(n, es._spec, str(folder.resolve())) for n in ns)
        rss = es.rss([r["J_cents"] for r in res[name]])
        print(f"{name}: {time.time() - t:.0f} s, RSS {rss['rss']:.4f} by level {rss['rss_by_stratum']}", flush=True)
        for r in res[name]:
            r["stratum"] = strata[r["episode"]]
        (OUT / f"pulse_cost_{tag}.json").write_text(json.dumps(res))
    report(res)


def report(res):
    a, b = res["pulse"], res["nopulse"]
    grids = a[0]["grids"]
    n = len(a)
    print(f"\n{n} episodes; mean per episode; diff = pulse - nopulse")
    print("cost components (USD):")
    for c in list(COMPONENTS) + ["salvage_credit"]:
        va, vb = np.mean([r["costs"][c] for r in a]), np.mean([r["costs"][c] for r in b])
        print(f"  {c:15s} pulse {va:12.4e} nopulse {vb:12.4e} diff {va - vb:+12.4e}")
    ja, jb = np.mean([r["J_cents"] for r in a]) / 100, np.mean([r["J_cents"] for r in b]) / 100
    print(f"  {'TOTAL J':15s} pulse {ja:12.4e} nopulse {jb:12.4e} diff {ja - jb:+12.4e}")
    print(f"\n{'grid':12s} {'shedUSD p':>11s} {'shedUSD np':>11s} {'d shedUSD':>11s} {'lots p':>10s} {'lots np':>10s}"
          f" {'energy p':>10s} {'energy np':>10s} {'0-shed wk p':>11s} {'np':>5s}")
    for gi, g in enumerate(grids):
        def m(rows, key):
            return np.mean([np.sum(np.array(r[key])[:, gi]) for r in rows])

        def zero(rows):
            return np.mean([np.sum(np.array(r["shed"])[:, gi] <= 1e-9) for r in rows])
        print(f"{g:12s} {m(a, 'shed_usd'):11.3e} {m(b, 'shed_usd'):11.3e} {m(a, 'shed_usd') - m(b, 'shed_usd'):+11.3e}"
              f" {m(a, 'lots_g'):10.4g} {m(b, 'lots_g'):10.4g} {m(a, 'energy_g'):10.4g} {m(b, 'energy_g'):10.4g}"
              f" {zero(a):11.1f} {zero(b):5.1f}")


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report(json.loads(Path(sys.argv[2]).read_text()))
    else:
        main(*sys.argv[1:])
