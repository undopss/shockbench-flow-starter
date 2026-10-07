"""Task 11: ceiling of steering scarce leftover fab power to the most valuable fabs.

    uv run python outputs/task-11/power_steer.py full 0 devpick:2,2,1,1 agents/mpc_pulse 4

Plays the agent exactly as outputs/cost_breakdown.py does (same worlds, seeds, fallback). For every grid-week in which
the fabs were power-limited (leftover power after homes < the fabs' requested draw), it takes the leftover power the fabs
actually got (sum E_f) and re-splits it greedily to the fabs with the highest chip value per power unit, each up to its
capacity draw e_f*alpha_f*cap0_f (as if it held enough wafers). Chip value per power unit at fab f = pi(product) * R_f / e_f
(p = R*E/e wafers -> 1 raw chip each), with pi(product) = the lost-weighted mean pi over sinks of that packaged chip, and
0 if that chip had no lost sales in the episode. Extra chips per product are capped by its lost units in the episode.
A "late" variant drops weeks whose chips cannot reach a sink before the horizon (t > T - tau_fab - tau_osat - 2).
"""

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed


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
    T = len(R)
    N, C = inst.nodes, inst.commodities

    # packaged product per raw chip, pi per packaged product (lost-weighted), lost units per packaged product
    raw2pk = {}
    for o in inst.osats:
        raw2pk.update(N[o].osat.packages)
    lost = np.sum([r.lost for r in R], axis=0)
    lost_k, lostusd_k, pi_mean = defaultdict(float), defaultdict(float), {}
    for d, dem in enumerate(inst.demands):
        lost_k[dem.k] += lost[d]
        lostusd_k[dem.k] += lost[d] * dem.pi
    for k in lost_k:
        pi_mean[k] = lostusd_k[k] / lost_k[k] if lost_k[k] > 0 else 0.0
    osat_tau = max(N[o].osat.tau for o in inst.osats)

    fabs = [N[f].fab for f in inst.fabs]
    gain = defaultdict(float)  # per grid
    gain_late = defaultdict(float)
    dchips = defaultdict(float)  # per packaged product, all weeks
    dchips_e = defaultdict(float)  # per packaged product, early weeks only
    contested = defaultdict(int)
    used_val = defaultdict(float)
    for r in R:
        t, ti = r.week, r.week - 1
        alpha, Rt = marks.alpha_bar[ti], marks.R[ti]
        for gi, g in enumerate(inst.grids):
            mem = list(inst.grid_fabs[gi])
            if len(mem) < 2:
                continue
            ehat = []
            for fi in mem:
                fab = fabs[fi]
                ehat.append(fab.e * alpha[fi] * fab.cap0)  # capacity draw (upper bound of e*phat/R)
            E = np.array([r.energy[fi] for fi in mem])
            L = E.sum()
            # power-limited: some fab got less energy than its wafers allowed, i.e. started fewer lots than
            # min(cap, wafers): detected as E_f < e*phat/R. Equivalent check: fab started p < R*E/e is impossible,
            # so use: any fab with E_f*R/e > p + tol never happens; instead check that energy, not wafers, bound p.
            # power-limited grid-week: base_first gives every fab the same factor min(1, leftover/sum ehat), so the grid
            # was power-limited iff some fab started fewer lots than p-hat = min(alpha R cap0, wafers on hand after
            # arrivals) = min(cap, end stock + p + disposal) (nothing else draws a fab's wafer slot after step 6)
            limited = False
            for fi in mem:
                s_in = inst.slot_index[(inst.fabs[fi], fabs[fi].input)]
                p = r.lots_started[fi]
                phat = min(alpha[fi] * Rt[fi] * fabs[fi].cap0, r.stock[s_in] + p + r.disposal[s_in])
                if phat > 1e-6 and p < phat * (1 - 1e-7):
                    limited = True
            if not limited or L <= 0:
                continue
            contested[N[g].id] += 1
            pk = [raw2pk[fabs[fi].product] for fi in mem]
            v = np.array([pi_mean.get(pk[j], 0.0) * Rt[fi] / fabs[fi].e for j, fi in enumerate(mem)])
            cur = float(v @ E)
            # greedy best split of the same L
            Ebest = np.zeros(len(mem))
            rem = L
            for j in np.argsort(-v):
                q = min(rem, ehat[j])
                Ebest[j] = q
                rem -= q
            best = float(v @ Ebest)
            used_val[N[g].id] += cur
            late = t > T - max(fabs[fi].tau for fi in mem) - osat_tau - 2
            gain[N[g].id] += best - cur
            for j, fi in enumerate(mem):
                dc = (Ebest[j] - E[j]) * Rt[fi] / fabs[fi].e
                dchips[pk[j]] += dc
                if not late:
                    dchips_e[pk[j]] += dc
            if not late:
                gain_late[N[g].id] += best - cur
    # value of the product shift, capped by lost units: positive shifts worth pi up to lost units, negative cost pi
    def capped(dc):
        tot = 0.0
        for k, x in dc.items():
            tot += pi_mean.get(k, 0.0) * (min(x, lost_k[k]) if x > 0 else x)
        return tot
    return {
        "episode": n,
        "J_agent_cents": traj.J_cents,
        "fallback_weeks": sum(took_fallback(r) for r in R),
        "lost_usd": {C[k].id: lostusd_k[k] for k in lost_k},
        "lost_units": {C[k].id: lost_k[k] for k in lost_k},
        "pi_mean": {C[k].id: pi_mean[k] for k in pi_mean},
        "contested_weeks": dict(contested),
        "value_made_contested": dict(used_val),
        "gain_by_grid": dict(gain),
        "gain_by_grid_early": dict(gain_late),
        "dchips": {C[k].id: v for k, v in dchips.items()},
        "dchips_early": {C[k].id: v for k, v in dchips_e.items()},
        "ceiling_uncapped": sum(gain.values()),
        "ceiling_capped": capped(dchips),
        "ceiling_capped_early": capped(dchips_e),
        "seconds": round(time.perf_counter() - t0, 1),
    }


def main(task, entropy, neps, agent, n_jobs):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from variants import pick_episodes  # noqa
    from shockbench_flow_agent.scoring import EpisodeSet

    entropy, n_jobs = int(entropy), int(n_jobs)
    eps = pick_episodes(task, entropy, neps, n_jobs)
    es = EpisodeSet.build(task, eps, entropy=entropy, n_jobs=n_jobs)
    root = str(Path(agent).resolve())
    rows = Parallel(n_jobs=n_jobs, verbose=5)(delayed(episode)(int(n), es._spec, root) for n in es.episodes)
    strata = {r["episode"]: r["stratum"] for r in es.references}
    for r in rows:
        r["stratum"] = strata[r["episode"]]
    out = Path(f"outputs/task-11/power_steer_{task}_{entropy}_{neps.replace(':', '-')}_{Path(agent).name}.json")
    out.write_text(json.dumps(rows, indent=1))
    print("written", out, "RSS check:", es.rss([r["J_agent_cents"] for r in rows]))
    print(f"{'ep':>5s} {'lvl':>3s} {'lost USD':>10s} {'uncapped':>10s} {'capped':>10s} {'capped,early':>12s}  gain by grid (T USD)")
    for r in rows:
        g = {k: round(v / 1e12, 4) for k, v in r["gain_by_grid"].items() if abs(v) > 1e9}
        print(f"{r['episode']:5d} {r['stratum']:3d} {sum(r['lost_usd'].values()) / 1e12:10.3f} {r['ceiling_uncapped'] / 1e12:10.4f} "
              f"{r['ceiling_capped'] / 1e12:10.4f} {r['ceiling_capped_early'] / 1e12:12.4f}  {g}")
    w = {1: .5, 2: .3, 3: .15, 4: .05}
    for key in ("ceiling_uncapped", "ceiling_capped", "ceiling_capped_early"):
        lv = {s: np.mean([r[key] for r in rows if r["stratum"] == s]) for s in sorted({r["stratum"] for r in rows})}
        wm = sum(w[s] * v for s, v in lv.items()) / sum(w[s] for s in lv)
        print(f"{key:22s} plain mean {np.mean([r[key] for r in rows]) / 1e12:.4f} T, harm-weighted {wm / 1e12:.4f} T, per level "
              + ", ".join(f"L{s} {v / 1e12:.4f}" for s, v in lv.items()))


if __name__ == "__main__":
    main(*sys.argv[1:])
