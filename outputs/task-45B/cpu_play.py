"""Task 45B: replay an agent on full root 1827351891 (20 episodes) and record CPU seconds per week (process_time of
Agent(config) + act for week 1, act alone after). Usage: cpu_play.py <agent_dir> <n_jobs> <out.json>"""
import json, sys, time
from pathlib import Path
import numpy as np
from joblib import Parallel, delayed


def episode(n, spec, root):
    from shockbench_flow.dynamics.env import rollout, took_fallback
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _metered_shim, _policy_seed, _world
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime, reps, cache = spec
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    shim = _metered_shim(load_agent_class(root, f"submission_{Path(root).stem}"), None)
    times, act = [], shim.act

    def timed(obs):
        c = time.process_time()
        a = act(obs)
        times.append(shim.carry + time.process_time() - c if not times else time.process_time() - c)
        return a

    shim.act = timed
    traj = rollout(inst, shim, omega, regime, _policy_seed(entropy, n, NO_ZIP_SHA256), marks=marks, fallback=fallback)
    unload_agent()
    return {"episode": n, "J": traj.J_cents, "fallback_weeks": sum(took_fallback(r) for r in traj.records),
            "cpu": times}


def main(agent, n_jobs, out):
    from shockbench_flow_agent.scoring import EpisodeSet
    es = EpisodeSet.build("full", 20, entropy=1827351891)
    root = str(Path(agent).resolve())
    rows = Parallel(n_jobs=int(n_jobs))(delayed(episode)(int(n), es._spec, root) for n in es.episodes)
    Path(out).write_text(json.dumps(rows))
    allc = np.concatenate([r["cpu"] for r in rows])
    print(f"weeks {len(allc)}, fallback weeks {sum(r['fallback_weeks'] for r in rows)}; CPU s/week: max {allc.max():.3f}, "
          f"p99 {np.percentile(allc, 99):.3f}, median {np.median(allc):.3f}; week 1 (incl. Agent(config)) max "
          f"{max(r['cpu'][0] for r in rows):.3f}")
    print("RSS:", es.rss([r["J"] for r in rows]))


if __name__ == "__main__":
    main(*sys.argv[1:])
