"""Task 26: per grid, where the energy goes (homes / fabs / unused) and fuel disposed, oracle vs agent."""
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from an26 import D, load  # noqa: E402


def main(task, ent, agent):
    st = pickle.loads((D / f"{task}_static.pkl").read_bytes())
    O, A = load(task, ent, "oracle", range(200)), load(task, ent, agent, range(200))
    common = sorted(set(O) & set(A))
    print(f"{task} {len(common)} episodes; per grid mean per week: G total, homes y, fabs E, unused, shed; as % of y_bar")
    fab_grid = [st["grids"].index(fa.grid) if fa.grid is not None else -1 for fa in st["fab_attrs"]]
    for go, g in enumerate(st["grids"]):
        segs = [j for j, (gg, k) in enumerate(st["seg_keys"]) if gg == go]
        fabs = [fo for fo, x in enumerate(fab_grid) if x == go]
        for who, data in (("oracle", O), (agent, A)):
            G = np.array([data[n]["seg"][:, segs].sum(1) for n in common])
            y = np.array([data[n]["served_load"][:, go] for n in common])
            E = np.array([data[n]["energy"][:, fabs].sum(1) if fabs else np.zeros(G.shape[1]) for n in common])
            sh = np.array([data[n]["shed"][:, go] for n in common])
            yb = np.array([data[n]["y_bar"][:, go] for n in common])
            un = G - y - E
            print(f"  {st['nodes'][g][0]:9s} {who:13s} G {G.mean() / yb.mean():7.2%} y {y.mean() / yb.mean():7.2%} "
                  f"E {E.mean() / yb.mean():6.2%} unused {un.mean() / yb.mean():6.2%} shed {sh.mean() / yb.mean():6.2%}"
                  f" | weeks unused>0.5% {np.mean(un > 0.005 * yb):5.1%}")
    print("\nfuel disposed per week (stock slots of energy commodities), mean")
    fuels = {i for i, c in enumerate(st["commodities"]) if c in ("lng", "crude", "nucfuel")}
    for s, (nd, k, _cap) in enumerate(st["slots"]):
        if k not in fuels:
            continue
        o = np.mean([O[n]["disposal"][:, s].mean() for n in common])
        a = np.mean([A[n]["disposal"][:, s].mean() for n in common])
        if max(o, a) > 1:
            print(f"  {st['nodes'][nd][0]:20s} {st['commodities'][k]:8s} oracle {o:9.1f}  {agent} {a:9.1f}")


if __name__ == "__main__":
    main(*sys.argv[1:])
