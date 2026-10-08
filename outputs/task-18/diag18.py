"""Why do CN/JP/SEA fabs get no power? Plays an agent on Full episodes exactly as outputs/cost_breakdown.py does and
reconstructs, per fab grid and week, each fuel segment's limit (rationing vs fuel on hand), the home shortfall and the
fab draw.

    uv run python outputs/task-18/diag18.py full 0 devpick:2,2,1,1 agents/mpc_fab3 4 [grids]
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def episode(n, spec, agent_root, grids):
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _metered_shim, _policy_seed, _world
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime, reps, cache = spec
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
    shim = _metered_shim(load_agent_class(agent_root, f"submission_{Path(agent_root).stem}"), None)
    traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=fallback)
    unload_agent()
    R = traj.records
    psi = inst.params.psi
    si = inst.slot_index
    ids = [nd.id for nd in inst.nodes]
    out = {"episode": n, "J": traj.J_cents, "grids": {}}
    for gi, g in enumerate(inst.grids):
        if grids and ids[g] not in grids:
            continue
        grid = inst.nodes[g].grid
        members = inst.grid_fabs[gi]
        rows = []
        for t, r in enumerate(R):
            G = float(marks.G_bar[t][gi])
            yb = float(marks.y_bar[t][gi])
            fuels = {}
            for k in grid.fuels:
                s = si[(g, k)]
                Iprev = float(R[t - 1].stock[s]) if t > 0 else np.nan
                burn = float(r.segment.get((gi, k), 0.0))
                pre = float(r.stock[s]) + burn + float(r.disposal[s])
                cap = grid.shares[k] * G
                ration = 1.0
                if k == grid.rationed and t > 0:
                    thr = psi * grid.ibar[k]
                    ration = 1.0 if Iprev >= thr else Iprev / thr
                av = min(cap * ration, pre)
                fuels[inst.commodities[k].id if hasattr(inst.commodities[k], "id") else str(k)] = {
                    "cap": cap, "ration": ration, "pre": pre, "av": av, "short": cap - av,
                    "lim": "full" if cap - av < 1e-6 * cap else ("ration" if cap * ration <= pre else "onhand"),
                }
            g_av = sum(f["av"] for f in fuels.values()) + grid.shares.get(None, 0.0) * G
            E = float(sum(r.energy[fi] for fi in members))
            rows.append({"t": t, "G": G, "ybar": yb, "gav": g_av, "shed": float(r.shed[gi]), "E": E,
                         "lots": float(sum(r.lots_started[fi] for fi in members)), "fuels": fuels})
        out["grids"][ids[g]] = rows
    return out


def main(task, entropy, eps, agent, n_jobs, grids="grid_cn,grid_jp,grid_sea"):
    from shockbench_flow_agent.scoring import EpisodeSet

    sys.path.insert(0, "outputs")
    from variants import pick_episodes

    entropy, n_jobs = int(entropy), int(n_jobs)
    sel = pick_episodes(task, entropy, eps, n_jobs)
    es = EpisodeSet.build(task, sel, entropy=entropy, n_jobs=n_jobs)
    ns = [int(n) for n in es.episodes]
    root = str(Path(agent).resolve())
    t0 = time.time()
    rows = Parallel(n_jobs=n_jobs)(delayed(episode)(n, es._spec, root, grids.split(",")) for n in ns)
    print(f"played {len(ns)} in {time.time() - t0:.0f} s; RSS {es.rss([r['J'] for r in rows])}")
    out = Path(f"outputs/task-18/diag_{task}_{entropy}_{eps.replace(':', '-').replace(',', '_')}_{Path(agent).name}.json")
    out.write_text(json.dumps(rows))
    print("written", out)
    for r in rows:
        for gid, wk in r["grids"].items():
            sh = np.array([w["shed"] for w in wk]); yb = np.array([w["ybar"] for w in wk])
            E = np.array([w["E"] for w in wk])
            lims = {}
            for w in wk:
                for fk, f in w["fuels"].items():
                    if f["lim"] != "full":
                        lims[(fk, f["lim"])] = lims.get((fk, f["lim"]), 0) + 1
            shortshare = {fk: np.median([w["fuels"][fk]["short"] / max(w["ybar"], 1) for w in wk if w["shed"] > 0] or [0])
                          for fk in wk[0]["fuels"]}
            print(f"ep {r['episode']:4d} {gid:9s} shed weeks {int((sh > 1e-6).sum()):3d}/{len(wk)}  "
                  f"median shed/ybar {np.median(sh[sh > 1e-6] / yb[sh > 1e-6]) if (sh > 1e-6).any() else 0:.4f}  "
                  f"E {E.sum():9.0f}  lim-weeks {dict(sorted(lims.items()))}  "
                  f"med short/ybar per fuel {{{', '.join(f'{k}: {v:.4f}' for k, v in shortshare.items())}}}")


if __name__ == "__main__":
    main(*sys.argv[1:])
