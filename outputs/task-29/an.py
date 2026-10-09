"""Task 29: pplan's fab-energy value (pp_value x pi) vs the chip LP's dual value, per grid, from probe_*.jsonl.

    uv run python outputs/task-29/an.py "outputs/task-29/probe_*.jsonl"
"""
import glob
import json
import sys

import gymnasium as gym
import numpy as np
import shockbench_flow_gym  # noqa: F401

env = gym.make("ShockBench/Full-v0")
obs, info = env.reset(options={"episode": 0})
ids = [n["id"] for n in info["static"]["instance"]["nodes"]]
rows = []
for f in sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else "outputs/task-29/probe_*.jsonl")):
    rows += [json.loads(line) for line in open(f)]
by = {}
for w, g, V, Vd, eh in rows:
    by.setdefault(ids[g], []).append((w, np.array(V), np.array(Vd), np.array(eh)))
print("week-0 values in VOLL units (fab-draw weighted); 'max' columns: the planner window's max (what decides a pulse)")
print(f"{'grid':10s} {'n':>5s} {'Vmax>1':>7s} {'Vdmax>1':>8s} {'Vd0>0':>6s} {'med V0':>8s} {'med Vd0|>0':>10s} "
      f"{'p90 Vd0':>8s} {'max Vd0':>8s} {'med Vd/V|>0':>11s}")
for g, L in sorted(by.items()):
    V = np.array([x[1][0] for x in L])
    Vd = np.array([x[2][0] for x in L])
    Vmx = np.array([x[1].max() for x in L])
    Vdmx = np.array([x[2].max() for x in L])
    pos = Vd > 0
    ratio = np.median(Vd[pos] / np.maximum(V[pos], 1e-9)) if pos.any() else 0.0
    print(f"{g:10s} {len(L):5d} {np.mean(Vmx > 1):7.2f} {np.mean(Vdmx > 1):8.2f} {np.mean(pos):6.2f} {np.median(V):8.1f} "
          f"{(np.median(Vd[pos]) if pos.any() else 0):10.2f} {np.percentile(Vd, 90):8.2f} {Vd.max():8.2f} {ratio:11.3f}")
print("\nshare of grid-weeks whose window max is > 1 (a pulse can pay), by quarter")
for q in range(4):
    sel = [x for L in by.values() for x in L if q * 26 < x[0] <= (q + 1) * 26]
    print(f"Q{q + 1}: dual {np.mean([x[2].max() > 1 for x in sel]):.2f}   pp_value x pi {np.mean([x[1].max() > 1 for x in sel]):.2f}")
