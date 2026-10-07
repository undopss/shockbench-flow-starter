"""Task 12: wasted power and wasted fuel at fab grids, for an agent on Full.

    uv run python outputs/task-12/waste.py full 0 devpick:2,2,1,1 agents/mpc_pulse 4

Plays the agent as outputs/cost_breakdown.py does and logs every allocate_energy call (g_av, y-bar, E-hat, y, E per grid
and week). Then, per episode, in USD:
  (a) power left over at a fab grid while its fabs were wafer-limited (homes and every fab's request served, fabs below
      capacity for lack of wafers): min(leftover, extra draw at capacity), valued at the best wafer-limited fabs.
      a_null = the part of that leftover from the non-fuel segment (cannot be stored); the fuel part stays in stock.
  (b) fuel disposed of (above storage) at grid slots and at terminals feeding them: what it could have bought if
      added in the weeks with the most valuable unmet need (shed at VOLL, unmet fab draw at chip value), limited by
      that fuel's segment headroom (share*G-bar*ration - available) in each week and by weeks >= the disposal week.
  (c) weeks a fab grid was 0-1% short of homes+fabs: the fab draw left unmet those weeks, valued at chip value
      (and the fuel that would have covered it). Also 1-5% and >5% bins for context.
Chip value of one power unit at fab f = pi(packaged product, demand-weighted over sinks that lost sales this episode) *
R_f / e_f; only lots started before T - (tau + 4) count; each product's total is capped by its lost-sales USD.
"""

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed


def episode(n, spec, agent_root):
    import shockbench_flow.dynamics.sim as sim
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _metered_shim, _policy_seed, _world
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime, reps, cache = spec
    t0 = time.perf_counter()
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    log = []
    orig = sim.allocate_energy

    def logged(priority, g_av, y_bar, e_hat):
        y, E = orig(priority, g_av, y_bar, e_hat)
        log.append((g_av, y_bar, list(e_hat), y, list(E)))
        return y, E

    sim.allocate_energy = logged
    try:
        shim = _metered_shim(load_agent_class(agent_root, f"submission_{Path(agent_root).stem}"), None)
        traj = rollout(inst, shim, omega, regime, _policy_seed(entropy, n, NO_ZIP_SHA256), marks=marks,
                       fallback=fallback)
        unload_agent()
    finally:
        sim.allocate_energy = orig
    R_ = traj.records
    T, G = len(R_), len(inst.grids)
    assert len(log) == T * G, (len(log), T, G)
    psi = inst.params.psi
    slot = {(sl.node, sl.k): s for s, sl in enumerate(inst.stock_slots)}
    fabs = [inst.nodes[f].fab for f in inst.fabs]
    init_stock = {(nd, k): q for nd, k, q in inst.initial_state.stock}

    # chip value per packaged product: lost-sales-weighted pi; caps = lost USD
    lost = np.sum([r.lost for r in R_], axis=0)
    lostusd, lostu, piw = defaultdict(float), defaultdict(float), defaultdict(float)
    for di, d in enumerate(inst.demands):
        if lost[di] > 0:
            lostusd[d.k] += lost[di] * d.pi
            lostu[d.k] += lost[di]
    for k in lostu:
        piw[k] = lostusd[k] / lostu[k]
    pkg = {}
    for o in inst.osats:
        pkg.update(inst.nodes[o].osat.packages)
    fab_pk = [pkg.get(f.product, f.product) for f in fabs]

    def vpe(fi, t):  # USD of chips per power unit at fab fi started in week t
        f = fabs[fi]
        if t > T - (f.tau + 4) or f.e <= 0:
            return 0.0
        R = float(marks.R[t][fi])
        return piw.get(fab_pk[fi], 0.0) * R / f.e

    fab_grids = [gi for gi in range(G) if inst.grid_fabs[gi]]
    gname = {gi: inst.nodes[inst.grids[gi]].id for gi in range(G)}

    out = {"episode": n, "lost_usd": float(sum(lostusd.values())),
           "shed_usd": float(sum(r.costs.shed for r in R_)), "shortage_usd": float(sum(r.costs.shortage for r in R_))}
    per_prod = {key: defaultdict(float) for key in ("a", "a_null", "b", "c1", "c5", "cbig", "unmet")}
    grid_rows = {}
    b_shed = 0.0
    # (b): disposed fuel per grid and fuel, by week
    fuel_ks = {k for gi in range(G) for k in inst.nodes[inst.grids[gi]].grid.fuels}
    disp = defaultdict(lambda: np.zeros(T))  # (gi, k) -> week array
    disp_where = defaultdict(float)
    for t, r in enumerate(R_):
        for s in np.nonzero(r.disposal)[0]:
            sl = inst.stock_slots[s]
            if sl.k not in fuel_ks:
                continue
            node = inst.nodes[sl.node]
            disp_where[(node.id, inst.commodities[sl.k].id)] += float(r.disposal[s])
            if node.grid is not None:
                targets = [inst.grids.index(sl.node)]
            else:
                targets = sorted({inst.grids.index(inst.edges[e].head) for e in inst.out_edges[sl.node]
                                  if inst.edges[e].head in inst.grids})
                if not targets:  # one more hop (terminal -> terminal/port -> grid)
                    nxt = {inst.edges[e].head for e in inst.out_edges[sl.node]}
                    targets = sorted({inst.grids.index(inst.edges[e].head) for m in nxt for e in inst.out_edges[m]
                                      if inst.edges[e].head in inst.grids})
            for gi in targets:
                disp[(gi, sl.k)][t] += float(r.disposal[s]) / len(targets)

    for gi in range(G):
        grid = inst.nodes[inst.grids[gi]].grid
        members = inst.grid_fabs[gi]
        gr = defaultdict(float)
        needs = []  # (t, k-headroom dict, list of (value per unit, units))
        for t, r in enumerate(R_):
            g_av, y_bar, e_hat, y, E = log[t * G + gi]
            full = y_bar + sum(e_hat)
            unmet_f = [(fi, eh - ef) for fi, eh, ef in zip(members, e_hat, E)]
            gr["shed"] += y_bar - y
            gr["E"] += sum(E)
            gr["Ehat"] += sum(e_hat)
            for fi, u in unmet_f:
                per_prod["unmet"][fab_pk[fi]] += u * vpe(fi, t)
            if not members:
                continue
            # (a)
            left = g_av - y - sum(E)
            if left > 1e-9 and y >= y_bar - 1e-9:
                capd = []
                for fi, eh in zip(members, e_hat):
                    f = fabs[fi]
                    R = float(marks.R[t][fi])
                    cap = float(marks.alpha_bar[t][fi]) * R * f.cap0
                    if R > 0:
                        capd.append((vpe(fi, t), fi, max(0.0, f.e * cap / R - eh)))
                null_frac = grid.shares.get(None, 0.0) * float(marks.G_bar[t][gi]) / g_av if g_av > 0 else 0.0
                rem = left
                for v, fi, room in sorted(capd, reverse=True):
                    use = min(rem, room)
                    rem -= use
                    per_prod["a"][fab_pk[fi]] += use * v
                    per_prod["a_null"][fab_pk[fi]] += use * v * null_frac
                    gr["a_units"] += use
                    gr["a_null_units"] += use * null_frac
            # (c)
            D = full - g_av
            if D > 1e-9 and full > 0:
                frac = D / full
                key = "c1" if frac <= 0.01 else ("c5" if frac <= 0.05 else "cbig")
                gr[f"{key}_weeks"] += 1
                gr[f"{key}_fuel"] += D
                for fi, u in unmet_f:
                    per_prod[key][fab_pk[fi]] += u * vpe(fi, t)
            # (b) needs: headroom per fuel this week
            load = (sum(E) + y) / g_av if g_av > 0 else 0.0
            head = {}
            for k in grid.fuels:
                s = slot[(inst.grids[gi], k)]
                Iprev = R_[t - 1].stock[s] if t > 0 else init_stock.get((inst.grids[gi], k), 0.0)
                ration = 1.0
                if k == grid.rationed:
                    th = psi * grid.ibar[k]
                    ration = 1.0 if (th <= 0 or Iprev >= th) else Iprev / th
                capk = grid.shares[k] * float(marks.G_bar[t][gi]) * ration
                avk = r.segment[(gi, k)] / load if load > 0 else 0.0
                head[k] = max(0.0, capk - avk)
            uses = [(float(grid.voll), y_bar - y, None)] + [(vpe(fi, t), u, fi) for fi, u in unmet_f]
            needs.append((t, head, uses))
        # (b) allocate disposed fuel of each kind greedily to its most valuable needs at weeks >= disposal week
        for k in grid.fuels:
            arr = disp.get((gi, k))
            if arr is None or arr.sum() <= 0:
                continue
            gr[f"disp_{k}"] += float(arr.sum())
            opts = []  # (value, week, units, fi)
            for t, head, uses in needs:
                room = head.get(k, 0.0)
                for v, u, fi in sorted(uses, key=lambda x: -x[0]):
                    take = min(room, u)
                    if take > 0 and v > 0:
                        opts.append((v, t, take, fi))
                    room -= take
            # earliest-disposal-first, each unit to the best option at or after its week
            pool = sorted([(t, q) for t, q in enumerate(arr) if q > 0])
            avail = sorted(opts, key=lambda o: -o[0])
            left = [o[2] for o in avail]
            for t0_, q in pool:
                for i, (v, t, units, fi) in enumerate(avail):
                    if q <= 0:
                        break
                    if t < t0_ or left[i] <= 0:
                        continue
                    use = min(q, left[i])
                    left[i] -= use
                    q -= use
                    if fi is None:
                        b_shed += use * v
                    else:
                        per_prod["b"][fab_pk[fi]] += use * v
                    gr[f"b_used_{k}"] += use
        if members:
            grid_rows[gname[gi]] = dict(gr)
    for key, d in per_prod.items():
        out[key + "_raw"] = float(sum(d.values()))
        out[key] = float(sum(min(v, lostusd.get(k, 0.0)) for k, v in d.items()))
    out["b_shed"] = b_shed
    out["grids"] = grid_rows
    out["disp_where"] = {f"{a}|{b}": v for (a, b), v in disp_where.items()}
    out["seconds"] = round(time.perf_counter() - t0, 1)
    return out


def main(task, entropy, neps, agent, n_jobs):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from shockbench_flow_agent.scoring import EpisodeSet
    from variants import pick_episodes

    entropy, n_jobs = int(entropy), int(n_jobs)
    eps = pick_episodes(task, entropy, neps, n_jobs)
    es = EpisodeSet.build(task, eps, entropy=entropy, n_jobs=n_jobs)
    root = str(Path(agent).resolve())
    rows = Parallel(n_jobs=n_jobs, verbose=5)(delayed(episode)(int(n), es._spec, root) for n in es.episodes)
    for r, ref in zip(rows, es.references):
        r["stratum"] = ref["stratum"]
        r["J_agent_minus_oracle_usd"] = None
    out = Path(f"outputs/task-12/waste_{task}_{entropy}_{neps.replace(':', '-').replace(',', '_')}_{Path(agent).name}.json")
    out.write_text(json.dumps(rows, indent=1))
    print(f"written {out}")
    keys = ["lost_usd", "shortage_usd", "shed_usd", "unmet", "a", "a_null", "b", "b_shed", "c1", "c5", "cbig"]
    print("USD per episode (capped by each product's lost-sales USD; _raw uncapped in the JSON)")
    print(f"{'ep':>4} {'lvl':>3} " + " ".join(f"{k:>10}" for k in keys))
    for r in rows:
        print(f"{r['episode']:>4} {r['stratum']:>3} " + " ".join(f"{r[k]:10.3e}" for k in keys))
    print(f"{'mean':>8} " + " ".join(f"{np.mean([r[k] for r in rows]):10.3e}" for k in keys))
    print("\nper fab grid, mean per episode")
    agg = defaultdict(lambda: defaultdict(float))
    for r in rows:
        for g, d in r["grids"].items():
            for k, v in d.items():
                agg[g][k] += v / len(rows)
    for g, d in sorted(agg.items()):
        print(g, " ".join(f"{k}={v:.4g}" for k, v in sorted(d.items())))
    dw = defaultdict(float)
    for r in rows:
        for k, v in r["disp_where"].items():
            dw[k] += v / len(rows)
    print("\nfuel disposal by node|fuel, mean units per episode:", {k: round(v, 1) for k, v in sorted(dw.items())})


if __name__ == "__main__":
    main(*sys.argv[1:])
