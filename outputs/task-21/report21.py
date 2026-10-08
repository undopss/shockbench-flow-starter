"""Task 21 tables: the agent's chip decisions vs the clairvoyant LP's, from diag21.py's play_<tag>.json and bound_<tag>.json.

    uv run python outputs/task-21/report21.py <tag>
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def T(x):
    return x / 1e12


def main(tag="nolim"):
    rows = json.loads((HERE / f"play_{tag}.json").read_text())
    bpath = HERE / f"bound_{tag}.json"
    bnd = json.loads(bpath.read_text()) if bpath.is_file() else {}
    r0 = rows[0]
    fabs, dem, grids = r0["fabs"], r0["demands"], r0["grids"]
    pi = np.array([d["pi"] for d in dem])
    ne = len(rows)

    print("## 1. Shortage (lost sales) per episode, T USD: agent vs oracle LPs on the agent's trajectory")
    print("   capped = oracle with each fab's weekly starts <= the agent's (routing ceiling)")
    print("   avail  = oracle with each grid's weekly fab energy <= what the agent's grid had left after homes (G_av - y)")
    print("   free   = the clairvoyant plan")
    print(f"{'ep':>4} {'agent':>7} {'capped':>7} {'avail':>7} {'free':>7} | {'a-capped':>8} {'a-avail':>8} {'avail-free':>10} | lots M agent/capped/avail/free")
    acc = {k: [] for k in ("a", "capped", "avail", "free")}
    for r in rows:
        b = bnd.get(str(r["episode"]), {})
        a = r["cost"]["shortage"]
        v = {m: (b[m]["cost"]["shortage"] if b.get(m) else np.nan) for m in ("capped", "avail", "free")}
        lots = {m: (np.sum(b[m]["lots_w"]) / 1e6 if b.get(m) else np.nan) for m in ("capped", "avail", "free")}
        acc["a"].append(a)
        for m in v:
            acc[m].append(v[m])
        print(f"{r['episode']:>4} {T(a):7.3f} {T(v['capped']):7.3f} {T(v['avail']):7.3f} {T(v['free']):7.3f} | "
              f"{T(a - v['capped']):8.3f} {T(a - v['avail']):8.3f} {T(v['avail'] - v['free']):10.3f} | "
              f"{np.sum(r['lots_w']) / 1e6:.1f}/{lots['capped']:.1f}/{lots['avail']:.1f}/{lots['free']:.1f}")
    m = {k: np.nanmean(v) for k, v in acc.items()}
    print(f"{'mean':>4} {T(m['a']):7.3f} {T(m['capped']):7.3f} {T(m['avail']):7.3f} {T(m['free']):7.3f} | "
          f"{T(m['a'] - m['capped']):8.3f} {T(m['a'] - m['avail']):8.3f} {T(m['avail'] - m['free']):10.3f}")
    if bnd:
        sh = {mm: np.nanmean([bnd[str(r['episode'])][mm]["cost"]["shed"] for r in rows if bnd[str(r['episode'])].get(mm)]) for mm in ("capped", "avail", "free")}
        print(f"   shed T/ep: agent {T(np.mean([r['cost']['shed'] for r in rows])):.3f}, capped {T(sh['capped']):.3f}, avail {T(sh['avail']):.3f}, free {T(sh['free']):.3f}")

    print("\n## 2. Lots started per fab (M per episode, mean) and where the agent's fab-weeks fall short of the oracle's")
    print("   deficit weeks: oracle starts more than the agent. Reason of the agent's week: 'wafer' = its wafers on hand")
    print("   (end of last week) were below the oracle's starts; 'power' = otherwise (it had wafers, so power or R cut it)")
    print(f"{'fab':<20} {'agent':>6} {'free':>6} {'avail':>6} | {'deficit':>7} {'wafer':>6} {'power':>6} | {'excess':>6} | agent run% oracle run%")
    for fi, f in enumerate(fabs):
        al = np.array([np.asarray(r["lots_w"])[:, fi] for r in rows])  # (ne, T)
        ol = np.array([np.asarray(bnd[str(r["episode"])]["free"]["lots_w"])[:, fi] for r in rows]) if bnd else np.zeros_like(al)
        avl = np.array([np.asarray(bnd[str(r["episode"])]["avail"]["lots_w"])[:, fi] for r in rows]) if bnd else np.zeros_like(al)
        wf = np.array([np.asarray(r["wafer_w"])[:, fi] for r in rows])
        wprev = np.concatenate([wf[:, :1] * 0 + 1e18, wf[:, :-1]], axis=1)
        d = np.maximum(ol - al, 0)
        wl = d * (wprev < ol * 0.999)
        cap = r0["fab_cap0"][fi]
        print(f"{f:<20} {al.sum() / ne / 1e6:6.2f} {ol.sum() / ne / 1e6:6.2f} {avl.sum() / ne / 1e6:6.2f} | {d.sum() / ne / 1e6:7.2f} "
              f"{wl.sum() / ne / 1e6:6.2f} {(d - wl).sum() / ne / 1e6:6.2f} | {np.maximum(al - ol, 0).sum() / ne / 1e6:6.2f} | "
              f"{100 * al.mean() / cap:5.0f}% {100 * ol.mean() / cap:5.0f}%")

    print("\n## 3. Lost sales by sink x product (T USD/episode): agent, avail LP, free LP")
    La = np.mean([np.sum(r["lost_w"], axis=0) for r in rows], axis=0) * pi
    Lv = np.mean([np.sum(bnd[str(r["episode"])]["avail"]["lost_w"], axis=0) for r in rows], axis=0) * pi if bnd else La * 0
    Lf = np.mean([np.sum(bnd[str(r["episode"])]["free"]["lost_w"], axis=0) for r in rows], axis=0) * pi if bnd else La * 0
    Dm = np.mean([np.sum(r["demand_w"], axis=0) for r in rows], axis=0) * pi
    for d in np.argsort(-(La - Lf)):
        print(f"  {dem[d]['node']:>9} {dem[d]['k']:<9} demand {T(Dm[d]):6.3f}  agent {T(La[d]):6.3f}  avail {T(Lv[d]):6.3f}  free {T(Lf[d]):6.3f}  a-free {T(La[d] - Lf[d]):6.3f}")

    print("\n## 4. Chip flows by stage (M units per episode): agent vs free oracle")
    def stage_tot(fl):
        out = {}
        for key, w in fl.items():
            st, a, b, k = key.split("|")
            out[(st, k)] = out.get((st, k), 0.0) + sum(w)
        return out
    A = {}
    O = {}
    for r in rows:
        for k, v in stage_tot(r["flows"]).items():
            A[k] = A.get(k, 0) + v / ne
        if bnd:
            for k, v in stage_tot(bnd[str(r["episode"])]["free"]["flows"]).items():
                O[k] = O.get(k, 0) + v / ne
    for k in sorted(set(A) | set(O)):
        print(f"  {k[0]:<18} {k[1]:<13} agent {A.get(k, 0) / 1e6:8.2f}  oracle {O.get(k, 0) / 1e6:8.2f}")

    print("\n## 5. Timing: chip shortage by quarter (T USD/episode)")
    for q in range(4):
        sl = slice(q * 26, (q + 1) * 26)
        a = np.mean([np.sum(np.asarray(r["lost_w"])[sl] * pi) for r in rows])
        f = np.mean([np.sum(np.asarray(bnd[str(r["episode"])]["free"]["lost_w"])[sl] * pi) for r in rows]) if bnd else 0
        v = np.mean([np.sum(np.asarray(bnd[str(r["episode"])]["avail"]["lost_w"])[sl] * pi) for r in rows]) if bnd else 0
        print(f"  weeks {q * 26 + 1:>3}-{(q + 1) * 26:<3} agent {T(a):.3f}  avail {T(v):.3f}  free {T(f):.3f}")

    print("\n## 6. The chip LP's own view (from its log)")
    # planned starts this week vs realized, per fab
    err_p, tot_p = np.zeros(len(fabs)), np.zeros(len(fabs))
    fe_err, fe_n = [], 0
    for r in rows:
        L = np.asarray(r["lots_w"])
        Dw = np.asarray(r["demand_w"])
        for e in r["log"]:
            w = e["week"]
            for j, fp in enumerate(e["fab_pos"]):
                err_p[fp] += e["start"][j][0] - L[w - 1, fp]
                tot_p[fp] += L[w - 1, fp]
            dmat = np.asarray(e["dem"])
            for j, row in enumerate(e["sink_rows"]):
                for t in (0, 4, 8, 16):
                    if t < dmat.shape[1] and w - 1 + t < Dw.shape[0]:
                        fe_err.append((t, row, dmat[j, t], Dw[w - 1 + t, row]))
    print("   planned starts (window week 0) minus realized, % of realized:")
    print("   " + "  ".join(f"{f.replace('fab_', '')}:{100 * err_p[i] / max(tot_p[i], 1):+.0f}%" for i, f in enumerate(fabs)))
    fe = np.array([(t, row, a, b) for t, row, a, b in fe_err])
    if len(fe):
        print("   demand the LP assumed vs true demand (pi-weighted), by look-ahead week:")
        for t in (0, 4, 8, 16):
            s = fe[fe[:, 0] == t]
            if not len(s):
                continue
            rows_ = s[:, 1].astype(int)
            a, b = s[:, 2] * pi[rows_], s[:, 3] * pi[rows_]
            print(f"     t+{t:<2}: assumed/true {a.sum() / b.sum():.3f}, mean |error| {np.abs(a - b).sum() / b.sum():.3f} of true")


if __name__ == "__main__":
    main(*sys.argv[1:])
