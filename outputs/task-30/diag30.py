"""Task 30: what limits the JP / SEA / CN (and EU, KR, TW) grids, fuel by fuel, week by week.

Plays an agent on Full episodes (the scorer's world without the naive fallback, as task 28's probe) and books, per
grid, fuel and week, the segment's shortfall (share * G-bar - available) to a cause:
  ration   : the rationed fuel's grid stock was under psi * I-bar last week (output cut by I / thr)
  held     : fuel was sitting at the grid's terminal(s) at the start of the week (our own dispatch / pplan held it)
  queued   : fuel bound for this grid was waiting in a chokepoint queue
  srclost  : a source with a lane to this grid threw supply away at its cap this week (we could have shipped more)
  lane     : a lane to this grid ran at >= 95% of its tightest edge capacity this week
  other    : none of the above (source empty / lanes closed or banned / too late)
Shortfalls are booked to the first cause in that order that has room (up to its quantity). Also: fab energy short
(GWh) per grid and which fuel's shortfall covered it.

    uv run python outputs/task-30/diag30.py full 0 devpick:2,2,1,1 agents/mpc_imit_room 4
"""

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
GRIDS = ("grid_jp", "grid_sea", "grid_cn", "grid_eu", "grid_kr", "grid_tw")


def episode(n, spec, agent_root):
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _label, _metered_shim, _policy_seed
    from shockbench_flow.disruption.sampler import sample_omega
    from shockbench_flow.hosting.tasks import task_generator
    from shockbench_flow.marks import compute_marks
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime, reps, cache = spec
    inst, gparams = task_generator(task)
    omega = sample_omega(inst, gparams, entropy, n, _label(entropy))
    marks = compute_marks(inst, omega)
    pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
    shim = _metered_shim(load_agent_class(agent_root, f"submission_{Path(agent_root).stem}"), None)
    traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=None)
    unload_agent()
    R = traj.records
    N, K, E = inst.nodes, inst.commodities, inst.edges
    ids = [nd.id for nd in N]
    si = inst.slot_index
    psi = inst.params.psi
    lane_dest = {li: E[l.edges[-1]].head for li, l in enumerate(inst.lanes)}
    lane_id_to_i = {l.id: li for li, l in enumerate(inst.lanes)}
    out = {"episode": n, "J": traj.J_cents, "grids": {}}
    for gi, g in enumerate(inst.grids):
        if ids[g] not in GRIDS:
            continue
        grid = N[g].grid
        members = inst.grid_fabs[gi]
        res = {}
        for k in grid.fuels if hasattr(grid, "fuels") else [k for k in grid.shares if k is not None]:
            kid = K[k].id
            terms = [E[e].tail for e in range(len(E)) if E[e].head == g and k in (E[e].K or ())
                     and N[E[e].tail].kind == "terminal"] if False else \
                [E[e].tail for e in range(len(E)) if E[e].head == g and k in (E[e].K or ())
                 and getattr(N[E[e].tail], "type", getattr(N[E[e].tail], "kind", "")) == "terminal"]
            dests = {g, *terms}
            lanes = [li for li, l in enumerate(inst.lanes) if lane_dest[li] in dests and k in (inst.lane_K[li] or ())]
            srcs = {E[inst.lanes[li].edges[0]].tail for li in lanes}
            src_slots = [si[(s, k)] for s in srcs if (s, k) in si]
            rows = []
            for t, r in enumerate(R):
                G = float(marks.G_bar[t][gi])
                s = si[(g, k)]
                Iprev = float(R[t - 1].stock[s]) if t > 0 else np.nan
                burn = float(r.segment.get((gi, k), 0.0))
                pre = float(r.stock[s]) + burn + float(r.disposal[s])
                cap = grid.shares[k] * G
                ration = 1.0
                if k == grid.rationed and t > 0:
                    thr = psi * grid.ibar[k]
                    ration = 1.0 if Iprev >= thr else Iprev / thr
                av = min(cap * ration, pre)
                short = max(cap - av, 0.0)
                held = sum(float(R[t - 1].stock[si[(tm, k)]]) for tm in terms if (tm, k) in si) if t > 0 else 0.0
                queued = 0.0
                for (c, kk, lane), q in r.queue.items():
                    li = lane if isinstance(lane, (int, np.integer)) else lane_id_to_i.get(lane)
                    if kk == k and li is not None and lane_dest.get(li) in dests:
                        queued += float(q)
                srclost = sum(max(float(marks.supply[t][ss]) - float(r.lift[ss]), 0.0) for ss in src_slots)
                lane_full = 0.0
                ship = defaultdict(float)
                for (e, kk, lane), q in r.x.items():
                    if kk == k and lane is not None and lane in lanes:
                        ship[lane] += float(q)
                for li in lanes:
                    ucap = min(float(marks.u[t][e]) for e in inst.lanes[li].edges)
                    if ucap > 1 and ship[li] >= 0.95 * ucap:
                        lane_full += ship[li]
                rows.append({"t": t, "cap": cap, "ration": ration, "pre": pre, "av": av, "short": short,
                             "held": held, "queued": queued, "srclost": srclost, "lanefull": lane_full,
                             "ship": float(sum(ship.values()))})
            res[kid] = rows
        fabE = [float(sum(r.energy[fi] for fi in members)) for r in R]
        fab_need = [float(sum(N[inst.fabs[fi]].fab.e * N[inst.fabs[fi]].fab.cap0 for fi in members))
                    if hasattr(N[inst.fabs[members[0]]].fab, "cap0") else np.nan for _ in R] if members else []
        out["grids"][ids[g]] = {"fuels": res, "fabE": fabE, "shed": [float(r.shed[gi]) for r in R],
                                "ybar": [float(marks.y_bar[t][gi]) for t in range(len(R))],
                                "G": [float(marks.G_bar[t][gi]) for t in range(len(R))],
                                "lots": [float(sum(r.lots_started[fi] for fi in members)) for r in R]}
    return out


def book(rows, ration_k):
    tot = defaultdict(float)
    for w in rows:
        sh = w["short"]
        if sh <= 1e-6:
            continue
        tot["short"] += sh
        if w["ration"] < 1.0 - 1e-9:
            tot["ration"] += sh
            continue
        for key in ("held", "queued", "srclost", "lanefull"):
            take = min(sh, w[key])
            tot[key] += take
            sh -= take
            if sh <= 1e-9:
                break
        tot["other"] += max(sh, 0.0)
    return tot


def main(task, entropy, eps, agent, n_jobs):
    from shockbench_flow_agent.scoring import EpisodeSet
    from variants import pick_episodes

    entropy, n_jobs = int(entropy), int(n_jobs)
    sel = pick_episodes(task, entropy, eps, n_jobs)
    es = EpisodeSet.build(task, sel, entropy=entropy, n_jobs=n_jobs)
    ns = [int(n) for n in es.episodes]
    root = str(Path(agent).resolve())
    t0 = time.time()
    rows = Parallel(n_jobs=n_jobs)(delayed(episode)(n, es._spec, root) for n in ns)
    print(f"played {len(ns)} in {time.time() - t0:.0f} s; RSS {es.rss([r['J'] for r in rows])}")
    tag = f"{task}_{entropy}_{eps.replace(':', '-').replace(',', '_')}_{Path(agent).name}"
    Path(f"outputs/task-30/diag_{tag}.json").write_text(json.dumps(rows))
    report(rows)


def report(rows):
    ne = len(rows)
    print("\nshortfall per segment, GWh per episode (mean), booked to causes in order ration > held > queued > "
          "srclost > lanefull > other")
    print(f"{'grid':9s} {'fuel':8s} {'weeks':>5s} {'short':>8s} {'ration':>8s} {'held':>8s} {'queued':>8s} "
          f"{'srclost':>8s} {'lanefull':>8s} {'other':>8s} | {'ship/wk':>8s} {'need/wk':>8s}")
    for gid in GRIDS:
        if gid not in rows[0]["grids"]:
            continue
        for kid in rows[0]["grids"][gid]["fuels"]:
            agg = defaultdict(float)
            wk = ship = need = 0.0
            for r in rows:
                w = r["grids"][gid]["fuels"][kid]
                for kk, v in book(w, None).items():
                    agg[kk] += v / ne
                wk += sum(x["short"] > 1e-6 for x in w) / ne
                ship += np.mean([x["ship"] for x in w]) / ne
                need += np.mean([x["cap"] for x in w]) / ne
            print(f"{gid:9s} {kid:8s} {wk:5.1f} {agg['short']:8.0f} {agg['ration']:8.0f} {agg['held']:8.0f} "
                  f"{agg['queued']:8.0f} {agg['srclost']:8.0f} {agg['lanefull']:8.0f} {agg['other']:8.0f} | "
                  f"{ship:8.0f} {need:8.0f}")
    print("\nfab weeks: per grid, weeks with fabs < 50% of the best week's energy, and which fuel was short then")
    for gid in GRIDS:
        if gid not in rows[0]["grids"]:
            continue
        cnt = defaultdict(float)
        dark = 0.0
        for r in rows:
            gg = r["grids"][gid]
            fe = np.array(gg["fabE"])
            top = max(fe.max(), 1e-9)
            for t in range(len(fe)):
                if fe[t] < 0.5 * top:
                    dark += 1 / ne
                    shorts = [kid for kid, w in gg["fuels"].items() if w[t]["short"] > 0.02 * (gg["G"][t] - gg["ybar"][t])]
                    for kid in shorts:
                        cand = gg["fuels"][kid][t]
                        why = "ration" if cand["ration"] < 1 - 1e-9 else "onhand"
                        cnt[f"{kid}:{why}"] += 1 / ne
                    if not shorts:
                        cnt["none(G-bar cut?)"] += 1 / ne
        print(f"  {gid:9s} dark weeks {dark:5.1f}/104  " + "  ".join(f"{k} {v:.1f}" for k, v in sorted(cnt.items())))


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report(json.loads(Path(sys.argv[2]).read_text()))
    else:
        main(*sys.argv[1:])
