"""Task 31: ceiling of a perfect switch. From a variants.py results.json, the pooled RSS if each episode (or each harm
level) played the best of the variants, using the references of a gap17.py JSON on the same episodes.

    uv run python outputs/task-31/switch_bound31.py outputs/variants/<round>/results.json outputs/task-31/gap17v2_full_0_dev_mpc_imit_room.json
"""
import json
import sys

import numpy as np

W = {1: 0.5, 2: 0.3, 3: 0.15, 4: 0.05}


def rss(J, ref):
    out, tot = {}, 0.0
    for s in W:
        idx = [i for i, r in enumerate(ref) if r["stratum"] == s]
        jn = sum(ref[i]["J_naive_cents"] for i in idx)
        jo = sum(ref[i]["J_oracle_cents"] for i in idx)
        out[s] = (jn - sum(J[i] for i in idx)) / (jn - jo)
        tot += W[s] * out[s]
    return tot, out


def main(res_path, gap_path):
    res = json.load(open(res_path))["results"]
    ref = json.load(open(gap_path))
    names = list(res)
    J = np.array([res[n]["J"] for n in names], dtype=float)
    for n, j in zip(names, J):
        t, lv = rss(j, ref)
        print(f"{n:12s} {t:.4f}  " + " ".join(f"L{s} {lv[s]:.3f}" for s in W))
    t, lv = rss(J.min(0), ref)
    print(f"{'best/episode':12s} {t:.4f}  " + " ".join(f"L{s} {lv[s]:.3f}" for s in W), " (perfect per-episode switch)")
    best = {s: max(names, key=lambda n: rss(J[names.index(n)], ref)[1][s]) for s in W}
    Jl = np.array([J[names.index(best[r["stratum"]])][i] for i, r in enumerate(ref)])
    t, lv = rss(Jl, ref)
    print(f"{'best/level':12s} {t:.4f}  " + " ".join(f"L{s} {lv[s]:.3f}" for s in W), " picks", best)


if __name__ == "__main__":
    main(*sys.argv[1:])
