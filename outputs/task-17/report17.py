"""Tables for results/task-17.md from gap17.py's JSON.  uv run python outputs/task-17/report17.py <json>"""

import sys
from collections import defaultdict
import json

import numpy as np

sys.path.insert(0, "outputs")
from cost_breakdown import table  # noqa: E402

T12 = 1e12


def main(path):
    rows = json.loads(open(path).read())
    rows = [r for r in rows if r["oracle"] is not None]
    meta = next(r["meta"] for r in rows if isinstance(r.get("meta"), dict) and "fabs" in r["meta"])
    n = len(rows)
    gap = np.array([(r["J_agent_cents"] - r["J_oracle_cents"]) / 100 for r in rows])
    ngap = np.array([(r["J_naive_cents"] - r["J_oracle_cents"]) / 100 for r in rows])
    print(f"episodes {n}; mean gap agent-oracle {gap.mean()/T12:.3f} T USD; naive-oracle {ngap.mean()/T12:.3f} T;"
          f" RSS (mean of per-ep ratio, unweighted) {np.mean(1 - gap / ngap):.4f}")
    table(rows, "ALL")
    for s in sorted({r["stratum"] for r in rows}):
        sub = [r for r in rows if r["stratum"] == s]
        table(sub, f"harm level {s}")
        g = np.array([(r["J_agent_cents"] - r["J_oracle_cents"]) / 100 for r in sub])
        print(f"  level {s}: gap {g.mean()/T12:.3f} T/ep")

    # level-weighted gap: what one RSS point is worth per level
    print("\n## Lost sales by product (USD/episode, mean): agent vs oracle vs naive")
    D = meta["demands"]
    pi = np.array([d["pi"] for d in D])
    A = np.mean([np.array(r["detail"]["lost"]) * pi for r in rows], axis=0)
    O = np.mean([np.array(r["oracle_detail"]["lost"]) * pi for r in rows if isinstance(r["oracle_detail"], dict) and "lost" in r["oracle_detail"]], axis=0)
    N = np.mean([np.array(r["naive_detail"]["lost"]) * pi for r in rows], axis=0)
    dem = np.mean([np.array(r["detail"]["demand"]) * pi for r in rows], axis=0)
    by = defaultdict(lambda: np.zeros(4))
    for i, d in enumerate(D):
        by[d["k"]] += [dem[i], N[i], A[i], O[i]]
    print(f"{'product':22s} {'demand $':>10s} {'naive lost':>10s} {'agent lost':>10s} {'oracle lost':>11s} {'agent-oracle':>12s}")
    for k, v in sorted(by.items(), key=lambda kv: -(kv[1][2] - kv[1][3])):
        if v[0] > 0:
            print(f"{k:22s} {v[0]/T12:10.3f} {v[1]/T12:10.3f} {v[2]/T12:10.3f} {v[3]/T12:11.3f} {(v[2]-v[3])/T12:12.3f}")
    print("(T USD per episode)")

    print("\n## Lost sales by sink x product, top 25 by agent-oracle (T USD/episode)")
    print(f"{'sink':28s} {'product':20s} {'demand':>8s} {'agent':>8s} {'oracle':>8s} {'a-o':>8s} {'agent fill':>10s} {'oracle fill':>11s}")
    order = np.argsort(-(A - O))
    for i in order[:25]:
        d = D[i]
        print(f"{d['node']:28s} {d['k']:20s} {dem[i]/T12:8.3f} {A[i]/T12:8.3f} {O[i]/T12:8.3f} {(A[i]-O[i])/T12:8.3f}"
              f" {1-A[i]/max(dem[i],1e-9):10.1%} {1-O[i]/max(dem[i],1e-9):11.1%}")
    byr = defaultdict(lambda: np.zeros(3))
    for i, d in enumerate(D):
        byr[d["region"]] += [dem[i], A[i], O[i]]
    print("\nby sink region:", ", ".join(f"{k} {(v[1]-v[2])/T12:.3f}" for k, v in sorted(byr.items(), key=lambda kv: -(kv[1][1]-kv[1][2]))))

    print("\n## Fab lots started per episode (mean): agent vs oracle")
    F = meta["fabs"]
    la = np.mean([r["detail"]["lots_started"] for r in rows], axis=0)
    lo = np.mean([r["oracle_detail"]["lots_started"] for r in rows], axis=0)
    ea = np.mean([r["detail"]["energy"] for r in rows], axis=0)
    eo = np.mean([r["oracle_detail"]["energy"] for r in rows], axis=0)
    T = len(rows[0]["detail"]["lots_w"])
    print(f"{'fab':26s} {'cls':8s} {'grid':10s} {'product':16s} {'cap*T':>9s} {'agent':>9s} {'oracle':>9s} {'a/o':>6s} {'a %cap':>7s} {'o %cap':>7s} {'E agent':>8s} {'E oracle':>8s}")
    for f in np.argsort(-(lo - la)):
        m = F[f]
        cap = m["cap0"] * T
        print(f"{m['id']:26s} {m['cls']:8s} {str(m['grid']):10s} {m['product']:16s} {cap:9.0f} {la[f]:9.0f} {lo[f]:9.0f}"
              f" {la[f]/max(lo[f],1e-9):6.2f} {la[f]/cap:7.1%} {lo[f]/cap:7.1%} {ea[f]:8.1f} {eo[f]:8.1f}")
    byg = defaultdict(lambda: np.zeros(2))
    for f, m in enumerate(F):
        byg[str(m["grid"])] += [la[f], lo[f]]
    print("lots by grid (agent / oracle):", ", ".join(f"{g} {v[0]:.0f}/{v[1]:.0f}" for g, v in byg.items()))
    byc = defaultdict(lambda: np.zeros(2))
    for f, m in enumerate(F):
        byc[m["cls"]] += [la[f], lo[f]]
    print("lots by class (agent / oracle):", ", ".join(f"{g} {v[0]:.0f}/{v[1]:.0f}" for g, v in byc.items()))

    print("\n## Shed by grid (USD/episode, mean)")
    G = meta["grids"]
    voll = np.array([g["voll"] for g in G])
    sa = np.mean([np.array(r["detail"]["shed"]) * voll for r in rows], axis=0)
    so = np.mean([np.array(r["oracle_detail"]["shed"]) * voll for r in rows], axis=0)
    sn = np.mean([np.array(r["naive_detail"]["shed"]) * voll for r in rows], axis=0)
    print(f"{'grid':12s} {'priority':11s} {'naive':>9s} {'agent':>9s} {'oracle':>9s} {'a-o':>9s}  (T USD)")
    for g in np.argsort(-(sa - so)):
        print(f"{G[g]['id']:12s} {G[g]['priority']:11s} {sn[g]/T12:9.4f} {sa[g]/T12:9.4f} {so[g]/T12:9.4f} {(sa[g]-so[g])/T12:9.4f}")

    print("\n## Per episode: gap and NEW disruption events (onset in week 0..T; events running since before the episode are left out)")
    types = sorted({e["type"] for r in rows if isinstance(r["events"], list) for e in r["events"]})
    print(f"{'ep':>4s} {'lvl':>3s} {'gap T':>7s} {'naive-o T':>9s} {'RSS':>6s} {'chipgap T':>9s} {'shedgap T':>9s}  " + " ".join(f"{t[:10]:>10s}" for t in types))
    cnt = []
    for r, g, ng in zip(rows, gap, ngap):
        ev = [e for e in r["events"] if e["onset"] >= 0] if isinstance(r["events"], list) else []
        c = [sum(e["type"] == t for e in ev) for t in types]
        cnt.append(c)
        cg = r["agent"]["shortage"] - r["oracle"]["shortage"]
        sg = r["agent"]["shed"] - r["oracle"]["shed"]
        print(f"{r['episode']:4d} {r['stratum']:3d} {g/T12:7.3f} {ng/T12:9.3f} {1-g/ng:6.3f} {cg/T12:9.3f} {sg/T12:9.3f}  " + " ".join(f"{x:10d}" for x in c))
    cnt = np.array(cnt)
    print("\nGap with vs without each event type (mean T USD/episode; corr = Pearson of count vs gap):")
    for j, t in enumerate(types):
        has = cnt[:, j] > 0
        w = gap[has].mean() / T12 if has.any() else float("nan")
        wo = gap[~has].mean() / T12 if (~has).any() else float("nan")
        cr = np.corrcoef(cnt[:, j], gap)[0, 1] if cnt[:, j].std() > 0 else float("nan")
        print(f"  {t:22s} episodes {has.sum():2d}/{n}: with {w:.3f}, without {wo:.3f}, corr {cr:+.2f}")
    print("\nEvent targets of the biggest-gap episodes:")
    for i in np.argsort(-gap)[:5]:
        r = rows[i]
        ev = [e for e in r["events"] if e["onset"] >= 0] if isinstance(r["events"], list) else []
        s = defaultdict(int)
        for e in ev:
            s[(e["type"], e["target"])] += 1
        print(f"  ep {r['episode']} (lvl {r['stratum']}, gap {gap[i]/T12:.3f} T):",
              "; ".join(f"{t}@{tg}x{c}" for (t, tg), c in sorted(s.items())))
    bad = [r["episode"] for r in rows if not isinstance(r["events"], list) or not isinstance(r["oracle_detail"], dict) or "error" in (r["oracle_detail"] or {})]
    if bad:
        print("episodes with extraction errors:", bad)


if __name__ == "__main__":
    main(sys.argv[1])
