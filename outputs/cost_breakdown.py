"""Where an agent loses money: its cost components next to naive's and the clairvoyant plan's, per episode.

    python outputs/cost_breakdown.py full 0 dev agents/mpc 3   (episodes: "dev", a count k, or a,b,c)

Plays the agent exactly as ``sbf evaluate`` does (same worlds, seeds, fallback) and recomputes the two references the way
``EpisodeSet`` builds them, keeping their per-component costs. Writes outputs/cost_breakdown_<task>_<root>_<n>_<agent>.json
and prints USD means per component, overall and per harm level.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

COMPONENTS = ("freight", "war_risk", "tariff", "holding", "queue_holding", "shortage", "disposal", "shed")


def _sum_records(traj):
    tot = dict.fromkeys(COMPONENTS, 0.0)
    for r in traj.records:
        for c in COMPONENTS:
            tot[c] += float(getattr(r.costs, c))
    tot["salvage_credit"] = -float(traj.salvage or 0.0)
    return tot


def _detail(traj):
    """Per-sink demand/served/lost/backlog, fab starts, OSAT packaging and disposal per stock slot, summed over weeks."""
    R = traj.records
    out = {f: np.sum([getattr(r, f) for r in R], axis=0).tolist() for f in ("demand", "served", "lost", "lots_started",
                                                                          "disposal")}
    out["backlog_end"] = np.asarray(R[-1].backlog).tolist()
    pk = {}
    for r in R:
        for key, v in r.packaged.items():
            pk[str(key)] = pk.get(str(key), 0.0) + float(v)
    out["packaged"] = pk
    return out


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
    if agent_root.startswith("policy:"):  # a package baseline, played as outputs/compare_baselines.py plays it
        from shockbench_flow.evaluation.cache import fq_quantiles
        from shockbench_flow.hosting.tasks import get_task
        from shockbench_flow.policies.naive_fq import generator_quantiles
        from shockbench_flow.policies.registry import GeneratorRef, PolicyContext, make_policy

        fq_quantiles(inst, params, reps, cache_dir=cache)
        ctx = PolicyContext(fq_quantile=generator_quantiles(inst, params, reps),
                            generator=GeneratorRef(task, get_task(task).gamma), fq_replications=reps)
        pol = make_policy(agent_root.split(":", 1)[1], ctx)
        cpu, act = [], pol.act

        def timed(obs):
            c = time.process_time()
            a = act(obs)
            cpu.append(time.process_time() - c)
            return a

        pol.act = timed
        traj = rollout(inst, pol, omega, regime, pseed, marks=marks, fallback=fallback)
    else:
        shim = _metered_shim(load_agent_class(agent_root, f"submission_{Path(agent_root).stem}"), None)
        traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=fallback)
        unload_agent()
        cpu = list(getattr(shim, "cpu_weeks", []))
    agent = _sum_records(traj)
    detail = _detail(traj)

    naive_traj = rollout(inst, anchor_policy(inst, params, reps), omega, ANCHOR_REGIME, pseed, marks=marks,
                         fallback=fallback)
    naive = _sum_records(naive_traj)
    naive_detail = _detail(naive_traj)

    model = build_lp(inst, marks)
    res = solve_oracle(model, method=ORACLE_METHOD)
    oracle = None
    if res.x is not None:
        weekly, salvage = lp_costs(model, res.x)
        oracle = {c: float(sum(getattr(w, c) for w in weekly)) for c in COMPONENTS}
        oracle["salvage_credit"] = -float(salvage)
    return {
        "episode": n,
        "omega_hash": omega.hash,
        "J_agent_cents": traj.J_cents,
        "J_naive_cents": naive_traj.J_cents,
        "J_oracle_cents": res.J_cents,
        "fallback_weeks": sum(took_fallback(r) for r in traj.records),
        "cpu_max": max(cpu, default=None),
        "cpu_median": float(np.median(cpu)) if cpu else None,
        "agent": agent,
        "naive": naive,
        "oracle": oracle,
        "detail": detail,
        "naive_detail": naive_detail,
        "seconds": round(time.perf_counter() - t0, 1),
    }


def table(rows, title):
    keys = list(COMPONENTS) + ["salvage_credit"]
    ok = [r for r in rows if r["oracle"] is not None]
    print(f"\n{title}: {len(ok)} episodes (USD per episode, mean)")
    print(f"{'component':15s} {'naive':>12s} {'agent':>12s} {'perfect':>12s} {'agent-perfect':>14s} {'share of gap':>12s}")
    gap_tot = sum(np.mean([r["agent"][k] - r["oracle"][k] for r in ok]) for k in keys)
    for k in keys + ["TOTAL"]:
        if k == "TOTAL":
            a = sum(np.mean([r["agent"][c] for r in ok]) for c in keys)
            nv = sum(np.mean([r["naive"][c] for r in ok]) for c in keys)
            o = sum(np.mean([r["oracle"][c] for r in ok]) for c in keys)
        else:
            a, nv, o = (np.mean([r[s][k] for r in ok]) for s in ("agent", "naive", "oracle"))
        share = (a - o) / gap_tot * 100 if gap_tot else float("nan")
        print(f"{k:15s} {nv:12.4e} {a:12.4e} {o:12.4e} {a - o:14.4e} {share:11.1f}%")


def main(task, entropy, neps, agent, n_jobs):
    from shockbench_flow_agent.scoring import EpisodeSet

    entropy, n_jobs = int(entropy), int(n_jobs)
    eps = "dev" if neps == "dev" else ([int(x) for x in neps.split(",")] if "," in neps else int(neps))
    es = EpisodeSet.build(task, eps, entropy=entropy, n_jobs=n_jobs)
    ns = [int(n) for n in es.episodes]
    root = agent if agent.startswith("policy:") else str(Path(agent).resolve())
    out = Path(f"outputs/cost_breakdown_{task}_{entropy}_{neps}_{Path(agent).name.replace(':', '-')}.json")
    t = time.time()
    rows = Parallel(n_jobs=n_jobs, verbose=10)(delayed(episode)(n, es._spec, root) for n in ns)
    strata = {r["episode"]: r["stratum"] for r in es.references}
    for r, ref in zip(rows, es.references):
        r["stratum"] = strata[r["episode"]]
        r["J_oracle_cached"] = ref["J_oracle_cents"]
        r["J_naive_cached"] = ref["J_naive_cents"]
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
