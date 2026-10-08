"""Task 20: why packaged/raw chips are disposed of (agent only), and could they have been sold?

    uv run python outputs/task-20/disp20.py <small|full> <entropy> <N|dev|devpick:...> <agent> <n_jobs>

Per chip stock slot (OSAT packaged chips, fab raw chips) and week with disposal > 0: was the slot's outflow
  blocked   no permitted out-edge for k with capacity > 0 that week (sanction / capacity cut),
  full      the agent's executed outflow on the slot's out-edges was >= 95% of their capacity that week,
  unused    there was spare permitted out-edge capacity the agent didn't use.
And: did any sink of that product lose sales that week (if not, the chips had nowhere useful to go anyway).
"""

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def episode(n, spec, agent_root):
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _metered_shim, _policy_seed, _world
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime, reps, cache = spec
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
    shim = _metered_shim(load_agent_class(agent_root, f"submission_{Path(agent_root).stem}"), None)
    traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=fallback)
    unload_agent()
    R = traj.records
    N, K, E = inst.nodes, inst.commodities, inst.edges
    u = np.asarray(marks.u)
    Z = np.asarray(marks.prohibited)
    pi = defaultdict(float)
    for d in inst.demands:
        pi[d.k] = max(pi[d.k], d.pi)
    pack_of = {}  # raw k -> packaged k
    for o in inst.osats:
        pack_of.update(N[o].osat.packages)
    out = defaultdict(lambda: defaultdict(float))
    for s, slot in enumerate(inst.stock_slots):
        kid = K[slot.k].id
        if not kid.startswith("chip") or slot.storage is None:
            continue
        kp = slot.k if slot.k in pi else pack_of.get(slot.k)
        sinks_k = [i for i, d in enumerate(inst.demands) if d.k == kp]
        oute = [e for e, ed in enumerate(E) if ed.tail == slot.node and slot.k in ed.K]
        key = f"{N[slot.node].id}/{kid}"
        for t, r in enumerate(R):
            o = float(r.disposal[s])
            if o <= 0:
                continue
            capt = sum(u[t, e] for e in oute if not Z[t, e, slot.k])
            ex = sum(v for (e, k, _l), v in r.x.items() if e in oute and k == slot.k)
            cls = "blocked" if capt <= 1e-9 else ("full" if ex >= 0.95 * capt else "unused")
            lost = sum(r.lost[i] for i in sinks_k)
            out[key][cls] += o
            out[key][cls + "_lostwk"] += o if lost > 1e-6 else 0.0
            out[key]["value"] += o * pi.get(kp, 0.0)
            out[key]["storage"] = slot.storage
            out[key]["n_out"] = len(oute)
    return {"episode": n, "slots": {k: dict(v) for k, v in out.items()}}


def main(task, entropy, neps, agent, n_jobs):
    from shockbench_flow_agent.scoring import EpisodeSet
    from variants import pick_episodes

    entropy, n_jobs = int(entropy), int(n_jobs)
    eps = pick_episodes(task, entropy, neps, n_jobs)
    es = EpisodeSet.build(task, eps, entropy=entropy, n_jobs=n_jobs)
    t = time.time()
    rows = Parallel(n_jobs=n_jobs)(delayed(episode)(int(n), es._spec, str(Path(agent).resolve())) for n in es.episodes)
    Path(f"outputs/task-20/disp20_{task}_{Path(agent).name}.json").write_text(json.dumps(rows))
    n = len(rows)
    tot = defaultdict(lambda: defaultdict(float))
    for r in rows:
        for k, v in r["slots"].items():
            for c, x in v.items():
                tot[k][c] += x / n if c not in ("storage", "n_out") else 0
                if c in ("storage", "n_out"):
                    tot[k][c] = x
    print(f"{n} episodes, {time.time()-t:.0f} s. Chip disposal per episode (M units) by outflow state that week;"
          " 'lost' = of which in weeks when a sink of that product lost sales")
    print(f"{'slot':36s} {'storage':>9s} {'n_out':>5s} {'blocked':>8s} {'(lost)':>7s} {'full':>7s} {'(lost)':>7s} {'unused':>7s} {'(lost)':>7s} {'value T':>8s}")
    allv = defaultdict(float)
    for k, v in sorted(tot.items(), key=lambda kv: -kv[1]["value"]):
        print(f"{k:36s} {v['storage']:9.0f} {int(v['n_out']):5d} " + " ".join(
            f"{v[c]/1e6:7.3f} {v[c+'_lostwk']/1e6:7.3f}" for c in ("blocked", "full", "unused")) + f" {v['value']/1e12:8.4f}")
        for c, x in v.items():
            if c not in ("storage", "n_out"):
                allv[c] += x
    print("TOTAL M units:", {c: round(x / 1e6, 3) for c, x in allv.items() if c != "value"}, f"value {allv['value']/1e12:.4f} T")


if __name__ == "__main__":
    main(*sys.argv[1:])
