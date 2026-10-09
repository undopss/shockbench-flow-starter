"""Task 35: how much chip / wafer cargo waits in strait queues, and why (next edge full, kappa_ct, closed).

Plays an agent on Full episodes (no naive fallback, as task 28 / 30's probes) and books, per chokepoint and week, the
container-pool cargo (wafer, chips) still queued at the end of the week (it did not release in its week) to a cause:
  closed   : the chokepoint's open fraction < 0.5
  edgefull : the lane's next edge carried >= 99% of its capacity this week (the LP's missing shared-edge row)
  kappa    : the chokepoint's container releases used >= 99% of kappa_ct
  other    : prohibited next edge, or none of the above
Also counts the static (commodity, later edge) groups that two chip routes with different first edges share.

    uv run python outputs/task-35/meas35.py full 0 devpick:2,2,1,1 agents/mpc_jpow 4
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def static_groups(inst):
    ct = [k for k in range(len(inst.commodities)) if inst.commodity_pool[k] == 1]
    firsts = defaultdict(set)  # (k, later edge) -> first edges of chip routes using it
    firsts_any = defaultdict(set)  # later edge -> first edges (any container commodity)
    for (e, k, lane) in inst.action_slots:
        if k not in ct or lane is None:
            continue
        route = list(inst.lanes[lane].edges)
        route = route[route.index(e):]
        for e2 in route[1:]:
            firsts[(k, e2)].add(route[0])
            firsts_any[e2].add(route[0])
    g = {key: v for key, v in firsts.items() if len(v) >= 2}
    ga = {key: v for key, v in firsts_any.items() if len(v) >= 2}
    return g, ga, ct


def episode(n, spec, agent_root):
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _label, _metered_shim, _policy_seed
    from shockbench_flow.disruption.sampler import sample_omega
    from shockbench_flow.hosting.tasks import task_generator
    from shockbench_flow.marks import compute_marks
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime = spec
    inst, gparams = task_generator(task)
    omega = sample_omega(inst, gparams, entropy, n, _label(entropy))
    marks = compute_marks(inst, omega)
    pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
    shim = _metered_shim(load_agent_class(agent_root, f"submission_{Path(agent_root).stem}"), None)
    traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=None)
    unload_agent()
    R = traj.records
    E = inst.edges
    ids = [nd.id for nd in inst.nodes]
    _g, _ga, ct = static_groups(inst)
    cord = inst.chokepoint_ordinal
    cause = defaultdict(float)  # cause -> unit-weeks queued (container pool)
    by_chk = defaultdict(float)
    by_edge = defaultdict(float)  # next edge id -> unit-weeks queued because it was full
    by_k = defaultdict(float)
    val = defaultdict(float)
    dispatched = 0.0
    for t, r in enumerate(R):
        xe = defaultdict(float)
        ct_rel = defaultdict(float)
        for (e, k, lane), q in r.x.items():
            xe[e] += q
            if inst.commodity_pool[k] == 1 and E[e].tail in cord:
                ct_rel[E[e].tail] += q
            if inst.commodity_pool[k] == 1 and E[e].tail not in cord:
                dispatched += q
        for (c, k, lane), q in r.queue.items():
            if q <= 1e-9 or inst.commodity_pool[k] != 1:
                continue
            ci = cord[c]
            ne = None
            for e in inst.lanes[lane].edges:
                if E[e].tail == c:
                    ne = e
            if marks.o[t][ci] < 0.5:
                why = "closed"
            elif ne is not None and xe[ne] >= 0.99 * float(marks.u[t][ne]):
                why = "edgefull"
                by_edge[E[ne].id] += q
            elif ct_rel[c] >= 0.99 * float(marks.kappa[t][ci][1]):
                why = "kappa"
            else:
                why = "other"
            cause[why] += q
            by_chk[ids[c]] += q
            by_k[inst.commodities[k].id] += q
    costs = defaultdict(float)
    for r in R:
        for name, v in r.costs.as_dict().items():
            costs[name] += v
    # chip lost sales value
    lost_units = defaultdict(float)
    lost_val = 0.0
    for r in R:
        for d, dm in enumerate(inst.demands):
            if r.lost[d] > 0:
                lost_units[inst.commodities[dm.k].id] += float(r.lost[d])
                lost_val += float(r.lost[d]) * dm.pi
    return {"episode": n, "J": traj.J_cents, "cause": dict(cause), "by_chk": dict(by_chk), "by_edge": dict(by_edge),
            "by_k": dict(by_k), "dispatched_ct": dispatched, "costs": dict(costs), "lost_units": dict(lost_units), "lost_val": lost_val}


def main(task, entropy, eps, agent, n_jobs="4"):
    from shockbench_flow.hosting.tasks import task_generator
    from shockbench_flow_agent.scoring import EpisodeSet
    from variants import pick_episodes
    inst, _ = task_generator(task)
    g, ga, ct = static_groups(inst)
    print(f"static: {len(g)} (commodity, later edge) groups shared by chip routes with >= 2 different first edges; "
          f"{len(ga)} later edges shared across any container commodity")
    E = inst.edges
    for (k, e), f in sorted(g.items()):
        print(f"  {inst.commodities[k].id:12s} {E[e].id:40s} u0={E[e].u0} firsts={len(f)}")
    entropy = int(entropy)
    picked = pick_episodes(task, entropy, eps, int(n_jobs))
    es = EpisodeSet.build(task, picked, entropy=entropy, n_jobs=int(n_jobs))
    ns = [int(r["episode"]) for r in es.references]
    out = Parallel(n_jobs=int(n_jobs))(delayed(episode)(n, (task, entropy, "standard"), agent) for n in ns)
    Path(f"outputs/task-35/meas_{task}_{entropy}_{eps.replace(':', '-').replace(',', '_')}_{Path(agent).name}.json"
         ).write_text(json.dumps(out, indent=1))
    tot = defaultdict(float)
    for o in out:
        for kk, v in o["cause"].items():
            tot[kk] += v / len(out)
    print(f"container cargo queued at chokepoints at end of week, unit-weeks per episode (mean over {len(out)}):")
    print("  " + "  ".join(f"{k} {v:,.0f}" for k, v in sorted(tot.items())))
    print(f"  dispatched container units per episode: {np.mean([o['dispatched_ct'] for o in out]):,.0f}")
    for key in ("by_chk", "by_edge", "by_k"):
        agg = defaultdict(float)
        for o in out:
            for kk, v in o[key].items():
                agg[kk] += v / len(out)
        print(f"  {key}: " + ", ".join(f"{k} {v:,.0f}" for k, v in sorted(agg.items(), key=lambda x: -x[1])[:10]))
    for o in out:
        print(f"  ep {o['episode']:3d} J {o['J']/1e14:.4f} T  queue {sum(o['cause'].values()):9,.0f} "
              f"edgefull {o['cause'].get('edgefull', 0):9,.0f}  qhold {o['costs']['queue_holding']/1e12:.4f} T  "
              f"lost sales {o['lost_val']/1e12:.3f} T  " + ", ".join(f"{k} {v:,.0f}" for k, v in o['lost_units'].items()))


if __name__ == "__main__":
    main(*sys.argv[1:])
