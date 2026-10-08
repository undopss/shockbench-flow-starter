"""Classify fab-weeks of diag22.json: full (lots >= 90% cap0), wafer-limited (end stock < 10% cap0), else power/other
limited (wafers left over, lots under capacity). Prints % of fab-weeks per class and lots per fab."""
import json
import numpy as np
rows = json.load(open("outputs/task-22/diag22.json"))
meta = next(r["meta"] for r in json.load(open("outputs/task-22/gap22_full_0_2-5-0-1-53-26.json"))["rows"] if r["player"] == "oracle")
cap = np.array([f["cap0"] for f in meta["fabs"]])
for p in dict.fromkeys(r["player"] for r in rows):
    R = [r for r in rows if r["player"] == p]
    L = np.array([r["detail"]["lots_w"] for r in R])  # (ep, T, F)
    W = np.array([r["detail"]["wafer_stock_w"] for r in R])
    full = L >= 0.9 * cap
    wlim = (~full) & (W < 0.1 * cap)
    plim = (~full) & ~wlim
    print(f"\n{p}: % of fab-weeks  full / wafer-limited / wafers-left-but-not-run, mean end wafer stock (weeks of cap0)")
    for f, fm in enumerate(meta["fabs"]):
        print(f"  {fm['id']:20s} {fm['grid'] or '-':9s} {100*full[...,f].mean():5.0f} {100*wlim[...,f].mean():5.0f} {100*plim[...,f].mean():5.0f}"
              f"   {np.mean(W[...,f])/cap[f]:6.2f}")
    print(f"  {'ALL':30s} {100*full.mean():5.0f} {100*wlim.mean():5.0f} {100*plim.mean():5.0f}")
