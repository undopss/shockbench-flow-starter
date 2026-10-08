"""Task 17: mpc_buffer's gap to the clairvoyant plan on Full, broken down by component, harm level, sink/product,
fab, grid and disruption type. One run; the per-episode JSON is the raw material for report17.py.

    uv run python outputs/task-17/gap17.py full 0 dev agents/mpc_buffer 4

episode() is outputs/cost_breakdown.py's (same worlds, seeds, fallback, references) plus: agent and oracle lots per fab,
energy per fab, shed per grid, lost per demand, and the episode's disruption events (omega ev_*) and marks summaries.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cost_breakdown import COMPONENTS, _detail, _sum_records, table  # noqa: E402


def meta(inst):
    N = inst.nodes
    K = inst.commodities
    return {
        "fabs": [{"id": N[f].id, "region": inst.regions[N[f].region], "cls": N[f].fab.cls, "cap0": N[f].fab.cap0,
                  "e": N[f].fab.e, "grid": None if N[f].fab.grid is None else N[N[f].fab.grid].id,
                  "product": K[N[f].fab.product].id} for f in inst.fabs],
        "grids": [{"id": N[g].id, "voll": N[g].grid.voll, "priority": N[g].grid.priority,
                   "base_load": N[g].grid.base_load} for g in inst.grids],
        "demands": [{"node": N[d.node].id, "region": inst.regions[N[d.node].region], "k": K[d.k].id, "pi": d.pi,
                     "backlog": d.backlog} for d in inst.demands],
        "chokepoints": [N[c].id for c in inst.chokepoints] if hasattr(inst, "chokepoints") else [],
        "regions": list(inst.regions),
        "nodes": [n.id for n in N],
        "edges": [getattr(e, "id", str(i)) for i, e in enumerate(inst.edges)],
    }


def events(omega, inst, T):
    from shockbench_flow.omega.codes import EVENT_TYPES, TARGET_KINDS
    if "ev_type" not in omega:
        return []
    out = []
    names = {"chokepoint": lambda i: inst.nodes[i].id, "node": lambda i: inst.nodes[i].id,
             "edge": lambda i: getattr(inst.edges[i], "id", str(i)), "region": lambda i: inst.regions[i]}
    for i in range(len(omega["ev_type"])):
        on, du = float(omega["ev_onset"][i]), float(omega["ev_duration"][i])
        if on > T or on + du < 0:
            continue
        tk = TARGET_KINDS[int(omega["ev_target_kind"][i])] if int(omega["ev_target_kind"][i]) >= 0 else None
        tg = int(omega["ev_target"][i])
        try:
            tname = names[tk](tg) if tk else None
        except Exception:
            tname = str(tg)
        out.append({"type": EVENT_TYPES[int(omega["ev_type"][i])], "onset": on, "duration": du,
                    "severity": float(omega["ev_severity"][i]), "target_kind": tk, "target": tname,
                    "region": inst.regions[int(omega["ev_region"][i])] if int(omega["ev_region"][i]) >= 0 else None})
    return out


def _safe(f, *a):
    try:
        return f(*a)
    except Exception as e:  # the extras must never lose the episode
        import traceback
        return {"error": repr(e), "tb": traceback.format_exc()}


def _odetail(inst, model, x):
    F, G, D, T = len(inst.fabs), len(inst.grids), len(inst.demands), model.T
    od = {"lots_started": np.zeros(F), "energy": np.zeros(F), "shed": np.zeros(G), "lost": np.zeros(D),
          "served": np.zeros(D), "lots_w": np.zeros((T, F)), "lost_w": np.zeros((T, D)),
          "shed_w": np.zeros((T, G)), "energy_w": np.zeros((T, F)), "xi": {}, "O": np.zeros(len(inst.stock_slots))}
    for j, key in enumerate(model.keys):
        tag = key[0]
        if tag == "p":
            od["lots_started"][key[2]] += x[j]; od["lots_w"][key[1] - 1, key[2]] += x[j]
        elif tag == "E":
            od["energy"][key[2]] += x[j]; od["energy_w"][key[1] - 1, key[2]] += x[j]
        elif tag == "ysh":
            od["shed"][key[2]] += x[j]; od["shed_w"][key[1] - 1, key[2]] += x[j]
        elif tag == "xi":
            od["xi"][str((key[2], key[3]))] = od["xi"].get(str((key[2], key[3])), 0.0) + float(x[j])
        elif tag == "O":
            od["O"][key[2]] += x[j]
        elif tag == "U":
            od["lost"][key[2]] += x[j]; od["lost_w"][key[1] - 1, key[2]] += x[j]
        elif tag == "D":
            od["served"][key[2]] += x[j]
    od = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in od.items()}
    return od


def episode(n, spec, agent_root):
    from shockbench_flow.dynamics.env import rollout, took_fallback
    from shockbench_flow.hosting.tasks import task_generator
    from shockbench_flow.oracle.lp import ORACLE_METHOD, build_lp, lp_costs, solve_oracle
    from shockbench_flow.policies.naive_fq import anchor_policy
    from shockbench_flow_agent.local_eval import ANCHOR_REGIME, NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _metered_shim, _policy_seed, _world
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime, reps, cache = spec
    t0 = time.perf_counter()
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
    _, params = task_generator(task)

    shim = _metered_shim(load_agent_class(agent_root, f"submission_{Path(agent_root).stem}"), None)
    traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=fallback)
    unload_agent()
    cpu = list(getattr(shim, "cpu_weeks", []))
    R = traj.records
    agent = _sum_records(traj)
    detail = _detail(traj)
    detail["energy"] = np.sum([r.energy for r in R], axis=0).tolist()
    detail["shed"] = np.sum([r.shed for r in R], axis=0).tolist()
    detail["lost_w"] = np.array([r.lost for r in R]).tolist()  # (T, D) for timing
    detail["lots_w"] = np.array([r.lots_started for r in R]).tolist()  # (T, F)
    detail["shed_w"] = np.array([r.shed for r in R]).tolist()  # (T, G)
    detail["energy_w"] = np.array([r.energy for r in R]).tolist()  # (T, F)
    detail["served_load_w"] = np.array([r.served_load for r in R]).tolist()  # (T, G)
    detail["disposal_w_chip"] = None
    sidx = {(s.node, s.k): i for i, s in enumerate(inst.stock_slots)}
    wslots = [sidx.get((f, inst.nodes[f].fab.input)) for f in inst.fabs]
    detail["wafer_stock_w"] = [[float(r.stock[s]) if s is not None else 0.0 for s in wslots] for r in R]  # (T, F)
    detail["stock_end"] = np.asarray(R[-1].stock).tolist()
    detail["slots"] = [[inst.nodes[s.node].id, inst.commodities[s.k].id] for s in inst.stock_slots]

    naive_traj = rollout(inst, anchor_policy(inst, params, reps), omega, ANCHOR_REGIME, pseed, marks=marks,
                         fallback=fallback)
    naive = _sum_records(naive_traj)
    nd = _detail(naive_traj)
    nd["shed"] = np.sum([r.shed for r in naive_traj.records], axis=0).tolist()

    model = build_lp(inst, marks)
    res = solve_oracle(model, method=ORACLE_METHOD)
    oracle, od = None, None
    if res.x is not None:
        weekly, salvage = lp_costs(model, res.x)
        oracle = {c: float(sum(getattr(w, c) for w in weekly)) for c in COMPONENTS}
        oracle["salvage_credit"] = -float(salvage)
        od = _safe(_odetail, inst, model, res.x)

    T = len(R)
    ms = _safe(lambda: {"o_mean": np.asarray(marks.o).mean(axis=0).tolist(),  # per chokepoint
          "R_mean": np.asarray(marks.R).mean(axis=0).tolist(),  # per fab
          "Gratio_min": (np.asarray(marks.G_bar) / np.maximum(np.asarray(marks.y_bar), 1e-12)).min(axis=0).tolist(),
          "Gbar_mean": np.asarray(marks.G_bar).mean(axis=0).tolist(),
          "ybar_mean": np.asarray(marks.y_bar).mean(axis=0).tolist(),
          "prohib_new": int(np.asarray(marks.prohibited).sum() - T * np.asarray(marks.prohibited)[0].sum()),
          "tariff_mean": float(np.asarray(marks.tariff).mean())})
    return {
        "episode": n, "omega_hash": omega.hash,
        "J_agent_cents": traj.J_cents, "J_naive_cents": naive_traj.J_cents, "J_oracle_cents": res.J_cents,
        "fallback_weeks": sum(took_fallback(r) for r in traj.records),
        "cpu_max": max(cpu, default=None), "cpu_median": float(np.median(cpu)) if cpu else None,
        "agent": agent, "naive": naive, "oracle": oracle, "detail": detail, "naive_detail": nd, "oracle_detail": od,
        "events": _safe(events, omega, inst, T), "marks": ms, "meta": _safe(meta, inst),
        "seconds": round(time.perf_counter() - t0, 1),
    }


def main(task, entropy, neps, agent, n_jobs):
    from shockbench_flow_agent.scoring import EpisodeSet

    entropy, n_jobs = int(entropy), int(n_jobs)
    from variants import pick_episodes
    eps = pick_episodes(task, entropy, neps, n_jobs)
    es = EpisodeSet.build(task, eps, entropy=entropy, n_jobs=n_jobs)
    ns = [int(n) for n in es.episodes]
    root = str(Path(agent).resolve())
    out = Path(f"outputs/task-17/gap17v2_{task}_{entropy}_{neps.replace(':', '-').replace(',', '-')}_{Path(agent).name}.json")
    t = time.time()
    rows = Parallel(n_jobs=n_jobs, verbose=10)(delayed(episode)(n, es._spec, root) for n in ns)
    for r, ref in zip(rows, es.references):
        r["stratum"] = ref["stratum"]
        r["J_oracle_cached"] = ref["J_oracle_cents"]
        r["J_naive_cached"] = ref["J_naive_cents"]
    for r in rows[1:]:
        r["meta"] = None
    out.write_text(json.dumps(rows))
    print(f"played in {time.time() - t:.0f} s, written {out}")
    agree = sum(r["J_oracle_cents"] == r["J_oracle_cached"] and r["J_naive_cents"] == r["J_naive_cached"] for r in rows)
    print(f"references reproduced exactly on {agree}/{len(rows)} episodes; fallback weeks {sum(r['fallback_weeks'] for r in rows)}")
    print("RSS check:", es.rss([r["J_agent_cents"] for r in rows]))
    cm = [r["cpu_max"] for r in rows if r["cpu_max"] is not None]
    if cm:
        print(f"CPU s per week: max {max(cm):.2f}, median of episode medians {np.median([r['cpu_median'] for r in rows]):.3f}")
    table(rows, "ALL")
    for s in sorted({r["stratum"] for r in rows if r["stratum"] is not None}):
        table([r for r in rows if r["stratum"] == s], f"harm level {s}")


if __name__ == "__main__":
    main(*sys.argv[1:])
