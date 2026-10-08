"""Task 26 step 2: simple observable rules fitted on oracle episodes 0-19, checked on 20-39 (held out).

Rule G (grid stock): when the pool (grid + terminal) holds enough fuel, the oracle ends the week with the grid's
rationed fuel at psi I-bar + m weeks of burn (m fitted per grid as the train median), the rest at the terminal.
Rule C (crude/other fuels): the grid's own stock ends at m weeks of burn (fitted).
Rule F (fabs): the oracle's fab utilisation comes in runs; run-length stats of weeks >= 90% and <= 10% of capacity.
"""
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from an26 import D, load, pools  # noqa: E402


def runs(b):
    out, c = [], 0
    for x in b:
        if x:
            c += 1
        elif c:
            out.append(c)
            c = 0
    if c:
        out.append(c)
    return out


def main(task, ent, agent="mpc_fab3sell"):
    st = pickle.loads((D / f"{task}_static.pkl").read_bytes())
    O = load(task, ent, "oracle", range(40))
    A = load(task, ent, agent, range(40))
    tr, te = [n for n in O if n < 20], [n for n in O if n >= 20]
    P = pools(st)
    print(f"{task}: train {len(tr)} test {len(te)} episodes")
    print("Rule G/C: weeks with enough fuel in the pool (>= thr + 1 week of burn): grid end stock (I - thr)/burn")
    print("  pool              m(train)  test: |err|<0.1wk  <0.25wk  enough-fuel share | agent same stat: within 0.25 of m")
    for key, p in P.items():
        go, k = key
        if not p["terms"]:
            continue

        def stat(data, ns):
            v = []
            for n in ns:
                d = data[n]
                burn = p["share"] * d["G_bar"][:, go]
                pool = d["stock"][:, p["grid"]] + sum(d["stock"][:, t] for t in p["terms"])
                ok = pool >= p["thr"] + burn
                v.append(((d["stock"][:, p["grid"]] - p["thr"]) / burn)[ok])
            return np.concatenate(v) if v else np.zeros(0), np.mean(np.concatenate([[1.0]] + [x * 0 + 1 for x in v])) if v else 0

        vtr, _ = stat(O, tr)
        vte, _ = stat(O, te)
        if vtr.size < 20:
            continue
        m = float(np.median(vtr))
        n_ok = sum(1 for _ in vte)
        share = vte.size / (len(te) * O[te[0]]["stock"].shape[0])
        va, _ = stat(A, [n for n in te if n in A]) if A else (np.zeros(0), 0)
        ag = f"{np.mean(np.abs(va - m) < 0.25):6.1%}" if va.size else "  -"
        print(f"  {p['name']:16s} {m:7.2f}   {np.mean(np.abs(vte - m) < 0.1):8.1%} {np.mean(np.abs(vte - m) < 0.25):8.1%}"
              f" {share:10.1%}        | {ag}")
    print("\nRule F: fab utilisation runs (weeks); oracle vs agent on test episodes: mean run length >=90% / <=10%, "
          "share of weeks >= 90%")
    for fo, f in enumerate(st["fabs"]):
        line = f"  {st['nodes'][f][0]:18s}"
        for who, data in (("oracle", O), (agent, A)):
            ns = [n for n in te if n in data]
            hi, lo, sh = [], [], []
            for n in ns:
                u = data[n]["lots"][:, fo] / np.maximum(data[n]["fabcap"][:, fo], 1)
                hi += runs(u >= 0.9)
                lo += runs(u <= 0.1)
                sh.append(np.mean(u >= 0.9))
            line += f" {who}: hi-run {np.mean(hi) if hi else 0:5.1f} lo-run {np.mean(lo) if lo else 0:5.1f} hi {np.mean(sh):5.1%} |"
        print(line)


if __name__ == "__main__":
    main(*sys.argv[1:])
