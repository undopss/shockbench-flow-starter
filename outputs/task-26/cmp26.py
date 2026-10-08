"""Task 26: paired comparison of recorded agent variants vs a base on the same training episodes (imit26.py npz).

    python outputs/task-26/cmp26.py full 2626 mpc_fab3sell ag_room,ag_target 0-7
dRSS ~ -dJ / naive's gap to the oracle (Full dev 3.418 T, Small dev 0.930 T per episode; task 20), an approximation.
"""
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from an26 import D  # noqa: E402
from imit26 import eps  # noqa: E402

NAIVE_GAP = {"full": 3.418e12, "small": 0.930e12}


def main(task, ent, base, others, spec):
    st = pickle.loads((D / f"{task}_static.pkl").read_bytes())
    ns = eps(spec)
    C = st["commodities"]
    fuel_seg = {j: (go, C[k]) for j, (go, k) in enumerate(st["seg_keys"]) if k is not None}
    fs = [s for s, (nd, k, _) in enumerate(st["slots"]) if C[k] in ("lng", "crude")]
    gname = [st["nodes"][g][0] for g in st["grids"]]

    def get(who):
        return {n: dict(np.load(D / f"{task}_{ent}_{who}_{n}.npz")) for n in ns if (D / f"{task}_{ent}_{who}_{n}.npz").exists()}

    B = get(base)
    O = get("oracle")
    for who in [base] + others.split(","):
        W = get(who)
        c = [n for n in ns if n in W and n in B]
        dJ = np.array([(W[n]["J"] - B[n]["J"]) / 100 for n in c])  # USD
        se = dJ.std(ddof=1) / np.sqrt(len(c)) if len(c) > 1 else 0
        lost = np.mean([(W[n]["lost"].sum(0) * [d[2] for d in st["demands"]]).sum() for n in c]) / 1e12
        shed = np.mean([W[n]["shed"].sum() * 4125277.26 for n in c]) / 1e12
        disp = np.mean([W[n]["disposal"][:, fs].sum() for n in c])
        crude = {g: np.mean([W[n]["seg"][:, j].mean() for n in c]) for j, (g, f) in fuel_seg.items() if f == "crude"}
        gap = np.mean([(W[n]["J"] - O[n]["J"]) / 100 for n in c if n in O]) / 1e12
        print(f"{who:14s} n={len(c)} dJ {dJ.mean() / 1e12:+.4f} T (se {se / 1e12:.4f}) ~dRSS {-dJ.mean() / NAIVE_GAP[task]:+.4f}"
              f" | gap to oracle {gap:.3f} T | lost-sales {lost:.3f} T shed {shed:.3f} T | fuel disposed {disp:9.0f}"
              f" | crude burnt/wk " + " ".join(f"{gname[g][5:]}:{v:.0f}" for g, v in crude.items()))


if __name__ == "__main__":
    main(*sys.argv[1:])
