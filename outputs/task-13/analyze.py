"""Task 13: how much of the lost chip sales could chips already in the system have covered?

    uv run python outputs/task-13/analyze.py outputs/task-13/raw_full_0_devpick-2211_mpc_pulse.pkl

Per episode (USD unless noted):
  lost        lost sales pi*U by product (and by sink)
  disposed    chips (raw/packaged) thrown away above storage, by node type, valued at the product's pi
  end_stock   chips left at the end (fab raw, OSAT raw+packaged, sink, shipments from OSATs still under way)
  sink_mis    weeks a sink of product k held stock above its demand while another sink of k lost sales: min(excess, lost)
  osat_mix    weeks an OSAT's throughput bound and it packaged mature chips while leading-edge raw chips waited there
              and leading-edge sales were lost: (pi_le - pi_mat) * min(mature packaged, le raw left, le lost)
  ceiling     time-aware upper bound: chips never sold (end stock + disposal) assigned greedily to the earliest lost
              sales of their product in weeks they (as stock of that product anywhere) could have existed; lead times
              ignored, so this over-counts
"""

import pickle
import sys
from collections import defaultdict

import numpy as np


def main(path):
    from shockbench_flow.hosting.tasks import task_generator

    inst, _ = task_generator("full")
    C = inst.commodities
    cid = {c.id: k for k, c in enumerate(C)}
    le_raw, mat_raw, le, mat = cid["chip_le_raw"], cid["chip_mat_raw"], cid["chip_le"], cid["chip_mat"]
    pk_of = {le_raw: le, mat_raw: mat, le: le, mat: mat}
    pi = {k: np.mean([d.pi for d in inst.demands if d.k == k]) for k in (le, mat)}
    ntype = [n.type for n in inst.nodes]
    slots = inst.stock_slots
    chip_slots = [s for s, st in enumerate(slots) if st.k in pk_of and ntype[st.node] in ("fab", "osat", "sink")]
    osat_ord = {o: i for i, o in enumerate(inst.osats)}
    rows = pickle.loads(open(path, "rb").read())
    agg = defaultdict(list)
    for r in rows:
        T = r["lost"].shape[0]
        lost_k = {k: np.zeros(T) for k in (le, mat)}
        lost_usd = 0.0
        by_sink = defaultdict(float)
        for di, d in enumerate(inst.demands):
            lost_k[d.k] += r["lost"][:, di]
            lost_usd += float((r["lost"][:, di] * d.pi).sum())
            by_sink[(inst.nodes[d.node].id, C[d.k].id)] += float((r["lost"][:, di] * d.pi).sum())
        demand_usd = sum(float((r["demand"][:, di] * d.pi).sum()) for di, d in enumerate(inst.demands))
        # disposal and stock of chips
        disp = defaultdict(float)
        disp_k = {k: np.zeros(T) for k in (le, mat)}
        stock_k = {k: np.zeros(T) for k in (le, mat)}
        end = defaultdict(float)
        for s in chip_slots:
            st = slots[s]
            k = pk_of[st.k]
            disp[(ntype[st.node], C[st.k].id)] += float(r["disposal"][:, s].sum()) * pi[k]
            disp_k[k] += r["disposal"][:, s]
            stock_k[k] += r["stock"][:, s]
            end[(ntype[st.node], C[st.k].id)] += float(r["stock"][-1, s])
        # shipments from OSATs still under way at the end
        transit = {le: 0.0, mat: 0.0}
        for t, xs in enumerate(r["x"]):
            for (e, k, lane), v in xs.items():
                E = inst.edges[e]
                if ntype[E.tail] == "osat" and k in (le, mat) and t + 1 + E.tau > T:
                    transit[k] += v
        end_units = {k: sum(v for (ty, kk), v in end.items() if pk_of[cid[kk]] == k) + transit[k] for k in (le, mat)}
        # sink misallocation
        mis = 0.0
        for k in (le, mat):
            rows_k = [di for di, d in enumerate(inst.demands) if d.k == k]
            for t in range(T):
                lost_t = sum(r["lost"][t, di] for di in rows_k)
                excess = sum(max(0.0, r["stock"][t, inst.slot_index[(inst.demands[di].node, k)]]
                                 - (r["demand"][t + 1, di] if t + 1 < T else 0.0)) for di in rows_k)
                mis += min(excess, lost_t) * pi[k]
        # OSAT mix: throughput bound with both raw types
        mix = 0.0
        for t in range(T):
            if lost_k[le][t] <= 0:
                continue
            for o in inst.osats:
                oi = osat_ord[o]
                q_mat = r["packaged"][t].get((oi, mat), 0.0)
                s_le = inst.slot_index.get((o, le_raw))
                if s_le is None or q_mat <= 0:
                    continue
                le_left = r["stock"][t, s_le]  # raw le left after packaging this week
                mix += min(q_mat, le_left, lost_k[le][t]) * (pi[le] - pi[mat])
        # time-aware ceiling
        ceil = 0.0
        for k in (le, mat):
            U = end_units[k] + disp_k[k].sum()
            for t in range(T):
                c = min(lost_k[k][t], stock_k[k][t] + disp_k[k][t], U)
                U -= c
                ceil += c * pi[k]
        agg["lost"].append(lost_usd)
        agg["demand"].append(demand_usd)
        agg["disp"].append(sum(disp.values()))
        agg["end_usd"].append(sum(end_units[k] * pi[k] for k in (le, mat)))
        agg["sink_mis"].append(mis)
        agg["osat_mix"].append(mix)
        agg["ceiling"].append(ceil)
        agg["gap"].append((r["J_agent_cents"] - r["J_oracle_cents"]) / 100)
        print(f"\nepisode {r['episode']} (level {r['stratum']}): gap to oracle {agg['gap'][-1]:.3e}, "
              f"lost sales {lost_usd:.3e} of demand {demand_usd:.3e} ({lost_usd / demand_usd:.1%})")
        print("  lost by product:", {C[k].id: f"{lost_k[k].sum():.4g} u, {lost_k[k].sum() * pi[k]:.3e} USD" for k in (le, mat)})
        print("  lost by sink   :", {f"{a}/{b}": f"{v:.2e}" for (a, b), v in sorted(by_sink.items()) if v > 0})
        print("  disposed chips :", {f"{a}/{b}": f"{v:.2e}" for (a, b), v in disp.items() if v > 0} or 0)
        print("  end stock units:", {f"{a}/{b}": round(v) for (a, b), v in end.items() if v > 0.5},
              "in transit", {C[k].id: round(v) for k, v in transit.items()})
        print(f"  end stock USD {agg['end_usd'][-1]:.3e}; sink misallocation {mis:.3e}; OSAT mix {mix:.3e}; "
              f"ceiling {ceil:.3e}")
    print("\nMEAN over", len(rows), "episodes (USD/episode):")
    for key in ("gap", "demand", "lost", "disp", "end_usd", "sink_mis", "osat_mix", "ceiling"):
        print(f"  {key:9s} {np.mean(agg[key]):.4e}")
    print(f"  ceiling total (ceiling + sink_mis + osat_mix, overlapping, upper bound) "
          f"{np.mean(agg['ceiling']) + np.mean(agg['sink_mis']) + np.mean(agg['osat_mix']):.4e}")


if __name__ == "__main__":
    main(*sys.argv[1:])
