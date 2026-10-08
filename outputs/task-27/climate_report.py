"""Task 27, step 1 report: rates, durations and depth of shocks per chokepoint / energy source / grid / energy edge.

    uv run python outputs/task-27/climate_report.py full 300

"Normal" = the item's median over all episode-weeks; a shock week = value < 0.9 x normal (chokepoint: open o < 1).
Spells are runs of shock weeks; "starts/ep" counts spells that begin after week 1; P(end<=k | in shock) is the share of
shock weeks whose spell ends within k weeks (what a persistence planner gets wrong).
"""

import sys

import numpy as np


def spells(x):
    """x (N, T) bool -> list of (ep, start, length, censored_left, censored_right)."""
    out = []
    N, T = x.shape
    for i in range(N):
        t = 0
        while t < T:
            if x[i, t]:
                s = t
                while t < T and x[i, t]:
                    t += 1
                out.append((i, s, t - s, s == 0, t == T))
            else:
                t += 1
    return out


def remaining(x, ks=(1, 2, 4, 8, 12)):
    """share of shock weeks (excluding right-censored spells' tails) whose spell is over within k weeks."""
    N, T = x.shape
    rem = []
    for i in range(N):
        for t in range(T):
            if x[i, t]:
                j = t
                while j < T and x[i, j]:
                    j += 1
                if j < T:
                    rem.append(j - t)
                elif T - t > max(ks):
                    rem.append(10**6)
    rem = np.array(rem)
    return [float((rem <= k).mean()) if len(rem) else float("nan") for k in ks]


def row(name, x, depth=None):
    N, T = x.shape
    sp = spells(x)
    starts = [s for s in sp if not s[3]]
    lens = [s[2] for s in sp if not s[3] and not s[4]]
    r = remaining(x)
    d = f"{depth:6.2f}" if depth is not None else "     -"
    print(f"  {name:28s} {x.mean():7.1%} {len(starts) / N:6.2f} {np.mean(lens) if lens else float('nan'):6.1f} "
          f"{np.median(lens) if lens else float('nan'):5.1f} {d}  " + " ".join(f"{v:5.0%}" for v in r))
    return dict(frac=float(x.mean()), starts=len(starts) / N, mean_len=float(np.mean(lens)) if lens else None,
                depth=depth, p_end=r)


HDR = (f"  {'item':28s} {'shock%':>7s} {'st/ep':>6s} {'meanL':>6s} {'medL':>5s} {'depth':>6s}  P(end<=1,2,4,8,12 w | in shock)")


def main(task="full", n=300):
    import gymnasium as gym
    import shockbench_flow_gym  # noqa: F401

    z = np.load(f"outputs/task-27/climate_{task}_{n}.npz")
    env = gym.make({"small": "ShockBench/Small-v0", "full": "ShockBench/Full-v0"}[task])
    env.reset(options={"episode": 0})
    inst, lay = env.unwrapped.instance, env.unwrapped.layout
    nid = [nd.id for nd in inst.nodes]
    com = [c.id for c in inst.commodities]
    energy = {0, 1, 2}
    N, T = z["o"].shape[:2]
    print(f"{task}: {N} episodes x {T} weeks (own root 27027)")
    print("\nchokepoints: shock = open o < 1 (o = 0: closed)")
    print(HDR)
    for c, node in enumerate(inst.chokepoints):
        o = z["o"][:, :, c]
        row(nid[node] + " closed", o < 0.5)
        row(nid[node] + " partial/closed", o < 0.999)
        for kk, kn in ((0, "kappa_tb"),):
            kap = z["kappa"][:, :, c, kk]
            med = np.median(kap)
            if med > 0:
                x = kap < 0.9 * med
                row(nid[node] + " " + kn + " cut", x, float(1 - (kap[x] / med).mean()) if x.any() else None)
    print("\nenergy sources: supply < 0.9 x median")
    print(HDR)
    for s, (node, k) in enumerate(lay.supply_slots):
        if k not in energy:
            continue
        v = z["supply"][:, :, s]
        med = np.median(v)
        if med <= 0:
            continue
        x = v < 0.9 * med
        row(f"{nid[node]}/{com[k]}", x, float(1 - (v[x] / med).mean()) if x.any() else None)
    print("\ngrids: G_bar < 0.9 x median")
    print(HDR)
    for g, node in enumerate(inst.grids):
        v = z["G"][:, :, g]
        med = np.median(v)
        x = v < 0.9 * med
        row(nid[node], x, float(1 - (v[x] / med).mean()) if x.any() else None)
    print("\nedges carrying energy (from a source or terminal): u < 0.9 x median (only edges with shocks > 1% of weeks)")
    print(HDR)
    for e, ed in enumerate(inst.edges):
        ks = set(getattr(ed, "K", ()) or ())
        if not (ks & energy):
            continue
        v = z["u"][:, :, e]
        med = np.median(v)
        if med <= 0:
            continue
        x = v < 0.9 * med
        if x.mean() < 0.01:
            continue
        row(f"{nid[ed.tail]}->{nid[ed.head]}", x, float(1 - (v[x] / med).mean()) if x.any() else None)
    TY = ("tariff", "sanction", "material_outage", "militarised_closure", "regional_conflict", "piracy",
          "energy_shock", "weather_closure", "port_strike")
    ev = z["ev"]  # ep, type, tk, target, onset, duration
    print("\nevents acting in the episode (incl. carried-in), per episode, and mean duration (weeks)")
    for t in range(9):
        r = ev[ev[:, 1] == t]
        inside = r[r[:, 4] >= 0]
        print(f"  {TY[t]:20s} acting/ep {len(r) / N:6.2f}  start inside/ep {len(inside) / N:5.2f}  "
              f"duration mean {inside[:, 5].mean() if len(inside) else float('nan'):6.1f} median "
              f"{np.median(inside[:, 5]) if len(inside) else float('nan'):6.1f}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
