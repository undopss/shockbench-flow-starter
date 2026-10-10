"""Task 40: split the generation the pulse loses (best - nopulse) by mechanism, from pleak.py's JSON.

    uv run python outputs/task-40/split.py outputs/task-40/pleak_full_0_dev.json [a b]
"""
import json
import sys

import numpy as np

res = json.load(open(sys.argv[1]))
A, B = (sys.argv[2], sys.argv[3]) if len(sys.argv) > 3 else ("best", "nopulse")
a, b = res[A], res[B]
n = len(a)
print(f"{n} episodes, {A} - {B}, units of grid output per episode (USD = x VOLL 4.125e6)")
print(f"{'grid':9s} {'d gen':>8s} {'d fuelburn':>10s} {'d nonfuel':>9s} | fuel: {'d inflow':>8s} {'d dispT':>8s} {'d dispG':>8s} {'d end':>8s}"
      f" | {'lost USD':>10s} {'lost(<=shed wks)':>16s}")
tot = np.zeros(8)
for gi, g in enumerate(a[0]["grids"]):
    def S(rows, f):
        return float(np.mean([f(r["grids"][gi]) for r in rows]))
    dgen = S(a, lambda q: sum(q["gen"])) - S(b, lambda q: sum(q["gen"]))
    ks = list(g["fuels"])
    dfb = sum(S(a, lambda q: sum(q["fuels"][k]["burn"])) - S(b, lambda q: sum(q["fuels"][k]["burn"])) for k in ks)
    din = sum(S(a, lambda q: sum(q["fuels"][k]["inflow"])) - S(b, lambda q: sum(q["fuels"][k]["inflow"])) for k in ks)
    ddt = sum(S(a, lambda q: sum(q["fuels"][k]["dispT"])) - S(b, lambda q: sum(q["fuels"][k]["dispT"])) for k in ks)
    ddg = sum(S(a, lambda q: sum(q["fuels"][k]["dispG"])) - S(b, lambda q: sum(q["fuels"][k]["dispG"])) for k in ks)
    dend = din - dfb - ddt - ddg
    # generation not used in weeks with no shed (load < 1: the surplus of a full week)
    def surplus(q):
        return 0.0
    row = np.array([dgen, dfb, dgen - dfb, din, ddt, ddg, dend, -dgen * g["voll"]])
    tot += row
    print(f"{g['id']:9s} {dgen:8.0f} {dfb:10.0f} {dgen - dfb:9.0f} | fuel: {din:8.0f} {ddt:8.0f} {ddg:8.0f} {dend:8.0f} | {-dgen * g['voll']:10.3e}")
print(f"{'TOTAL':9s} {tot[0]:8.0f} {tot[1]:10.0f} {tot[2]:9.0f} | fuel: {tot[3]:8.0f} {tot[4]:8.0f} {tot[5]:8.0f} {tot[6]:8.0f} | {tot[7]:10.3e}")
