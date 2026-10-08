"""Task 26 analysis: oracle vs agent structure on recorded episodes (imit26.py's npz files).

    python outputs/task-26/an26.py small 2626 mpc_fab3sell [eps]
"""
import pickle
import sys
from pathlib import Path

import numpy as np

D = Path("outputs/task-26/data")


def load(task, ent, who, ns):
    out = {}
    for n in ns:
        f = D / f"{task}_{ent}_{who}_{n}.npz"
        if f.exists():
            out[n] = dict(np.load(f))
    return out


def pools(st):
    """(grid ordinal, fuel k) -> grid slot, terminal slots, burn share, thr."""
    nodes, slots = st["nodes"], st["slots"]
    sidx = {(nd, k): i for i, (nd, k, _) in enumerate(slots)}
    feeds = {}
    for _id, tail, head in st["edges"]:
        if nodes[tail][1] == "terminal" and nodes[head][1] == "grid":
            feeds.setdefault(head, set()).add(tail)
    out = {}
    for go, (g, ga) in enumerate(zip(st["grids"], st["grid_attrs"])):
        for k in ga.fuels:
            terms = [sidx[(t, k)] for t in sorted(feeds.get(g, ())) if (t, k) in sidx]
            thr = st["psi"] * ga.ibar.get(k, 0.0) if k == ga.rationed else 0.0
            out[(go, k)] = dict(grid=sidx.get((g, k)), terms=terms, share=ga.shares[k], thr=thr,
                                name=f"{nodes[g][0]}/{st['commodities'][k]}", cap=slots[sidx[(g, k)]][2])
    return out


def q(a, ps=(10, 50, 90)):
    a = np.asarray(a).ravel()
    a = a[np.isfinite(a)]
    return " ".join(f"{np.percentile(a, p):7.2f}" for p in ps) if a.size else "   -"


def main(task, ent, agent, spec=None):
    st = pickle.loads((D / f"{task}_static.pkl").read_bytes())
    ns = range(0, 200) if spec is None else [int(x) for x in spec.split(",")]
    O = load(task, ent, "oracle", ns)
    A = load(task, ent, agent, ns)
    common = sorted(set(O) & set(A)) if A else sorted(O)
    print(f"{task} root {ent}: {len(O)} oracle, {len(A)} agent, {len(common)} common episodes")
    P = pools(st)
    W = {"oracle": O, agent: A}
    print("\n## Grid fuel: end-of-week stock in weeks of burn (share*G_bar); grid slot / terminals; p10 p50 p90")
    print("   and share of weeks the grid's rationed fuel ends under psi*Ibar (ration next week)")
    for key, p in P.items():
        go, k = key
        for who, data in W.items():
            if not data:
                continue
            gs, ts, under, gap = [], [], [], []
            for n in common:
                d = data[n]
                burn = p["share"] * d["G_bar"][:, go]
                gs.append(d["stock"][:, p["grid"]] / burn)
                ts.append(sum(d["stock"][:, t] for t in p["terms"]) / burn if p["terms"] else np.zeros_like(burn))
                if p["thr"] > 0:
                    under.append(d["stock"][:, p["grid"]] < p["thr"] * 0.999)
                    gap.append((d["stock"][:, p["grid"]] - p["thr"]) / burn)
            extra = f" under {np.mean(under):5.1%}  (I-thr)/burn {q(gap)}" if under else ""
            print(f"  {p['name']:16s} {who:13s} grid {q(gs)} | term {q(ts)}{extra}")
    print("\n## Shed share of base load per grid (mean over weeks), weeks with shed > 0.1%")
    for go, g in enumerate(st["grids"]):
        line = f"  {st['nodes'][g][0]:10s}"
        for who, data in W.items():
            if not data:
                continue
            sh = np.array([data[n]["shed"][:, go] / data[n]["y_bar"][:, go] for n in common])
            line += f" {who}: mean {sh.mean():6.2%} weeks>0.1% {np.mean(sh > 1e-3):5.1%} |"
        print(line)
    print("\n## Fabs: utilisation lots/fabcap (mean, share of weeks >90%, <10%), lag-1 autocorr; wafer stock in weeks of cap")
    sidx = {(nd, k): i for i, (nd, k, _) in enumerate(st["slots"])}
    for fo, (f, fa) in enumerate(zip(st["fabs"], st["fab_attrs"])):
        ws = sidx[(f, fa.input)]
        for who, data in W.items():
            if not data:
                continue
            u = np.array([data[n]["lots"][:, fo] / np.maximum(data[n]["fabcap"][:, fo], 1) for n in common])
            wk = np.array([data[n]["stock"][:, ws] / max(fa.cap0, 1) for n in common])
            ac = np.nanmean([np.corrcoef(x[:-1], x[1:])[0, 1] if x.std() > 1e-6 else np.nan for x in u])
            print(f"  {st['nodes'][f][0]:18s} {who:13s} util {u.mean():5.1%} >90% {np.mean(u > .9):5.1%} "
                  f"<10% {np.mean(u < .1):5.1%} ac1 {ac:5.2f} | wafers/cap {q(wk)}")
    print("\n## Fuel burnt per grid segment, mean per week (G of the segment), and fuel shipped out of each source")
    for j, (go, k) in enumerate(st["seg_keys"]):
        if k is None:
            continue
        line = f"  {st['nodes'][st['grids'][go]][0]:10s} {st['commodities'][k]:8s}"
        for who, data in W.items():
            if data:
                line += f" {who}: {np.mean([data[n]['seg'][:, j].mean() for n in common]):9.1f}"
        print(line)
    nodes = st["nodes"]
    fuels = [i for i, c in enumerate(st["commodities"]) if c in ("lng", "crude", "nucfuel")]
    rows = {}
    for e, (eid, tail, head) in enumerate(st["edges"]):
        if nodes[tail][1] == "source":
            for k in fuels:
                for who, data in W.items():
                    if data:
                        v = np.mean([data[n]["x"][:, e, k].mean() for n in common])
                        if v > 1e-6:
                            rows.setdefault((eid, k), {})[who] = v
    for (eid, k), v in sorted(rows.items()):
        print(f"  {eid:40s} {st['commodities'][k]:8s} " + " ".join(f"{w}: {x:9.1f}" for w, x in v.items()))
    print("\n## Cost J (T USD) mean")
    for who, data in W.items():
        if data:
            print(f"  {who}: {np.mean([data[n]['J'] for n in common]) / 1e14:.4f}")


if __name__ == "__main__":
    main(*sys.argv[1:])
