"""Task 32: power steering inside a grid. Replay an agent on Full episodes and measure, per multi-fab grid and week,
the split of the fabs' leftover power we get vs the split that maximises chip value (greedy by pi / e, each fab up to
alpha-bar R cap0 lots), plus fab lots, disposal and shed (before/after comparisons of two agents).

    uv run python outputs/task-32/probe32.py full 0 devpick:2,2,1,1 <agent folder> 3

Same world construction as task 28's probe (no naive fallback: check fallback_weeks == 0).
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
    from shockbench_flow_agent.scoring import _label, _metered_shim, _policy_seed
    from shockbench_flow.disruption.sampler import sample_omega
    from shockbench_flow.hosting.tasks import task_generator
    from shockbench_flow.marks import compute_marks
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime, reps, cache = spec
    t0 = time.perf_counter()
    inst, gparams = task_generator(task)
    omega = sample_omega(inst, gparams, entropy, n, _label(entropy))
    marks = compute_marks(inst, omega)
    pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
    shim = _metered_shim(load_agent_class(agent_root, f"submission_{Path(agent_root).name}_{n}"), None)
    traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=None)
    unload_agent()
    R = traj.records
    N, K = inst.nodes, inst.commodities
    sidx = inst.slot_index
    pi_of = {}
    for d in inst.demands:
        pi_of[d.k] = max(pi_of.get(d.k, 0.0), d.pi)
    raw_to_pk = {}
    for o in inst.osats:
        raw_to_pk.update(N[o].osat.packages)
    val = [pi_of[raw_to_pk[N[f].fab.product]] for f in inst.fabs]
    out = {"episode": n, "fallback_weeks": sum(took_fallback(r) for r in R), "J_agent_cents": traj.J_cents}
    fid = [N[f].id for f in inst.fabs]
    out["lots"] = {fid[fi]: float(sum(float(r.lots_started[fi]) for r in R)) for fi in range(len(fid))}
    out["fab_out_disposed"] = {fid[fi]: float(sum(float(r.disposal[sidx[(f, N[f].fab.product)]]) for r in R))
                               for fi, f in enumerate(inst.fabs)}
    out["fab_wafer_mean"] = {fid[fi]: float(np.mean([float(r.stock[sidx[(f, N[f].fab.input)]]) for r in R]))
                             for fi, f in enumerate(inst.fabs)}
    dk = defaultdict(float)
    for r in R:
        for s, sl in enumerate(inst.stock_slots):
            dk[K[sl.k].id] += float(r.disposal[s])
    out["disposal_units"] = dict(dk)
    lost = defaultdict(float)
    for r in R:
        for di, d in enumerate(inst.demands):
            lost[K[d.k].id] += float(r.lost[di])
    out["lost_units"] = dict(lost)
    out["shed_GWh"] = {N[g].id: float(sum(float(r.shed[gi]) for r in R)) for gi, g in enumerate(inst.grids)}

    grids = {}
    for gi, g in enumerate(inst.grids):
        members = [fi for fi in inst.grid_fabs[gi] if N[inst.fabs[fi]].fab.e > 0]
        if len(members) < 2:
            continue
        st = defaultdict(float)
        for ti, r in enumerate(R):
            full = sum(N[inst.fabs[fi]].fab.e * float(marks.alpha_bar[ti][fi]) * N[inst.fabs[fi]].fab.cap0
                       for fi in members if float(marks.R[ti][fi]) > 0)
            Etot = float(sum(r.energy[fi] for fi in members))
            phi = Etot / full if full > 0 else 0.0
            cls = "zero" if phi < 0.02 else ("full" if phi > 0.98 else "partial")
            st[f"weeks_{cls}"] += 1
            st[f"E_{cls}"] += Etot
            have = sum(float(r.lots_started[fi]) * val[fi] for fi in members)
            opts = []
            for fi in members:
                fab = N[inst.fabs[fi]].fab
                cap = float(marks.alpha_bar[ti][fi]) * float(marks.R[ti][fi]) * fab.cap0
                opts.append((val[fi] / fab.e, fab.e, cap, fi))
            opts.sort(reverse=True)
            best, left = 0.0, Etot
            for vpe, e, cap, fi in opts:
                use = min(left, e * cap)
                best += use * vpe
                left -= use
            st[f"gain_T_{cls}"] += max(0.0, best - have) / 1e12
            if cls == "partial":
                top = opts[0][3]
                st["partial_top_share_got"] += float(r.energy[top]) / Etot
                st["partial_top_share_best"] += min(Etot, opts[0][1] * opts[0][2]) / Etot
                # wafers on hand at the low-value fabs at the energy step vs their full-power need
                for vpe, e, cap, fi in opts[1:]:
                    st["partial_low_wafers_over_cap"] += float(r.lots_started[fi] + r.stock[sidx[(inst.fabs[fi], N[inst.fabs[fi]].fab.input)]]) / max(cap, 1.0)
                    st["partial_low_n"] += 1
        if st["weeks_partial"]:
            st["partial_top_share_got"] /= st["weeks_partial"]
            st["partial_top_share_best"] /= st["weeks_partial"]
        if st["partial_low_n"]:
            st["partial_low_wafers_over_cap"] /= st["partial_low_n"]
        grids[N[g].id] = dict(st)
    out["grids"] = grids
    out["seconds"] = round(time.perf_counter() - t0, 1)
    return out


def main(task, entropy, neps, agent, n_jobs, tag=None):
    from shockbench_flow_agent.scoring import EpisodeSet
    from variants import pick_episodes

    entropy, n_jobs = int(entropy), int(n_jobs)
    eps = pick_episodes(task, entropy, neps, n_jobs)
    es = EpisodeSet.build(task, eps, entropy=entropy, n_jobs=n_jobs)
    ns = [int(n) for n in es.episodes]
    root = str(Path(agent).resolve())
    rows = Parallel(n_jobs=n_jobs, verbose=5)(delayed(episode)(n, es._spec, root) for n in ns)
    for r, ref in zip(rows, es.references):
        r["stratum"] = ref["stratum"]
    tag = tag or Path(agent).name
    out = Path(f"outputs/task-32/probe_{task}_{entropy}_{neps.replace(':', '-').replace(',', '-')}_{tag}.json")
    out.write_text(json.dumps(rows, indent=1))
    print("written", out)
    print("RSS check:", es.rss([r["J_agent_cents"] for r in rows]))
    summarize(rows)


def summarize(rows):
    n = len(rows)
    print("fallback weeks", sum(r["fallback_weeks"] for r in rows))
    g = defaultdict(lambda: defaultdict(float))
    for r in rows:
        for gid, st in r["grids"].items():
            for k, v in st.items():
                g[gid][k] += v / n
    for gid, st in g.items():
        print(gid, {k: round(v, 4) for k, v in sorted(st.items())})
    for key in ("lots", "fab_out_disposed", "fab_wafer_mean", "disposal_units", "lost_units", "shed_GWh"):
        agg = defaultdict(float)
        for r in rows:
            for k, v in r[key].items():
                agg[k] += v / n
        print(key, {k: round(v) for k, v in agg.items()})


if __name__ == "__main__":
    main(*sys.argv[1:])
