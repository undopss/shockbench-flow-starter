"""Task 19 ceiling: the clairvoyant LP with every fab's weekly starts capped at what the agent actually started.

Its chip shortage is the best any routing (and any 'start fewer') could do with the agent's production, with perfect
foresight. agent shortage - this = the most that routing / not making unsellable chips can save (no new production).

    uv run python outputs/task-19/bound19.py outputs/task-19/diag19_full_0_devpick-2-2-1-1_base.json 4
"""
import json
import sys
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed


def one(n, lots_w, energy_w, spec):
    from shockbench_flow.oracle.lp import ORACLE_METHOD, build_lp, lp_costs, solve_oracle
    from shockbench_flow_agent.scoring import _world
    task, entropy, regime, reps, cache = spec
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    lots_w = np.asarray(lots_w)
    out = {}
    energy_w = np.asarray(energy_w)
    for mode in ("free", "gridE", "capped"):
        model = build_lp(inst, marks)
        keys = model.keys
        if mode == "gridE":
            # sum of fab energy per (grid, week) <= the agent's; fabs and routing otherwise free
            from scipy.sparse import coo_matrix, vstack
            grid_of = [inst.grid_ordinal[inst.nodes[f].fab.grid] if inst.nodes[f].fab.grid is not None else None
                       for f in inst.fabs]
            rows_, cols_, b_ = [], [], []
            idx = {}
            for j, key in enumerate(keys):
                if key[0] == "E" and grid_of[key[2]] is not None:
                    r = idx.setdefault((grid_of[key[2]], key[1]), len(idx))
                    rows_.append(r); cols_.append(j)
            for (g, t), r in sorted(idx.items(), key=lambda kv: kv[1]):
                fs = [fo for fo in range(len(inst.fabs)) if grid_of[fo] == g]
                b_.append(float(sum(energy_w[t - 1, fo] for fo in fs)) * 1.0001 + 1e-6)
            extra = coo_matrix((np.ones(len(rows_)), (rows_, cols_)), shape=(len(idx), len(model.keys))).tocsr()
            object.__setattr__(model, "A_ub", vstack([model.A_ub, extra]).tocsr())
            object.__setattr__(model, "b_ub", np.concatenate([model.b_ub, np.array(b_)]))
        if mode == "capped":
            for j, key in enumerate(keys):
                if key[0] == "p":
                    model.ub[j] = min(model.ub[j], lots_w[key[1] - 1, key[2]] * 1.0001 + 1e-6)
        res = solve_oracle(model, method=ORACLE_METHOD)
        if res.x is None:
            out[mode] = None
            continue
        weekly, salvage = lp_costs(model, res.x)
        c = {k: float(sum(getattr(w, k) for w in weekly)) for k in ("shortage", "disposal", "shed", "holding")}
        lots = np.zeros(len(inst.fabs))
        for j, key in enumerate(keys):
            if key[0] == "p":
                lots[key[2]] += res.x[j]
        c["lots"] = lots.tolist()
        lost = np.zeros(len(inst.demands))
        disp = {}
        for j, key in enumerate(keys):
            if key[0] == "U":
                lost[key[2]] += res.x[j]
            elif key[0] == "O" and res.x[j] > 1:
                sl = inst.stock_slots[key[2]]
                nm = inst.nodes[sl.node].id + "/" + inst.commodities[sl.k].id
                disp[nm] = disp.get(nm, 0.0) + float(res.x[j])
        c["lost"] = lost.tolist()
        c["disp"] = disp
        c["J"] = res.J_cents / 100
        out[mode] = c
    return n, out


def main(path, n_jobs="4"):
    from shockbench_flow_agent.scoring import EpisodeSet
    rows = json.loads(Path(path).read_text())
    es = EpisodeSet.build("full", [r["episode"] for r in rows], entropy=0, n_jobs=int(n_jobs))
    res = Parallel(n_jobs=int(n_jobs), verbose=5)(delayed(one)(r["episode"], r["lots_w"], r["energy_w"], es._spec) for r in rows)
    res = dict(res)
    Path(path.replace(".json", "_bound.json")).write_text(json.dumps(res))
    print(f"{'ep':>4} {'agent short':>12} {'capped LP':>10} {'gridE LP':>10} {'free LP':>10} {'agent-capped':>13} {'agent-gridE':>12} | lots agent / capped LP / gridE LP (M)")
    gaps, gaps2 = [], []
    for r in rows:
        o = res[r["episode"]]
        a = r["cost"]["shortage"]
        cs = o["capped"]["shortage"] if o["capped"] else float("nan")
        fs = o["free"]["shortage"] if o["free"] else float("nan")
        gs = o["gridE"]["shortage"] if o["gridE"] else float("nan")
        gaps.append(a - cs); gaps2.append(a - gs)
        print(f"{r['episode']:>4} {a/1e12:12.3f} {cs/1e12:10.3f} {gs/1e12:10.3f} {fs/1e12:10.3f} {(a-cs)/1e12:13.3f} {(a-gs)/1e12:12.3f} | "
              f"{np.sum(r['lots_w'])/1e6:.1f} / {sum(o['capped']['lots'])/1e6 if o['capped'] else float('nan'):.1f}"
              f" / {sum(o['gridE']['lots'])/1e6 if o['gridE'] else float('nan'):.1f}")
    dem = rows[0]["demands"]
    print("lost sales (M units/episode, mean): agent / capped LP / gridE LP / free LP")
    L = {m: np.nanmean([res[r["episode"]][m]["lost"] for r in rows if res[r["episode"]][m]], axis=0) for m in ("capped", "gridE", "free")}
    La = np.mean([np.sum(r["lost_w"], axis=0) for r in rows], axis=0)
    for d in np.argsort(-(La - L["capped"]) * np.array([x["pi"] for x in dem])):
        print(f"  {dem[d]['node']:>9} {dem[d]['k']:<9} {La[d]/1e6:6.2f} {L['capped'][d]/1e6:6.2f} {L['gridE'][d]/1e6:6.2f} {L['free'][d]/1e6:6.2f}   agent-capped {(La[d]-L['capped'][d])*dem[d]['pi']/1e12:.3f} T")
    dd = {}
    for r in rows:
        for k, v in (res[r["episode"]]["capped"] or {}).get("disp", {}).items():
            dd[k] = dd.get(k, 0) + v / len(rows)
    print("capped LP disposal (M/episode):", {k: round(v / 1e6, 2) for k, v in sorted(dd.items(), key=lambda kv: -kv[1])[:8]})
    print(f"mean agent - gridE-LP shortage: {np.nanmean(gaps2)/1e12:.3f} T USD/episode (+ moving each grid's fab power between its fabs)")
    print(f"mean agent - capped-LP shortage: {np.nanmean(gaps)/1e12:.3f} T USD/episode (routing + start-capping ceiling)")


if __name__ == "__main__":
    main(*sys.argv[1:])
