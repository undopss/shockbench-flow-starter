"""Task 30: agent (diag30 json) vs oracle (oracle30 json) per fab grid and fuel, per episode means."""
import json
import sys
import numpy as np

ag = {r["episode"]: r for r in json.load(open(sys.argv[1]))}
orc = {r["episode"]: r for r in json.load(open(sys.argv[2]))}
eps = [e for e in orc if e in ag]
print(f"episodes {eps}; GWh per episode unless said")
print(f"{'grid':9s} {'fuel':7s} {'need':>8s} | {'out ag':>8s} {'out or':>8s} | {'shortwk ag':>10s} {'or':>5s} | "
      f"{'grid stk ag':>11s} {'or':>6s} | {'term stk or':>11s} (weeks of burn)")
for g in ("grid_jp", "grid_cn", "grid_sea", "grid_eu", "grid_kr", "grid_tw"):
    for f in orc[eps[0]]["grids"][g]["fuels"]:
        need = np.mean([np.sum(orc[e]["grids"][g]["fuels"][f]["cap"]) for e in eps])
        oo = np.mean([np.sum(orc[e]["grids"][g]["fuels"][f]["G"]) for e in eps])
        ao = np.mean([sum(w["av"] for w in ag[e]["grids"][g]["fuels"][f]) for e in eps])
        osw = np.mean([sum(1 for c, G in zip(orc[e]["grids"][g]["fuels"][f]["cap"], orc[e]["grids"][g]["fuels"][f]["G"])
                           if c - G > 1e-3 * c) for e in eps])
        asw = np.mean([sum(1 for w in ag[e]["grids"][g]["fuels"][f] if w["short"] > 1e-3 * w["cap"]) for e in eps])
        burn = need / 104
        og = np.mean([np.mean(orc[e]["grids"][g]["fuels"][f]["Igrid"]) for e in eps]) / burn
        ot = np.mean([np.mean(orc[e]["grids"][g]["fuels"][f]["Iterm"]) for e in eps]) / burn
        agst = np.mean([np.mean([w["pre"] - w["av"] for w in ag[e]["grids"][g]["fuels"][f]]) for e in eps]) / burn
        print(f"{g:9s} {f:7s} {need:8.0f} | {ao:8.0f} {oo:8.0f} | {asw:10.1f} {osw:5.1f} | {agst:11.2f} {og:6.2f} | {ot:11.2f}")
    ofE = np.mean([np.sum(orc[e]["grids"][g]["fabE"]) for e in eps])
    afE = np.mean([np.sum(ag[e]["grids"][g]["fabE"]) for e in eps])
    oshed = np.mean([np.sum(orc[e]["grids"][g]["ysh"]) for e in eps])
    ashed = np.mean([np.sum(ag[e]["grids"][g]["shed"]) for e in eps])
    orun = np.mean([sum(1 for v in orc[e]["grids"][g]["fabE"] if v > 0.5 * max(orc[e]["grids"][g]["fabE"])) for e in eps])
    arun = np.mean([sum(1 for v in ag[e]["grids"][g]["fabE"] if v > 0.5 * max(ag[e]["grids"][g]["fabE"])) for e in eps])
    print(f"   {g}: fab energy agent {afE:8.0f} oracle {ofE:8.0f} | home shed agent {ashed:8.0f} oracle {oshed:8.0f} | "
          f"fab weeks >50% agent {arun:5.1f} oracle {orun:5.1f}")
print("\nsources: supply / oracle lift per week")
for k in orc[eps[0]]["src"]:
    v = np.mean([orc[e]["src"][k] for e in eps], axis=0)
    print(f"  {k:24s} supply {v[0]:8.0f} oracle lift {v[1]:8.0f}")
