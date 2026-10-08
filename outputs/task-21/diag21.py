"""Task 21: mpc_fab3sell's chip decisions vs the clairvoyant LP's, and offline tests of what the chip LP lacks.

    uv run python outputs/task-21/diag21.py play  <tag> <opts.json|-> [n_jobs]   # play outputs/task-21/ag on Full devpick
    uv run python outputs/task-21/diag21.py bound <tag> [n_jobs]                 # oracle LPs on that play's trajectory

play: plays the hooked copy of agents/mpc_fab3sell (outputs/task-21/ag, its params.json = the agent's) exactly as
outputs/cost_breakdown.py does, with chips.ORACLE filled with the episode's true marks and chips.OPTS from the JSON
(true_demand, true_caps, true_fabcap: the agent's realized lots from the 'base' play, chip_H via params). Records per
week: lots, energy and wafer stock per fab, the energy the grid had left for its fabs after homes (G_av - y), lost and
served per demand, chip flows by stage, chip disposal, and the chip LP's own plan (chips.LOG).

bound: the package's oracle LP on the same episodes: free, and with per-(grid, week) fab energy capped at what the
agent's grid had left for fabs after homes ('avail'), and with per-(fab, week) starts capped at the agent's ('capped').
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

HERE = Path(__file__).resolve().parent
EPS = "devpick:2,2,1,1"
sys.path.insert(0, str(HERE.parent))


def stage_of(inst, e):
    N = inst.nodes
    ed = inst.edges[e]
    a, b = N[ed.tail], N[ed.head]
    ta, tb = getattr(a, "type", None), getattr(b, "type", None)
    return f"{ta}>{tb}", a.id, b.id


def play(n, spec, agent_root, opts, base_lots):
    from shockbench_flow.dynamics import sim as sim_mod
    from shockbench_flow.dynamics.env import rollout, took_fallback
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _metered_shim, _policy_seed, _world
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime, reps, cache = spec
    t0 = time.perf_counter()
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
    cls = load_agent_class(agent_root, f"submission_{Path(agent_root).stem}")
    mod = sys.modules.get(cls.__module__)
    chips = mod._chips
    chips.ORACLE = {"demand": np.asarray(marks.demand), "u": np.asarray(marks.u), "o": np.asarray(marks.o),
                    "prohibited": np.asarray(marks.prohibited),
                    "lots": np.asarray(base_lots) if base_lots is not None else None}
    chips.OPTS = dict(opts)
    chips.LOG.clear()
    # record G_av per grid call (grids in order each week)
    gav = []
    orig = sim_mod.allocate_energy

    def rec(priority, g_av, y_bar, e_hat):
        y, E = orig(priority, g_av, y_bar, e_hat)
        gav.append((g_av, y_bar, sum(e_hat), y, sum(E)))
        return y, E

    sim_mod.allocate_energy = rec
    shim = _metered_shim(cls, None)
    try:
        traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=fallback)
    finally:
        sim_mod.allocate_energy = orig
    log = list(chips.LOG)
    unload_agent()
    cpu = list(getattr(shim, "cpu_weeks", []))
    R = traj.records
    T, G = len(R), len(inst.grids)
    gav = np.array(gav).reshape(T, G, 5) if len(gav) == T * G else None
    N, K = inst.nodes, inst.commodities
    sidx = {(s.node, s.k): i for i, s in enumerate(inst.stock_slots)}
    wslots = [sidx.get((f, N[f].fab.input)) for f in inst.fabs]
    chip_slots = [i for i, s in enumerate(inst.stock_slots) if getattr(N[s.node], "type", None) in ("material", "fab", "osat", "sink")
                  and ("chip" in K[s.k].id or "wafer" in K[s.k].id)]
    flows = {}  # stage|tail|head|k -> weekly
    for t, r in enumerate(R):
        for (e, k, lane), q in r.x.items():
            if "chip" in K[k].id or "wafer" in K[k].id:
                st, a, b = stage_of(inst, e)
                flows.setdefault(f"{st}|{a}|{b}|{K[k].id}", [0.0] * T)[t] += float(q)
    from cost_breakdown import COMPONENTS
    cost = {c: float(sum(getattr(r.costs, c) for r in R)) for c in COMPONENTS if c != "salvage_credit"}
    return {
        "episode": n, "J_agent_cents": traj.J_cents, "fallback_weeks": sum(took_fallback(r) for r in R),
        "cpu_max": max(cpu, default=None), "cpu_median": float(np.median(cpu)) if cpu else None, "cost": cost,
        "fabs": [N[f].id for f in inst.fabs], "grid_of_fab": [inst.grid_ordinal[N[f].fab.grid] if N[f].fab.grid is not None else None for f in inst.fabs],
        "fab_e": [float(N[f].fab.e) for f in inst.fabs], "fab_cap0": [float(N[f].fab.cap0) for f in inst.fabs],
        "grids": [N[g].id for g in inst.grids],
        "demands": [{"node": N[d.node].id, "k": K[d.k].id, "pi": float(d.pi)} for d in inst.demands],
        "lots_w": np.array([r.lots_started for r in R]).tolist(), "energy_w": np.array([r.energy for r in R]).tolist(),
        "wafer_w": [[float(r.stock[s]) if s is not None else 0.0 for s in wslots] for r in R],
        "lost_w": np.array([r.lost for r in R]).tolist(), "served_w": np.array([r.served for r in R]).tolist(),
        "demand_w": np.array([r.demand for r in R]).tolist(),
        "shed_w": np.array([r.shed for r in R]).tolist(),
        "gav_w": gav.tolist() if gav is not None else None,
        "chip_slots": [[N[inst.stock_slots[i].node].id, K[inst.stock_slots[i].k].id] for i in chip_slots],
        "chip_stock_w": [[float(r.stock[i]) for i in chip_slots] for r in R],
        "chip_disp_w": [[float(r.disposal[i]) for i in chip_slots] for r in R],
        "flows": flows, "log": log, "R_w": np.asarray(marks.R).tolist(),
        "seconds": round(time.perf_counter() - t0, 1),
    }


def bound(n, spec, run):
    from scipy.sparse import coo_matrix, vstack
    from shockbench_flow.oracle.lp import ORACLE_METHOD, build_lp, lp_costs, solve_oracle
    from shockbench_flow_agent.scoring import _world
    task, entropy, regime, reps, cache = spec
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    N, K = inst.nodes, inst.commodities
    lots_w = np.asarray(run["lots_w"])
    gav = np.asarray(run["gav_w"])  # (T, G, 5): g_av, y_bar, e_hat, y, sumE
    grid_of = run["grid_of_fab"]
    out = {}
    for mode in ("free", "avail", "capped"):
        t0 = time.perf_counter()
        model = build_lp(inst, marks)
        keys = model.keys
        if mode == "avail":
            rows_, cols_, b_, idx = [], [], [], {}
            for j, key in enumerate(keys):
                if key[0] == "E" and grid_of[key[2]] is not None:
                    r = idx.setdefault((grid_of[key[2]], key[1]), len(idx))
                    rows_.append(r); cols_.append(j)
            for (g, t), r in sorted(idx.items(), key=lambda kv: kv[1]):
                g_av, y_bar = gav[t - 1, g, 0], gav[t - 1, g, 1]
                b_.append(max(g_av - min(y_bar, g_av), 0.0) * 1.0001 + 1e-6)
            extra = coo_matrix((np.ones(len(rows_)), (rows_, cols_)), shape=(len(idx), len(keys))).tocsr()
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
        x = res.x
        weekly, salvage = lp_costs(model, x)
        T = len(weekly)
        c = {k: float(sum(getattr(w, k) for w in weekly)) for k in ("shortage", "disposal", "shed", "holding", "freight", "tariff")}
        F, D = len(inst.fabs), len(inst.demands)
        lots = np.zeros((T, F)); en = np.zeros((T, F)); lost = np.zeros((T, D)); served = np.zeros((T, D))
        flows = {}
        sidx = {(s.node, s.k): i for i, s in enumerate(inst.stock_slots)}
        wslot = {sidx.get((f, N[f].fab.input)): fi for fi, f in enumerate(inst.fabs)}
        wafer = np.zeros((T, F))
        for j, key in enumerate(keys):
            tag, v = key[0], float(x[j])
            if tag == "p":
                lots[key[1] - 1, key[2]] += v
            elif tag == "E":
                en[key[1] - 1, key[2]] += v
            elif tag == "U":
                lost[key[1] - 1, key[2]] += v
            elif tag == "D":
                served[key[1] - 1, key[2]] += v
            elif tag == "I" and key[2] in wslot:
                wafer[key[1] - 1, wslot[key[2]]] = v
            elif tag == "x" and abs(v) > 1e-9:
                e, k = key[2], key[3]
                if "chip" in K[k].id or "wafer" in K[k].id:
                    st, a, b = stage_of(inst, e)
                    flows.setdefault(f"{st}|{a}|{b}|{K[k].id}", [0.0] * T)[key[1] - 1] += v
        out[mode] = {"cost": c, "J": res.J_cents / 100, "lots_w": lots.tolist(), "energy_w": en.tolist(),
                     "lost_w": lost.tolist(), "served_w": served.tolist(), "wafer_w": wafer.tolist(), "flows": flows,
                     "seconds": round(time.perf_counter() - t0, 1)}
    return n, out


def main(cmd, tag, *rest):
    from shockbench_flow_agent.scoring import EpisodeSet
    from variants import pick_episodes
    if cmd == "play":
        opts_file, n_jobs = rest[0], int(rest[1]) if len(rest) > 1 else 4
        opts = json.loads(Path(opts_file).read_text()) if opts_file != "-" else {}
    else:
        n_jobs = int(rest[0]) if rest else 4
    eps = pick_episodes("full", 0, EPS, n_jobs)
    es = EpisodeSet.build("full", eps, entropy=0, n_jobs=n_jobs)
    ns = [int(n) for n in es.episodes]
    if cmd == "play":
        agent = opts.pop("agent", str(HERE / "ag"))
        params = opts.pop("params", None)
        root = HERE / "agents" / tag
        import shutil
        if root.exists():
            shutil.rmtree(root)
        shutil.copytree(agent, root, ignore=shutil.ignore_patterns("__pycache__"))
        if params:
            p = json.loads((root / "params.json").read_text()) if (root / "params.json").is_file() else {}
            p.update(params)
            (root / "params.json").write_text(json.dumps(p))
        base = {}
        if opts.get("true_fabcap"):
            for r in json.loads((HERE / f"play_{opts.pop('fabcap_from', 'nolim')}.json").read_text()):
                base[r["episode"]] = r["lots_w"]
        t = time.time()
        rows = Parallel(n_jobs=n_jobs, verbose=5)(delayed(play)(n, es._spec, str(root), opts, base.get(n)) for n in ns)
        J = [r["J_agent_cents"] for r in rows]
        print(f"{tag}: played in {time.time() - t:.0f} s; RSS {es.rss(J)}; fallback weeks {sum(r['fallback_weeks'] for r in rows)}")
        print(f"  shortage T/ep {np.mean([r['cost']['shortage'] for r in rows]) / 1e12:.4f}  shed {np.mean([r['cost']['shed'] for r in rows]) / 1e12:.4f}"
              f"  total {np.mean(J) / 1e14:.4f}")
        (HERE / f"play_{tag}.json").write_text(json.dumps(rows))
    else:
        rows = json.loads((HERE / f"play_{tag}.json").read_text())
        res = Parallel(n_jobs=n_jobs, verbose=5)(delayed(bound)(r["episode"], es._spec, r) for r in rows)
        (HERE / f"bound_{tag}.json").write_text(json.dumps(dict(res)))
        print("written", HERE / f"bound_{tag}.json")


if __name__ == "__main__":
    main(*sys.argv[1:])
