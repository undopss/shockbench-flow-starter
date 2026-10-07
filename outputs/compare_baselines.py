"""The package's baselines vs our agent on the same cached episodes, scored like `sbf compare`.

    python outputs/compare_baselines.py small 12345 64 greedy_lp,mpc_det,mpc_scen agents/mpc 3
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed
from shockbench_flow.dynamics.env import rollout, took_fallback
from shockbench_flow.evaluation.cache import fq_quantiles
from shockbench_flow.hosting.tasks import get_task, task_generator
from shockbench_flow.policies.naive_fq import generator_quantiles
from shockbench_flow.policies.registry import GeneratorRef, PolicyContext, make_policy
from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
from shockbench_flow_agent.scoring import LEVEL, N_BOOT, EpisodeSet, _boot_stats, _interval, _policy_seed, _world


def play(name, n, spec):
    task, entropy, regime, reps, cache = spec
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    _, params = task_generator(task)
    fq_quantiles(inst, params, reps, cache_dir=cache)
    t = get_task(task)
    ctx = PolicyContext(
        fq_quantile=generator_quantiles(inst, params, reps), generator=GeneratorRef(task, t.gamma), fq_replications=reps
    )
    pol = make_policy(name, ctx)
    cpu, act = [], pol.act

    def timed(obs):
        c = time.process_time()
        a = act(obs)
        cpu.append(time.process_time() - c)
        return a

    pol.act = timed
    traj = rollout(inst, pol, omega, regime, _policy_seed(entropy, n, NO_ZIP_SHA256), marks=marks, fallback=fallback)
    return {
        "episode": n,
        "J": traj.J_cents,
        "fallback_weeks": sum(took_fallback(r) for r in traj.records),
        "cpu_max": max(cpu, default=0.0),
        "cpu_median": float(np.median(cpu)) if cpu else 0.0,
    }


def main(task, entropy, neps, names, ours, n_jobs):
    entropy, neps, n_jobs = int(entropy), int(neps), int(n_jobs)
    es = EpisodeSet.build(task, list(range(neps)), entropy=entropy, n_jobs=n_jobs)
    spec = es._spec
    out = Path(f"outputs/baselines_{task}_{entropy}_{neps}.json")
    res = json.loads(out.read_text()) if out.is_file() else {}

    if ours not in res:
        rows = es.play(str(Path(ours).resolve()), n_jobs=n_jobs)
        res[ours] = {"J": [r["J_policy_cents"] for r in rows], "fallback_weeks": sum(r["fallback_weeks"] for r in rows)}
        out.write_text(json.dumps(res))
        print(f"{ours}: played", flush=True)

    for name in names.split(","):
        if name in res:
            continue
        t0 = time.time()
        try:
            rows = Parallel(n_jobs=n_jobs)(delayed(play)(name, n, spec) for n in range(neps))
        except Exception as err:  # one baseline failing must not stop the others
            print(f"{name}: FAILED {type(err).__name__}: {err}", flush=True)
            continue
        res[name] = {
            "J": [r["J"] for r in rows],
            "fallback_weeks": sum(r["fallback_weeks"] for r in rows),
            "cpu_max": max(r["cpu_max"] for r in rows),
            "cpu_median": float(np.median([r["cpu_median"] for r in rows])),
            "wall_s": round(time.time() - t0),
        }
        out.write_text(json.dumps(res))
        print(f"{name}: played in {res[name]['wall_s']} s", flush=True)

    budget = {"small": 2.0, "full": 4.0}[task]
    print(f"\n{task}, {neps} episodes, root {entropy}; diff = row minus {ours}, 90% paired interval")
    print(f"{'agent':18s} {'RSS':>7s} {'L1':>6s} {'L2':>6s} {'L3':>6s} {'L4':>6s}  {'diff':>7s}  interval"
          f"            fallb  cpu max/median per week (budget {budget} s)")
    Jo = res[ours]["J"]
    for name, r in res.items():
        table = es.rss(r["J"])
        lv = table["rss_by_stratum"]
        ba, bb = _boot_stats(es.references, [r["J"], Jo], table["pooled"], N_BOOT, 0)
        d = ba - bb
        lo, hi = _interval(d, LEVEL) if name != ours else (0.0, 0.0)
        ro = es.rss(Jo)["rss"]
        diff = table["rss"] - ro if table["rss"] is not None and ro is not None else float("nan")
        cpu = f"{r['cpu_max']:.2f} / {r['cpu_median']:.3f}" if "cpu_max" in r else "-"
        print(f"{name:18s} {table['rss'] if table['rss'] is not None else float('nan'):7.4f} " + " ".join((f"{lv[s]:6.3f}" if lv.get(s) is not None else "     -") for s in (1, 2, 3, 4))
              + f"  {diff:+7.4f}  [{lo:+.4f}, {hi:+.4f}]  {r['fallback_weeks']:5d}  {cpu}")


if __name__ == "__main__":
    main(*sys.argv[1:])
