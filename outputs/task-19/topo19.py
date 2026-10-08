"""Task 19: chip topology of a task's instance (fabs, their out-edges, OSATs, sinks), from episode 0 of root 0."""
import sys
from shockbench_flow_agent.scoring import EpisodeSet, _world

task = sys.argv[1] if len(sys.argv) > 1 else "full"
es = EpisodeSet.build(task, [0], entropy=0, n_jobs=1)
inst, omega, marks, fb = _world(task, 0, 0, *es._spec[3:])
N, K, E = inst.nodes, inst.commodities, inst.edges
print("fields of edge:", [a for a in dir(E[0]) if not a.startswith("_")])
print("fields of node:", [a for a in dir(N[0]) if not a.startswith("_")])
chipk = {i for i, k in enumerate(K) if "chip" in k.id or "wafer" in k.id}
for i, e in enumerate(E):
    ks = [K[k].id for k in (getattr(e, "K", None) or []) if k in chipk]
    if ks:
        print(f"edge {i:4d} {N[e.tail].id:>22s} -> {N[e.head].id:<22s} u={getattr(e,'u',None)} tau={getattr(e,'tau',None)} K={ks}")
for f in inst.fabs:
    fb_ = N[f].fab
    print("fab", N[f].id, "in", K[fb_.input].id, "out", K[fb_.product].id, "cap0", fb_.cap0, "tau", fb_.tau,
          "grid", None if fb_.grid is None else N[fb_.grid].id, "e", fb_.e, "stock", getattr(N[f], "stock", None))
for o in inst.osats:
    print("osat", N[o].id, vars(N[o].osat) if hasattr(N[o].osat, "__dict__") else N[o].osat, "stock", getattr(N[o], "stock", None))
for d in inst.demands:
    print("demand", N[d.node].id, K[d.k].id, "pi", d.pi, "dbar", getattr(d, "dbar", None))
