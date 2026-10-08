"""Task 19: chip topology of a task's instance (fabs, their chip out-edges, OSATs, sinks)."""
import sys
from shockbench_flow.hosting.tasks import task_generator

inst, params = task_generator(sys.argv[1] if len(sys.argv) > 1 else "full")
N, K, E = inst.nodes, inst.commodities, inst.edges
print("edge fields:", [a for a in dir(E[0]) if not a.startswith("_")])
print("node fields:", [a for a in dir(N[0]) if not a.startswith("_")])
print("fab fields:", [a for a in dir(N[inst.fabs[0]].fab) if not a.startswith("_")])
print("osat fields:", [a for a in dir(N[inst.osats[0]].osat) if not a.startswith("_")])
chipk = {i for i, k in enumerate(K) if "chip" in k.id or "wafer" in k.id}
for i, e in enumerate(E):
    ks = [K[k].id for k in (e.K or []) if k in chipk]
    if ks:
        print(f"edge {i:4d} {N[e.tail].id:>20s} -> {N[e.head].id:<20s} u={e.u0} tau={e.tau} K={ks}")
for f in inst.fabs:
    fb = N[f].fab
    print("fab", N[f].id, K[fb.input].id, "->", K[fb.product].id, "cap0", fb.cap0, "tau", fb.tau,
          "grid", None if fb.grid is None else N[fb.grid].id, "e", fb.e, )
for o in inst.osats:
    print("osat", N[o].id, N[o].osat)
for d in inst.demands:
    print("demand", N[d.node].id, K[d.k].id, "pi", d.pi, d)
