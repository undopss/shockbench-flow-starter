"""Fab energy per grid vs the fabs' full draw (G-bar - y-bar), and which fuel limits the shed weeks, from diag18 JSONs."""
import json
import sys
import numpy as np

files = sys.argv[1:]
data = [json.load(open(f)) for f in files]
grids = list(data[0][0]["grids"])
print("grid       " + "".join(f"{f.split('_')[-1][:12]:>26s}" for f in files))
print("           " + "".join(f"{'E/draw':>9s}{'shed wk':>9s}{'crude-lim':>8s}" for _ in files))
for g in grids:
    line = f"{g:10s} "
    for d in data:
        E = sum(sum(w["E"] for w in r["grids"][g]) for r in d)
        draw = sum(sum(w["G"] - w["ybar"] for w in r["grids"][g]) for r in d)
        sw = sum(sum(w["shed"] > 1e-6 for w in r["grids"][g]) for r in d)
        cl = sum(sum(any(k != "lng" and f["lim"] != "full" for k, f in w["fuels"].items()) and all(
            f["lim"] == "full" for k, f in w["fuels"].items() if k == "lng") for w in r["grids"][g]) for r in d)
        line += f"{E / max(draw, 1):9.3f}{sw / len(d):9.1f}{cl / len(d):8.1f}"
    print(line)
