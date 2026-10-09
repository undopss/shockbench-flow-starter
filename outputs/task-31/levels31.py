"""Task 31: split the gap to the clairvoyant plan by harm level (calm = level 1) from a gap17.py JSON.

    uv run python outputs/task-31/levels31.py outputs/task-17/gap17v2_full_0_dev_mpc_imit_room.json [nopulse.json]

Per level: RSS, gap (T USD/ep) by component, chip shortage by product, shed by grid, gap by quarter, and per episode
the gap with its event counts. With a second JSON (same agent, pulses off) also the pulses' shed price per level.
"""
import json
import sys
from collections import Counter

import numpy as np

T12 = 1e12


def load(p):
    return json.load(open(p))


def comp_gap(r, c):
    return (r["agent"][c] - r["oracle"][c]) / T12


def main(path, nopulse=None):
    R = load(path)
    NP = {r["episode"]: r for r in load(nopulse)} if nopulse else {}
    m = R[0]["meta"]
    grids = [g["id"] for g in m["grids"]]
    dem = m["demands"]
    levels = sorted({r["stratum"] for r in R})
    comps = list(R[0]["agent"].keys())
    print(f"{path}: {len(R)} episodes, levels {levels}")
    for s in levels:
        rs = [r for r in R if r["stratum"] == s]
        ja = sum(r["J_agent_cents"] for r in rs); jn = sum(r["J_naive_cents"] for r in rs)
        jo = sum(r["J_oracle_cents"] for r in rs)
        n = len(rs)
        print(f"\n=== level {s}: n={n}  RSS {(jn - ja) / (jn - jo):.4f}  gap {(ja - jo) / 100 / n / T12:.3f} T/ep"
              f"  naive gap {(jn - jo) / 100 / n / T12:.3f}")
        print("  components (agent - oracle, T/ep):",
              "  ".join(f"{c} {np.mean([comp_gap(r, c) for r in rs]):+.4f}" for c in comps
                        if abs(np.mean([comp_gap(r, c) for r in rs])) > 5e-4))
        # chip shortage by product (lost x pi)
        byk = Counter()
        for r in rs:
            la = r["detail"]["lost"]; lo = r["oracle_detail"]["lost"]
            for i, d in enumerate(dem):
                byk[d["k"]] += (la[i] - lo[i]) * d["pi"] / T12 / n
        print("  shortage by product:", "  ".join(f"{k} {v:+.4f}" for k, v in byk.items()))
        # shed by grid (GWh x voll)
        sg = Counter()
        for r in rs:
            for i, g in enumerate(m["grids"]):
                sg[g["id"]] += (r["detail"]["shed"][i] - r["oracle_detail"]["shed"][i]) * g["voll"] / T12 / n
        print("  shed by grid:", "  ".join(f"{g} {v:+.4f}" for g, v in sg.items() if abs(v) > 5e-4))
        if NP:
            pp = Counter()
            for r in rs:
                q = NP.get(r["episode"])
                if q is None:
                    continue
                for i, g in enumerate(m["grids"]):
                    pp[g["id"]] += (r["detail"]["shed"][i] - q["detail"]["shed"][i]) * g["voll"] / T12 / n
            print("  pulse shed price (with - without pulses):", "  ".join(f"{g} {v:+.4f}" for g, v in pp.items()
                                                                          if abs(v) > 5e-4),
                  f" total {sum(pp.values()):+.4f}")
            print("  pulses-off chip shortage gap:",
                  f"{np.mean([comp_gap(NP[r['episode']], 'shortage') for r in rs if r['episode'] in NP]):+.4f}",
                  " RSS-off", end=" ")
            ja2 = sum(NP[r["episode"]]["J_agent_cents"] for r in rs)
            print(f"{(jn - ja2) / (jn - jo):.4f}")
        # by quarter
        Tn = len(rs[0]["detail"]["shed_w"])
        q4 = np.array_split(np.arange(Tn), 4)
        line = []
        for qi, idx in enumerate(q4):
            sh = np.mean([sum((np.array(r["detail"]["shed_w"])[idx] - np.array(r["oracle_detail"]["shed_w"])[idx]
                              ).sum(0) * [g["voll"] for g in m["grids"]]) / T12 for r in rs])
            ls = np.mean([sum(((np.array(r["detail"]["lost_w"])[idx] - np.array(r["oracle_detail"]["lost_w"])[idx]
                               ).sum(0)) * [d["pi"] for d in dem]) / T12 for r in rs])
            line.append(f"Q{qi + 1} shed {sh:+.3f} lost {ls:+.3f}")
        print("  by quarter:", " | ".join(line))
        print("  episodes: ep  gap  shed  short  | naive gap | events")
        for r in sorted(rs, key=lambda r: -(r["J_agent_cents"] - r["J_oracle_cents"])):
            ev = Counter(e["type"] for e in r["events"])
            print(f"    {r['episode']:3d} {(r['J_agent_cents'] - r['J_oracle_cents']) / 100 / T12:6.3f}"
                  f" {comp_gap(r, 'shed'):6.3f} {comp_gap(r, 'shortage'):6.3f} | "
                  f"{(r['J_naive_cents'] - r['J_oracle_cents']) / 100 / T12:6.3f} | "
                  + " ".join(f"{k}:{v}" for k, v in sorted(ev.items())))


if __name__ == "__main__":
    main(*sys.argv[1:])
