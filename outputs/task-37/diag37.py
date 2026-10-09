"""Task 37: chips made and thrown away. Plays an agent (the scorer's world, seed and fallback, as task 19's diag19.py)
and records, per week:
  - per chip/wafer stock slot: real disposal, real end stock, class of the disposal week (blocked / full / unused out-
    edges, as task 20's disp20.py) and whether a sink of that product lost sales that week;
  - the chip LP's own plan of that week (needs chips.py's ``self.last``, task 37): planned disposal at t=0 and over the
    window, planned end stock at t=0, planned fab starts at t=0 and the LP's fab capacity;
  - per fab: lots started, wafers on hand before the start, energy.

    uv run python outputs/task-37/diag37.py full 0 devpick:2,2,1,1 agents/mpc_nodisp 4 [tag] [params_json]
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
    from shockbench_flow.dynamics.env import rollout, took_fallback
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _metered_shim, _policy_seed, _world
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime, reps, cache = spec
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
    cls = load_agent_class(agent_root, f"submission_{Path(agent_root).stem}")
    mod = sys.modules.get(cls.__module__)
    CP = mod._chips.ChipPlanner
    plans = {}
    planners = []
    orig = CP.plan

    def plan(self, obs):
        self.last = None
        out = orig(self, obs)
        if self.last is not None:
            plans[int(self.last["week"])] = self.last
        if not planners:
            planners.append(self)
        return out

    CP.plan = plan
    shim = _metered_shim(cls, None)
    traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=fallback)
    CP.plan = orig
    unload_agent()
    R = traj.records
    N, K, E = inst.nodes, inst.commodities, inst.edges
    u = np.asarray(marks.u)
    Z = np.asarray(marks.prohibited)
    pl = planners[0]
    slot_of = {(sl.node, sl.k): s for s, sl in enumerate(inst.stock_slots)}
    pack_of = {}
    for o in inst.osats:
        pack_of.update(N[o].osat.packages)
    pi = defaultdict(float)
    for d in inst.demands:
        pi[d.k] = max(pi[d.k], d.pi)
    weeks = sorted(plans)
    T = len(R)
    out = {"episode": n, "J": traj.J_cents, "fallback_weeks": sum(took_fallback(r) for r in R), "slots": {},
           "fabs": {}}
    for i, p in enumerate(pl.pos):
        s = slot_of[(p["node"], p["k"])]
        kid = K[p["k"]].id
        if not (kid.startswith("chip") or kid.startswith("wafer")):
            continue
        kp = p["k"] if p["k"] in pi else pack_of.get(p["k"])
        sinks_k = [j for j, d in enumerate(inst.demands) if d.k == kp]
        oute = [e for e, ed in enumerate(E) if ed.tail == p["node"] and p["k"] in ed.K]
        disp = np.array([float(r.disposal[s]) for r in R])
        stock = np.array([float(r.stock[s]) for r in R])
        cls_w, lost_w, outx, capw = [], [], [], []
        for t, r in enumerate(R):
            capt = sum(u[t, e] for e in oute if not Z[t, e, p["k"]])
            ex = sum(v for (e, k, _l), v in r.x.items() if e in oute and k == p["k"])
            outx.append(ex)
            capw.append(capt)
            cls_w.append("blocked" if capt <= 1e-9 else ("full" if ex >= 0.95 * capt else "unused"))
            lost_w.append(sum(r.lost[j] for j in sinks_k))
        pd0, pdw, pI0 = np.zeros(T), np.zeros(T), np.full(T, np.nan)
        for w in weeks:
            L = plans[w]
            H = L["H"]
            xs = L["x"]
            pd0[w - 1] = xs[L["off_d"] + i * H]
            pdw[w - 1] = xs[L["off_d"] + i * H: L["off_d"] + i * H + H].sum()
            pI0[w - 1] = xs[L["off_I"] + i * H]
        if disp.sum() <= 0 and p["kind"] != "fab":
            continue
        out["slots"][f"{N[p['node']].id}/{kid}"] = {
            "kind": p["kind"], "cap": p["cap"], "disp": disp.tolist(), "stock": stock.tolist(), "cls": cls_w,
            "lost": lost_w, "outx": outx, "outcap": capw, "plan_d0": pd0.tolist(), "plan_dwin": pdw.tolist(),
            "plan_I0": pI0.tolist(), "pi": pi.get(kp, 0.0)}
    for fi, f in enumerate(pl.fabs):
        node = f["node"]
        fidx = list(inst.fabs).index(node)
        s_in = slot_of[(node, N[node].fab.input)]
        lots = np.array([float(r.lots_started[fidx]) for r in R])
        held = [float(R[t - 1].stock[s_in]) if t > 0 else np.nan for t in range(T)]
        ps0, cap0 = np.full(T, np.nan), np.full(T, np.nan)
        for w in weeks:
            L = plans[w]
            H = L["H"]
            ps0[w - 1] = L["x"][L["off_f"] + fi * H]
            cap0[w - 1] = L["hi_f"][fi * H]
        out["fabs"][N[node].id] = {"lots": lots.tolist(), "held_prev": held, "energy": [float(r.energy[fidx]) for r in R],
                                   "plan_s0": ps0.tolist(), "plan_cap0": cap0.tolist(), "cap0": float(N[node].fab.cap0),
                                   "product": K[N[node].fab.product].id}
    # route-level class of every disposal week (packaged chips: routes to a sink of k; raw chips: routes to an OSAT
    # that packages k): "route" = some route had every edge < 95% used that week and (packaged) its sink lost sales
    # in the arrival week; else "routes_full"
    flow = np.zeros((T, len(E)))
    for t, r in enumerate(R):
        for (e, k, _l), v in r.x.items():
            flow[t, e] += v
    routes = defaultdict(list)  # (node, k) -> [(edges, head)]
    for l in inst.lanes:
        routes[E[l.edges[0]].tail].append((list(l.edges), E[l.edges[-1]].head))
    for e, ed in enumerate(E):
        routes[ed.tail].append(([e], ed.head))
    dem_at = defaultdict(list)
    for j, d in enumerate(inst.demands):
        dem_at[(d.node, d.k)].append(j)
    osat_pk = {o: N[o].osat.packages for o in inst.osats}
    for key, sd in out["slots"].items():
        node = next(i for i, nd in enumerate(N) if nd.id == key.split("/")[0])
        k = next(i for i, c in enumerate(K) if c.id == key.split("/")[1])
        rc, why = [], []
        for t in range(T):
            if sd["disp"][t] <= 0:
                rc.append(None); why.append(None); continue
            ok, best = False, None
            for edges, head in routes[node]:
                if any(k not in E[e].K for e in edges):
                    continue
                if any(Z[t, e, k] for e in edges):
                    continue
                spare = min(u[t, e] - flow[t, e] for e in edges)
                if spare < 0.05 * min(u[t, e] for e in edges):
                    continue
                lead = sum(int(E[e].tau) for e in edges)
                if head in osat_pk and K[k].id in osat_pk[head]:
                    ok = True; best = N[head].id
                elif (head, k) in dem_at:
                    ta = min(T - 1, t + lead)
                    if t + lead < T and any(R[ta].lost[j] > 1e-6 for j in dem_at[(head, k)]):
                        ok = True; best = N[head].id
            rc.append("route" if ok else "routes_full"); why.append(best)
        sd["rcls"] = rc; sd["rwhere"] = why
    out["lost_by_k"] = {}
    for j, d in enumerate(inst.demands):
        key = f"{N[d.node].id}/{K[d.k].id}"
        out["lost_by_k"][key] = [float(sum(r.lost[j] for r in R)), float(d.pi)]
    out["costs"] = {c: float(sum(getattr(r.costs, c) for r in R)) for c in ("shortage", "disposal", "shed", "holding")}
    return out


def main(task, entropy, neps, agent, n_jobs, tag=None, params=None):
    import shutil
    import tempfile
    from shockbench_flow_agent.scoring import EpisodeSet
    from variants import pick_episodes

    entropy, n_jobs = int(entropy), int(n_jobs)
    eps = pick_episodes(task, entropy, neps, n_jobs)
    es = EpisodeSet.build(task, eps, entropy=entropy, n_jobs=n_jobs)
    ns = [int(n) for n in es.episodes]
    root = Path(agent).resolve()
    tag = tag or root.name
    if params:
        tmp = Path(tempfile.mkdtemp()) / root.name
        shutil.copytree(root, tmp, ignore=shutil.ignore_patterns("__pycache__"))
        (tmp / "params.json").write_text(Path(params).read_text() if Path(params).is_file() else params)
        root = tmp
    t = time.time()
    rows = Parallel(n_jobs=n_jobs, verbose=5)(delayed(episode)(n, es._spec, str(root)) for n in ns)
    for r, ref in zip(rows, es.references):
        r["stratum"] = ref["stratum"]
    outp = Path(f"outputs/task-37/diag37_{task}_{entropy}_{neps.replace(':', '-').replace(',', '-')}_{tag}.json")
    outp.write_text(json.dumps(rows))
    print(f"played in {time.time() - t:.0f} s, written {outp}")
    print("RSS:", es.rss([r["J"] for r in rows]))
    print("fallback weeks", sum(r["fallback_weeks"] for r in rows))


if __name__ == "__main__":
    main(*sys.argv[1:])
