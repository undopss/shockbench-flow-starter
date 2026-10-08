"""Task 27: chokepoint closure tables for the agent (climate.json): P(open at lead t | state now, elapsed weeks d).

    uv run python outputs/task-27/hazard.py   (reads climate_{full,small}_300.npz, writes agents/mpc_clim/climate.json)

closed[d][t] = P(open o >= 0.5 at week now + t | closed now and closed for exactly d weeks so far, d capped at DMAX),
open[t] = P(open at now + t | open now). Pooled per chokepoint over 300 episodes of an own root (27027); weeks whose
lead t falls past the episode end are skipped.
"""

import json
from pathlib import Path

import numpy as np

DMAX, TMAX = 8, 24


def tables(o):
    N, T = o.shape
    closed = o < 0.5
    num_c = np.zeros((DMAX + 1, TMAX + 1)); den_c = np.zeros((DMAX + 1, TMAX + 1))
    num_o = np.zeros(TMAX + 1); den_o = np.zeros(TMAX + 1)
    for i in range(N):
        d = 0
        for t in range(T):
            d = d + 1 if closed[i, t] else 0
            for k in range(1, TMAX + 1):
                if t + k >= T:
                    break
                op = not closed[i, t + k]
                if d:
                    dd = min(d, DMAX)
                    num_c[dd, k] += op; den_c[dd, k] += 1
                else:
                    num_o[k] += op; den_o[k] += 1
    pc = np.where(den_c > 20, num_c / np.maximum(den_c, 1), np.nan)
    po = num_o / np.maximum(den_o, 1)
    # rows with too few samples: carry the last estimated row (longer closures look alike)
    for dd in range(2, DMAX + 1):
        bad = np.isnan(pc[dd])
        pc[dd, bad] = pc[dd - 1, bad]
    return np.nan_to_num(pc[1:, 1:], nan=0.0), po[1:], den_c[1:, 1].astype(int)


def main():
    import gymnasium as gym
    import shockbench_flow_gym  # noqa: F401

    out = {}
    for task in ("small", "full"):
        z = np.load(f"outputs/task-27/climate_{task}_300.npz")
        env = gym.make({"small": "ShockBench/Small-v0", "full": "ShockBench/Full-v0"}[task])
        env.reset(options={"episode": 0})
        inst = env.unwrapped.instance
        T = z["o"].shape[1]
        out[str(T)] = {}
        print(f"\n{task}: P(open at +1, +2, +4, +8, +12 | closed for d weeks)  [n weeks]   and | open now")
        for c, node in enumerate(inst.chokepoints):
            nid = inst.nodes[node].id
            pc, po, n = tables(z["o"][:, :, c])
            out[str(T)][nid] = {"closed": np.round(pc, 4).tolist(), "open": np.round(po, 4).tolist(),
                                "frac": round(float((z["o"][:, :, c] < 0.5).mean()), 4)}
            print(f"  {nid:12s} open now: " + " ".join(f"{po[k - 1]:.2f}" for k in (1, 2, 4, 8, 12)))
            for d in (1, 2, 3, 5, 8):
                print(f"  {'':12s} d={d}: " + " ".join(f"{pc[d - 1, k - 1]:.2f}" for k in (1, 2, 4, 8, 12))
                      + f"  [{n[d - 1]}]")
    path = Path("agents/mpc_clim/climate.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out))
    print("wrote", path)


if __name__ == "__main__":
    main()
