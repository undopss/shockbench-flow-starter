"""Task 22: the package's joint LP (mpc_det family) vs our agent on the same Full episodes, with per-fab / per-grid /
per-sink detail, plus the oracle's detail. One job per (episode, player) and one per episode for the oracle.

    uv run python outputs/task-22/gap22.py full 0 devpick:2,2,1,1 4 agents/mpc_fab3sell policy:mpc_det \
        policy:mpc_det@L+8 policy:mpc_det_safety

A player is an agent folder, or policy:<name>[@<H label>] (H label from lp_common.H_SWEEP, mpc_det only).
Writes outputs/task-22/gap22_<task>_<entropy>_<eps>.json (merged with earlier runs of the same episodes).
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "task-17"))
from cost_breakdown import COMPONENTS, _detail, _sum_records  # noqa: E402
from gap17 import _odetail, _safe, meta  # noqa: E402


def make(spec_name, inst, task, reps, cache):
    from shockbench_flow.evaluation.cache import fq_quantiles
    from shockbench_flow.hosting.tasks import get_task, task_generator
    from shockbench_flow.policies.naive_fq import generator_quantiles
    from shockbench_flow.policies.registry import GeneratorRef, PolicyContext, make_policy

    _, params = task_generator(task)
    fq_quantiles(inst, params, reps, cache_dir=cache)
    ctx = PolicyContext(fq_quantile=generator_quantiles(inst, params, reps),
                        generator=GeneratorRef(task, get_task(task).gamma), fq_replications=reps)
    name = spec_name.split(":", 1)[1]
    if "@" in name:
        from shockbench_flow.policies.mpc_det import MpcDetParams
        base, h = name.split("@", 1)
        return make_policy(base, ctx, MpcDetParams(H=h))
    return make_policy(name, ctx)


def play(n, spec, player):
    from shockbench_flow.dynamics.env import rollout, took_fallback
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _metered_shim, _policy_seed, _world
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime, reps, cache = spec
    t0 = time.perf_counter()
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
    if player.startswith("policy:"):
        pol = make(player, inst, task, reps, cache)
        cpu, act = [], pol.act

        def timed(obs):
            c = time.process_time()
            a = act(obs)
            cpu.append(time.process_time() - c)
            return a

        pol.act = timed
        traj = rollout(inst, pol, omega, regime, pseed, marks=marks, fallback=fallback)
        inner_fb = sum(bool(getattr(s, "fallback", False)) for s in getattr(pol, "telemetry", []))
    else:
        root = str(Path(player).resolve())
        shim = _metered_shim(load_agent_class(root, f"submission_{Path(root).stem}"), None)
        traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=fallback)
        unload_agent()
        cpu = list(getattr(shim, "cpu_weeks", []))
        inner_fb = None
    R = traj.records
    d = _detail(traj)
    d["energy"] = np.sum([r.energy for r in R], axis=0).tolist()
    d["shed"] = np.sum([r.shed for r in R], axis=0).tolist()
    d["lots_w"] = np.array([r.lots_started for r in R]).tolist()
    d["shed_w"] = np.array([r.shed for r in R]).tolist()
    d["lost_w"] = np.array([r.lost for r in R]).tolist()
    d["stock_end"] = np.asarray(R[-1].stock).tolist()
    sidx = {(s.node, s.k): i for i, s in enumerate(inst.stock_slots)}
    wslots = [sidx.get((f, inst.nodes[f].fab.input)) for f in inst.fabs]
    d["wafer_stock_w"] = [[float(r.stock[s]) if s is not None else 0.0 for s in wslots] for r in R]
    d["energy_w"] = np.array([r.energy for r in R]).tolist()
    return {"episode": n, "player": player, "J_cents": traj.J_cents, "costs": _sum_records(traj), "detail": d,
            "fallback_weeks": sum(took_fallback(r) for r in R), "inner_fallback_weeks": inner_fb,
            "cpu_max": max(cpu, default=None), "cpu_median": float(np.median(cpu)) if cpu else None,
            "cpu_mean": float(np.mean(cpu)) if cpu else None, "seconds": round(time.perf_counter() - t0, 1)}


def oracle(n, spec):
    from shockbench_flow.oracle.lp import ORACLE_METHOD, build_lp, lp_costs, solve_oracle
    from shockbench_flow_agent.scoring import _world

    task, entropy, regime, reps, cache = spec
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    model = build_lp(inst, marks)
    res = solve_oracle(model, method=ORACLE_METHOD)
    weekly, salvage = lp_costs(model, res.x)
    costs = {c: float(sum(getattr(w, c) for w in weekly)) for c in COMPONENTS}
    costs["salvage_credit"] = -float(salvage)
    od = _safe(_odetail, inst, model, res.x)
    od.pop("xi", None)
    od.pop("O", None)
    return {"episode": n, "player": "oracle", "J_cents": res.J_cents, "costs": costs, "detail": od,
            "meta": _safe(meta, inst)}


def main(task, entropy, neps, n_jobs, *players):
    from shockbench_flow_agent.scoring import EpisodeSet
    from variants import pick_episodes

    entropy, n_jobs = int(entropy), int(n_jobs)
    eps = pick_episodes(task, entropy, neps, n_jobs)
    es = EpisodeSet.build(task, eps, entropy=entropy, n_jobs=n_jobs)
    ns = [int(n) for n in es.episodes]
    out = Path(f"outputs/task-22/gap22_{task}_{entropy}_{neps.replace(':', '-').replace(',', '-')}.json")
    old = json.loads(out.read_text()) if out.is_file() else {"refs": None, "rows": []}
    have = {(r["episode"], r["player"]) for r in old["rows"]}
    jobs = [delayed(oracle)(n, es._spec) for n in ns if (n, "oracle") not in have]
    jobs += [delayed(play)(n, es._spec, p) for p in players for n in ns if (n, p) not in have]
    print(f"{len(jobs)} jobs on {ns}", flush=True)
    t = time.time()
    rows = Parallel(n_jobs=n_jobs, verbose=10)(jobs)
    old["rows"] += rows
    old["refs"] = [{"episode": int(r["episode"]), "stratum": r["stratum"], "J_naive_cents": r["J_naive_cents"],
                    "J_oracle_cents": r["J_oracle_cents"]} for r in es.references]
    out.write_text(json.dumps(old))
    print(f"played in {time.time() - t:.0f} s, written {out}")
    for p in players:
        js = {r["episode"]: r["J_cents"] for r in old["rows"] if r["player"] == p}
        if all(n in js for n in ns):
            print(p, "RSS", es.rss([js[n] for n in ns]))


if __name__ == "__main__":
    main(*sys.argv[1:])
