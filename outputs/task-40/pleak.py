"""Task 40: where does pulse-related generation leak on mpc_best? (Full dev, cached references)

    uv run python outputs/task-40/pleak.py full 0 dev 4 [variants.json]
    uv run python outputs/task-40/pleak.py report outputs/task-40/pleak_full_0_dev.json

Plays variants of agents/mpc_best (default: "best" = its params.json, "nopulse" = the same with pulse_plan off and
pulse_weeks 0) exactly as outputs/cost_breakdown.py does and records, per grid with fabs and week: home shed (units,
VOLL USD), served load, fab energy, generation (sum of segments), and per controlled fuel the terminal + grid system:
fuel shipped into it from outside, burned, disposed (terminal / grid), end stock (terminal, grid, in transit), the
output the rationing factor cut while fuel was on hand ("ration loss") and the weeks it happened. Also the supply
thrown away at the sources (availability above the source's storage cap) per fuel.

Fuel balance of a grid's terminal+grid system: burned = inflow - disposal - end residual (stock + in transit), so
d generation (fuel part) = d inflow - d disposal - d end residual, split by mechanism.
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

OUT = Path("outputs/task-40")
BASE = json.loads(Path("agents/mpc_best/params.json").read_text())
VARIANTS = {"best": dict(BASE), "nopulse": dict(BASE, pulse_plan=False, pulse_weeks=0.0)}


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
    T = len(R)
    si = inst.slot_index
    fab_grid = {}
    for gi, members in enumerate(inst.grid_fabs):
        for f in members:
            fab_grid[f] = gi
    psi = inst.params.psi
    energy = np.array([r.energy for r in R])
    lots = np.array([r.lots_started for r in R])
    grids = []
    for gi, g in enumerate(inst.grids):
        members = list(inst.grid_fabs[gi])
        if not members:
            continue
        grid = inst.nodes[g].grid
        # terminals feeding this grid: tails of edges into g that are terminals
        terms = {}
        for e, ed in enumerate(inst.edges):
            if ed.head == g and inst.nodes[ed.tail].type == "terminal":
                terms.setdefault(ed.tail, []).append(e)
        G_bar = np.array([marks.G_bar[t][gi] for t in range(T)])
        rec = {
            "id": inst.nodes[g].id, "voll": float(grid.voll),
            "shed": [float(r.shed[gi]) for r in R],
            "served": [float(r.served_load[gi]) for r in R],
            "y_bar": [float(marks.y_bar[t][gi]) for t in range(T)],
            "fab_e": energy[:, members].sum(1).tolist(),
            "lots": lots[:, members].sum(1).tolist(),
            "gen": [float(sum(v for (gg, k), v in r.segment.items() if gg == gi)) for r in R],
            "fuels": {},
        }
        for k in grid.fuels:
            sys_nodes = {g} | {tn for tn in terms if (tn, k) in si}
            gs = si[(g, k)]
            ts = [si[(tn, k)] for tn in sys_nodes if tn != g]
            inflow = np.zeros(T)
            release = np.zeros(T)
            for t, r in enumerate(R):
                for (e, kk, lane), q in r.x.items():
                    if kk != k:
                        continue
                    ed = inst.edges[e]
                    if ed.head in sys_nodes and ed.tail not in sys_nodes:
                        inflow[t] += q
                    elif ed.head == g and ed.tail in sys_nodes:
                        release[t] += q
            burn = np.array([r.segment.get((gi, k), 0.0) for r in R])
            dispG = np.array([r.disposal[gs] for r in R])
            dispT = np.array([sum(r.disposal[s] for s in ts) for r in R])
            stG = np.array([r.stock[gs] for r in R])
            stT = np.array([sum(r.stock[s] for s in ts) for r in R])
            cap = grid.shares[k] * G_bar
            # ration loss: output the rationing factor removed while the fuel on hand covered more
            rloss = np.zeros(T)
            if k == grid.rationed and psi * grid.ibar.get(k, 0.0) > 0:
                thr = psi * grid.ibar[k]
                Iprev = np.concatenate([[traj.records[0].stock[gs] * 0 + _init(inst, gs)], stG[:-1]])
                ration = np.minimum(1.0, Iprev / thr)
                onhand = stG + burn + dispG  # stock before the burn (after arrivals) = end + burn + disposal
                rloss = np.maximum(np.minimum(cap, onhand) - np.minimum(cap * ration, onhand), 0.0)
            rec["fuels"][str(k)] = {
                "inflow": inflow.tolist(), "release": release.tolist(), "burn": burn.tolist(),
                "dispG": dispG.tolist(), "dispT": dispT.tolist(), "stG": stG.tolist(), "stT": stT.tolist(),
                "cap": cap.tolist(), "rloss": rloss.tolist(), "rationed": k == grid.rationed,
                "name": inst.commodities[k].id if hasattr(inst.commodities[k], "id") else str(k),
            }
        grids.append(rec)
    # supply thrown away at the sources (availability above the cap), per fuel k
    src_lost = {}
    for s, storage in [(s, sl) for s, sl in enumerate(inst.stock_slots)]:
        pass
    lift = np.array([r.lift for r in R])  # (T, S)
    sup = np.array([marks.supply[t] for t in range(T)])
    lost = np.maximum(sup - lift, 0.0).sum(0)
    for s, sl in enumerate(inst.stock_slots):
        if sup[:, s].sum() > 0:
            key = inst.commodities[sl.k].id if hasattr(inst.commodities[sl.k], "id") else str(sl.k)
            src_lost[key] = src_lost.get(key, 0.0) + float(lost[s])
    return {"episode": n, "J_cents": traj.J_cents, "fallback_weeks": sum(took_fallback(r) for r in R),
            "costs": _sum_records(traj), "grids": grids, "src_lost": src_lost}


_INIT = {}


def _init(inst, s):
    if id(inst) not in _INIT:
        from shockbench_flow.dynamics.sim import initial_stock
        _INIT[id(inst)] = initial_stock(inst)
    return float(_INIT[id(inst)][s])


def main(task, entropy, eps_spec, n_jobs="4", variants=None):
    from shockbench_flow_agent.scoring import EpisodeSet

    entropy, n_jobs = int(entropy), int(n_jobs)
    vs = json.loads(Path(variants).read_text()) if variants else VARIANTS
    eps = pick_episodes(task, entropy, eps_spec, n_jobs)
    es = EpisodeSet.build(task, eps, entropy=entropy, n_jobs=n_jobs)
    ns = [int(n) for n in es.episodes]
    strata = {int(r["episode"]): r["stratum"] for r in es.references}
    tag = f"{task}_{entropy}_{eps_spec.replace(':', '-').replace(',', '-')}" + (f"_{Path(variants).stem}" if variants else "")
    res = {}
    for name, params in vs.items():
        folder = OUT / "agents" / name
        if folder.exists():
            shutil.rmtree(folder)
        shutil.copytree("agents/mpc_best", folder, ignore=shutil.ignore_patterns("__pycache__", "params.json"))
        (folder / "params.json").write_text(json.dumps(params))
        t = time.time()
        res[name] = Parallel(n_jobs=n_jobs, verbose=5)(delayed(episode)(n, es._spec, str(folder.resolve())) for n in ns)
        rss = es.rss([r["J_cents"] for r in res[name]])
        print(f"{name}: {time.time() - t:.0f} s, RSS {rss['rss']:.4f} by level {rss['rss_by_stratum']}", flush=True)
        for r in res[name]:
            r["stratum"] = strata[r["episode"]]
            r["rss"] = rss["rss"]
        (OUT / f"pleak_{tag}.json").write_text(json.dumps(res))
    report(res)


def report(res, a_name="best", b_name="nopulse"):
    a, b = res[a_name], res[b_name]
    n = len(a)
    print(f"\n{n} episodes; mean per episode; diff = {a_name} - {b_name}")
    for c in list(COMPONENTS) + ["salvage_credit"]:
        va, vb = np.mean([r["costs"][c] for r in a]), np.mean([r["costs"][c] for r in b])
        print(f"  {c:15s} {a_name} {va:12.4e} {b_name} {vb:12.4e} diff {va - vb:+12.4e}")
    ja, jb = np.mean([r["J_cents"] for r in a]) / 100, np.mean([r["J_cents"] for r in b]) / 100
    print(f"  {'TOTAL J':15s} {a_name} {ja:12.4e} {b_name} {jb:12.4e} diff {ja - jb:+12.4e}")

    def m(rows, gi, f):
        return float(np.mean([f(r["grids"][gi]) for r in rows]))

    print(f"\nper grid (units of grid output; USD = units x VOLL), mean per episode, {a_name} | {b_name} | diff")
    tot = {"shed": 0.0, "transfer": 0.0, "lostgen": 0.0}
    for gi, g in enumerate(a[0]["grids"]):
        voll = g["voll"]
        sh = [m(x, gi, lambda q: sum(q["shed"])) for x in (a, b)]
        fe = [m(x, gi, lambda q: sum(q["fab_e"])) for x in (a, b)]
        gen = [m(x, gi, lambda q: sum(q["gen"])) for x in (a, b)]
        lots = [m(x, gi, lambda q: sum(q["lots"])) for x in (a, b)]
        zero = [m(x, gi, lambda q: sum(1 for s in q["shed"] if s <= 1e-9)) for x in (a, b)]
        d_sh, d_fe, d_gen = sh[0] - sh[1], fe[0] - fe[1], gen[0] - gen[1]
        # d shed = d fab energy - d generation (served = gen - fab energy, shed = y_bar - served)
        tot["shed"] += d_sh * voll
        tot["transfer"] += d_fe * voll
        tot["lostgen"] += -d_gen * voll
        print(f"{g['id']:10s} shed {sh[0]:9.0f} | {sh[1]:9.0f} | {d_sh:+8.0f} ({d_sh * voll:+.3e} USD)   fabE {fe[0]:8.0f} |"
              f" {fe[1]:8.0f} | {d_fe:+7.0f}   gen {d_gen:+8.0f}   lots {lots[0]:.3g} | {lots[1]:.3g}   0-shed wk "
              f"{zero[0]:.1f} | {zero[1]:.1f}")
        for k in g["fuels"]:
            def fs(rows, key, last=False):
                return float(np.mean([(r["grids"][gi]["fuels"][k][key][-1] if last else sum(r["grids"][gi]["fuels"][k][key]))
                                      for r in rows]))
            vals = {}
            for key in ("inflow", "burn", "dispG", "dispT", "rloss"):
                vals[key] = [fs(x, key) for x in (a, b)]
            for key in ("stG", "stT"):
                vals[key] = [fs(x, key, True) for x in (a, b)]
            vals["resid"] = [vals["inflow"][i] - vals["burn"][i] - vals["dispG"][i] - vals["dispT"][i] for i in (0, 1)]
            rw = [float(np.mean([sum(1 for v in r["grids"][gi]["fuels"][k]["rloss"] if v > 1e-9) for r in x])) for x in (a, b)]
            nm = g["fuels"][k]["name"]
            print("    " + f"{nm:8s}" + "  ".join(f"{key} {vals[key][0]:9.0f}/{vals[key][1]:9.0f}({vals[key][0] - vals[key][1]:+8.0f})"
                                             for key in ("inflow", "burn", "dispT", "dispG", "resid", "stT", "stG", "rloss"))
                  + f"  rloss-wk {rw[0]:.1f}/{rw[1]:.1f}")
    print(f"\nTOTAL fab grids: d shed {tot['shed']:+.4e} USD = transfer to fabs {tot['transfer']:+.4e} + lost generation"
          f" {tot['lostgen']:+.4e}  (0.01 RSS ~ 3.4e10)")
    keys = sorted(set(a[0]["src_lost"]) | set(b[0]["src_lost"]))
    print("source supply thrown away (units/ep): " + ", ".join(
        f"{k} {np.mean([r['src_lost'].get(k, 0) for r in a]):.0f}/{np.mean([r['src_lost'].get(k, 0) for r in b]):.0f}" for k in keys))


if __name__ == "__main__":
    if sys.argv[1] == "report":
        rr = json.loads(Path(sys.argv[2]).read_text())
        report(rr, *(sys.argv[3:5] if len(sys.argv) > 4 else ()))
    else:
        main(*sys.argv[1:])
