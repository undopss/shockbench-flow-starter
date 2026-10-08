"""Task 21: per-edge chip flows (M units/episode) of the agent vs the oracle LP capped at the agent's starts.
    uv run python outputs/task-21/routes21.py nolim [mode]
"""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
tag = sys.argv[1] if len(sys.argv) > 1 else "nolim"; mode = sys.argv[2] if len(sys.argv) > 2 else "capped"
rows = json.loads((HERE / f"play_{tag}.json").read_text()); bnd = json.loads((HERE / f"bound_{tag}.json").read_text())
A, O = {}, {}
for r in rows:
    for k, w in r["flows"].items():
        A[k] = A.get(k, 0) + sum(w) / len(rows)
    for k, w in bnd[str(r["episode"])][mode]["flows"].items():
        O[k] = O.get(k, 0) + sum(w) / len(rows)
keys = sorted(set(A) | set(O), key=lambda k: -abs(A.get(k, 0) - O.get(k, 0)))
print(f"{'stage':<22} {'tail':<18} {'head':<18} {'k':<13} {'agent':>7} {mode:>7} {'diff':>7}")
for k in keys[:45]:
    st, a, b, c = k.split("|")
    print(f"{st:<22} {a:<18} {b:<18} {c:<13} {A.get(k, 0) / 1e6:7.2f} {O.get(k, 0) / 1e6:7.2f} {(O.get(k, 0) - A.get(k, 0)) / 1e6:+7.2f}")
