import sys
import numpy as np
from shockbench_flow_agent.scoring import EpisodeSet, _world
es = EpisodeSet.build("full", [int(sys.argv[1])], entropy=0, n_jobs=1)
inst, omega, marks, fb = _world("full", 0, int(sys.argv[1]), *es._spec[3:])
print([a for a in dir(marks) if not a.startswith("_")])
N, K, E = inst.nodes, inst.commodities, inst.edges
for name in ("u", "u_eff", "cap", "kappa"):
    if hasattr(marks, name):
        print(name, np.asarray(getattr(marks, name)).shape)
U = np.asarray(marks.u) if hasattr(marks, "u") else None
P = np.asarray(marks.prohibited) if hasattr(marks, "prohibited") else None
print("prohibited shape", None if P is None else P.shape)
for i, e in enumerate(E):
    if N[e.tail].id in sys.argv[2].split(","):
        ks = [K[k].id for k in e.K]
        row = U[:, i] if U is not None else None
        print(f"{i} {N[e.tail].id}->{N[e.head].id} {ks} u0 {e.u0:.0f} u mean {row.mean():.0f} min {row.min():.0f} max {row.max():.0f}")
