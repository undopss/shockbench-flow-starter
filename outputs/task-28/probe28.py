"""Task 28 ("rule lawyer"): replay an agent on Full episodes and measure, per simulator mechanic, how much is at stake.

    uv run python outputs/task-28/probe28.py full 0 devpick:2,2,1,1 agents/mpc_fab3sell 4

Plays exactly as gap17.py / cost_breakdown.py (same worlds, seeds, fallback). No oracle solve: oracle components come
from task 20's dev-20 JSON. Per episode it records (T USD unless said otherwise):
  scrap (14): wafers scrapped by fab hits, valued at the product's pi (upper bound: every scrapped lot would have sold)
  osat (19): raw chip_le displaced by pro-rata packaging in weeks the OSAT throughput binds (vs chip_le first)
  energy (15)-(18): per grid and fuel segment, GWh lost to rationing (gas, I^{t-1} < psi I-bar) and to empty stock
                    (any fuel: share G-bar > fuel on hand), and shed / fab-energy shortfall in those weeks
  alpha (13): headroom alpha-bar R cap0 - R cap0 and lots started above R cap0
  supply lift: availability lost at the cap per supply node (wafers, fuel)
  terminal: salvage credit, its maximum (every slot at I^max), chips and fuel left at T
  disposal: by commodity
  chokepoints: tanker fuel queued (GWh-weeks) by chokepoint, and while the chokepoint is (partly) closed
  sinks: chip stock idle at one sink while another sink of the same product loses sales
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
    from shockbench_flow.marks import osat_throughput
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _label, _metered_shim, _policy_seed
    from shockbench_flow.disruption.sampler import sample_omega
    from shockbench_flow.hosting.tasks import task_generator
    from shockbench_flow.marks import compute_marks
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime, reps, cache = spec
    t0 = time.perf_counter()
    # the scorer's world without the naive fallback (its F_Q takes ~1 h to build here); a failed week would play the
    # empty action instead of naive, so check fallback_weeks == 0 (mpc_fab3sell has none on Full dev)
    inst, gparams = task_generator(task)
    omega = sample_omega(inst, gparams, entropy, n, _label(entropy))
    marks, fallback = compute_marks(inst, omega), None
    pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
    shim = _metered_shim(load_agent_class(agent_root, f"submission_{Path(agent_root).stem}"), None)
    traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=fallback)
    unload_agent()
    R = traj.records
    T = len(R)
    N, K = inst.nodes, inst.commodities
    sidx = inst.slot_index
    pi_of = {}
    for d in inst.demands:
        pi_of[d.k] = max(pi_of.get(d.k, 0.0), d.pi)
    raw_to_pk = {}
    for o in inst.osats:
        raw_to_pk.update(N[o].osat.packages)
    out = {"episode": n, "fallback_weeks": sum(took_fallback(r) for r in R), "J_agent_cents": traj.J_cents}

    # ---- scrap (14)
    scr = np.sum([r.scrapped for r in R], axis=0)
    val = [pi_of[raw_to_pk[N[f].fab.product]] for f in inst.fabs]
    out["scrap_units"] = float(scr.sum())
    out["scrap_T"] = float(np.dot(scr, val)) / 1e12
    out["fab_hits"] = [(N[inst.fabs[h.fab]].id, float(h.onset), float(h.severity)) for h in marks.fab_hits]

    # ---- OSAT pro rata (19)
    disp_le_bind, displaced, bind_weeks = 0.0, 0.0, 0
    le_raw = [k for k in range(len(K)) if K[k].id == "chip_le_raw"][0]
    for ti, r in enumerate(R):
        cap = osat_throughput(inst, marks.R_osat[ti])
        for oi, o in enumerate(inst.osats):
            pk = N[o].osat.packages
            if len(pk) < 2:
                continue
            xi = {raw: r.packaged.get((oi, p), 0.0) for raw, p in pk.items()}
            if sum(xi.values()) < 0.999 * cap[oi]:
                continue
            bind_weeks += 1
            s = sidx[(o, le_raw)]
            r_le = xi[le_raw] + float(r.stock[s]) + float(r.disposal[s])
            displaced += min(cap[oi], r_le) - xi[le_raw]
            disp_le_bind += float(r.disposal[s])
    out["osat_bind_weeks"] = bind_weeks
    out["osat_le_displaced_units"] = displaced
    out["osat_le_disposed_in_bind_weeks"] = disp_le_bind

    # ---- energy (15)-(18)
    psi = inst.params.psi
    en = {}
    for gi, g in enumerate(inst.grids):
        grid = N[g].grid
        rows = defaultdict(float)
        for ti, r in enumerate(R):
            Gb = float(marks.G_bar[ti][gi])
            shed = float(r.shed[gi])
            members = inst.grid_fabs[gi]
            ehat_full = sum(N[inst.fabs[fi]].fab.e * float(marks.R[ti][fi]) * float(marks.alpha_bar[ti][fi])
                            * N[inst.fabs[fi]].fab.cap0 / max(float(marks.R[ti][fi]), 1e-12)
                            for fi in members if float(marks.R[ti][fi]) > 0)
            fab_short = max(0.0, ehat_full - float(sum(r.energy[fi] for fi in members)))
            for k in grid.fuels:
                s = sidx[(g, k)]
                burn = float(r.segment.get((gi, k), 0.0))
                I_prod = float(r.stock[s]) + burn + float(r.disposal[s])  # fuel on hand at the energy step
                cap_k = grid.shares[k] * Gb
                if k == grid.rationed:
                    prev = float(R[ti - 1].stock[s]) if ti > 0 else None
                    if prev is None:
                        from shockbench_flow.dynamics.sim import initial_stock
                        prev = float(initial_stock(inst)[s])
                    thr = psi * grid.ibar[k]
                    ration = 1.0 if prev >= thr else prev / thr
                    rows[f"{K[k].id}_ration_GWh"] += cap_k * (1 - ration)
                    rows[f"{K[k].id}_ration_GWh_when_shed"] += cap_k * (1 - ration) if shed > 1e-6 else 0.0
                    cap_k *= ration
                lack = max(0.0, cap_k - I_prod)
                rows[f"{K[k].id}_stockout_GWh"] += lack
                rows[f"{K[k].id}_stockout_weeks"] += lack > 1e-6
                rows[f"{K[k].id}_stockout_GWh_when_shed"] += lack if shed > 1e-6 else 0.0
                rows[f"{K[k].id}_end_stock"] = float(r.stock[s])
            rows["shed_GWh"] += shed
            rows["shed_weeks"] += shed > 1e-6
            rows["fab_energy_short_GWh"] += fab_short
        rows["shed_T"] = rows["shed_GWh"] * grid.voll / 1e12
        en[N[g].id] = dict(rows)
    out["energy"] = en

    # ---- alpha-bar (13)
    head, above = 0.0, 0.0
    for ti, r in enumerate(R):
        for fi, f in enumerate(inst.fabs):
            base = float(marks.R[ti][fi]) * N[f].fab.cap0
            head += (float(marks.alpha_bar[ti][fi]) - 1.0) * base
            above += max(0.0, float(r.lots_started[fi]) - base)
    out["alpha_headroom_lots"] = head
    out["alpha_lots_above_Rcap"] = above

    # ---- power steering inside a grid (sim.py:349-354, production.py:200): leftover power is split pro rata to
    # e p-hat / R, so the wafers on hand decide who gets it. Bound: each grid-week, re-split the fab energy the grid
    # actually gave its fabs, greedily by chip value per GWh (pi / e), each fab up to alpha-bar R cap0 lots (as if the
    # agent had steered wafers perfectly), vs what the agent's split made. Gross: every extra lot valued at its pi.
    steer, fab_val = 0.0, 0.0
    steer_g = defaultdict(float)
    steer_wk = defaultdict(float)  # grid-weeks where the agent's split left value on the table
    for ti, r in enumerate(R):
        for gi, g in enumerate(inst.grids):
            members = inst.grid_fabs[gi]
            if len(members) < 2:
                continue
            Etot = float(sum(r.energy[fi] for fi in members))
            if Etot <= 1e-9:
                continue
            have = sum(float(r.lots_started[fi]) * val[fi] for fi in members)
            opts = []
            for fi in members:
                fab = N[inst.fabs[fi]].fab
                if fab.e <= 0:
                    continue
                cap = float(marks.alpha_bar[ti][fi]) * float(marks.R[ti][fi]) * fab.cap0
                opts.append((val[fi] / fab.e, fab.e, cap, fi))
            best, left = 0.0, Etot
            for vpe, e, cap, fi in sorted(opts, reverse=True):
                use = min(left, e * cap)
                best += use * vpe
                left -= use
            steer += max(0.0, best - have)
            steer_g[N[g].id] += max(0.0, best - have) / 1e12
            steer_wk[N[g].id] += best - have > 1e-3 * max(best, 1.0)
            fab_val += have
    out["steer_gain_T"] = steer / 1e12
    out["fab_lot_value_T"] = fab_val / 1e12
    out["steer_gain_by_grid_T"] = dict(steer_g)
    out["steer_weeks_by_grid"] = dict(steer_wk)

    # ---- supply lift
    lostsup = defaultdict(float)
    for ti, r in enumerate(R):
        for s, sl in enumerate(inst.stock_slots):
            if sl.node in inst.supply_nodes:
                lostsup[K[sl.k].id] += float(marks.supply[ti][s]) - float(r.lift[s])
    out["supply_lost_at_cap"] = dict(lostsup)

    # ---- terminal
    supply = set(inst.supply_nodes)
    smax = sum((sl.storage or 0.0) * sl.salvage for sl in inst.stock_slots if sl.node not in supply)
    out["salvage_T"] = float(traj.salvage or 0.0) / 1e12
    out["salvage_max_stock_T"] = smax / 1e12
    endk = defaultdict(float)
    for s, sl in enumerate(inst.stock_slots):
        endk[K[sl.k].id] += float(R[-1].stock[s])
    out["end_stock"] = dict(endk)

    # ---- disposal by commodity and cost
    dk = defaultdict(float)
    for r in R:
        for s, sl in enumerate(inst.stock_slots):
            dk[K[sl.k].id] += float(r.disposal[s])
    out["disposal_units"] = dict(dk)

    # ---- chokepoint queues (tanker fuel)
    qk = defaultdict(float)
    for ti, r in enumerate(R):
        for (c, k, _l), q in r.queue.items():
            ci = inst.chokepoint_ordinal[c]
            closed = float(marks.o[ti][ci]) < 0.999
            tag = f"{N[c].id}/{K[k].id}" + ("/closed" if closed else "")
            qk[tag] += q
    out["queue_unit_weeks"] = dict(qk)

    # ---- idle stock at one sink while another sink of the same product loses sales
    idle = defaultdict(float)
    by_k = defaultdict(list)
    for di, d in enumerate(inst.demands):
        by_k[d.k].append(di)
    for r in R:
        for k, ds in by_k.items():
            lost = sum(float(r.lost[di]) for di in ds)
            stock = sum(float(r.stock[sidx[(inst.demands[di].node, k)]]) for di in ds if float(r.lost[di]) < 1e-6)
            idle[K[k].id] += min(lost, stock)
    out["sink_idle_vs_lost_units"] = dict(idle)
    lost_tot = defaultdict(float)
    for r in R:
        for di, d in enumerate(inst.demands):
            lost_tot[K[d.k].id] += float(r.lost[di])
    out["lost_units"] = dict(lost_tot)
    # lost sales in weeks where the same sink had stock left over at the end of the previous week = 0 by construction;
    # demand noise: lost units in weeks where the sink's stock at the start of the week covered the median demand
    out["seconds"] = round(time.perf_counter() - t0, 1)
    return out


def main(task, entropy, neps, agent, n_jobs):
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
    out = Path(f"outputs/task-28/probe_{task}_{entropy}_{neps.replace(':', '-').replace(',', '-')}_{Path(agent).name}.json")
    out.write_text(json.dumps(rows, indent=1))
    print("written", out)
    print("RSS check:", es.rss([r["J_agent_cents"] for r in rows]))


if __name__ == "__main__":
    main(*sys.argv[1:])
