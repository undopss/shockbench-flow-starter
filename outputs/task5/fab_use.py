"""Per fab: lots started by the agent vs the clairvoyant plan (and naive), summed over the episode.

    uv run python outputs/task5/fab_use.py full 0 devpick:2,2,1,1 agents/mpc_chip '{"fab_cap_mode":"observed"}' 4
"""
import json, sys, time, shutil
from pathlib import Path
import numpy as np
from joblib import Parallel, delayed
sys.path.insert(0, "outputs")
import cost_breakdown as cb
from variants import pick_episodes


def run(n, spec, root):
    import shockbench_flow.oracle.lp as olp
    from shockbench_flow_agent.scoring import _world
    cap = {}
    b0, s0 = olp.build_lp, olp.solve_oracle
    def build(*a, **k):
        cap["model"] = b0(*a, **k); return cap["model"]
    def solve(*a, **k):
        cap["res"] = s0(*a, **k); return cap["res"]
    olp.build_lp, olp.solve_oracle = build, solve
    row = cb.episode(n, spec, root)
    task, entropy, regime, reps, cache = spec
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    model, res = cap["model"], cap["res"]
    p = np.zeros(len(inst.fabs))
    if res.x is not None:
        for i, key in enumerate(model.keys):
            if key[0] == "p":
                p[key[-1]] += res.x[i]
    row["oracle_starts"] = p.tolist()
    row["fab_ids"] = [inst.nodes[f].id for f in inst.fabs]
    row["cap_weeks"] = [float(np.sum(marks.alpha_bar[:, fi] * marks.R[:, fi]) * inst.nodes[f].fab.cap0) for fi, f in enumerate(inst.fabs)]
    return row


def main(task, entropy, eps, agent, params, n_jobs):
    from shockbench_flow_agent.scoring import EpisodeSet
    n_jobs, entropy = int(n_jobs), int(entropy)
    folder = Path("outputs/task5/agent_copy") / Path(agent).name
    if folder.exists(): shutil.rmtree(folder)
    shutil.copytree(agent, folder, ignore=shutil.ignore_patterns("__pycache__", "params.json"))
    p = json.loads(params)
    if p: (folder / "params.json").write_text(json.dumps(p))
    es = EpisodeSet.build(task, pick_episodes(task, entropy, eps, n_jobs), entropy=entropy, n_jobs=n_jobs)
    ns = [int(n) for n in es.episodes]
    t = time.time()
    rows = Parallel(n_jobs=n_jobs)(delayed(run)(n, es._spec, str(folder.resolve())) for n in ns)
    print(f"{time.time()-t:.0f}s")
    out = Path(f"outputs/task5/fab_use_{task}_{entropy}_{eps.replace(':','-').replace(',','_')}_{Path(agent).name}.json")
    out.write_text(json.dumps(rows))
    fids = rows[0]["fab_ids"]
    for r in rows:
        print(f"\nepisode {r['episode']}: J agent {r['J_agent_cents']/100:.4e} naive {r['J_naive_cents']/100:.4e} oracle {r['J_oracle_cents']/100:.4e}")
        print(f"{'fab':20s} {'cap*wk':>10s} {'agent':>10s} {'naive':>10s} {'oracle':>10s}")
        for fi, f in enumerate(fids):
            print(f"{f:20s} {r['cap_weeks'][fi]:10.3e} {r['detail']['lots_started'][fi]:10.3e} {r['naive_detail']['lots_started'][fi]:10.3e} {r['oracle_starts'][fi]:10.3e}")
        print("shortage agent", f"{r['agent']['shortage']:.3e}", "oracle", f"{r['oracle']['shortage']:.3e}", "shed agent", f"{r['agent']['shed']:.3e}", "oracle", f"{r['oracle']['shed']:.3e}")

if __name__ == "__main__":
    main(*sys.argv[1:])
