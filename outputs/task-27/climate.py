"""Task 27, step 1: the disruption climate from omega (marks), on an own root (no agent needed).

    uv run python outputs/task-27/climate.py full 200 4 [entropy]

Per episode: chokepoint open o (T, C) and tanker kappa, source supply (T, S), grid G_bar (T, G), edge capacity u (T, E),
from ``marks.compute_marks``. Also the closure events (type 3 militarised / 7 weather) with onset and duration.
Writes outputs/task-27/climate_<task>_<n>.npz.
"""

import sys
import time

import numpy as np
from joblib import Parallel, delayed

ENTROPY = 27027


def episode(task, n, entropy):
    from shockbench_flow.hosting.tasks import scenario, task_generator
    from shockbench_flow.marks import compute_marks

    inst, _ = task_generator(task, None)
    om = scenario(task, n, entropy=entropy)
    m = compute_marks(inst, om)
    ty, tk, tg = np.asarray(om["ev_type"]), np.asarray(om["ev_target_kind"]), np.asarray(om["ev_target"])
    on, du = np.asarray(om["ev_onset"]), np.asarray(om["ev_duration"])
    keep = (on < m.T) & (on + du > 0)
    ev = np.stack([ty[keep], tk[keep], tg[keep], on[keep], du[keep]], 1).astype(float)
    return dict(o=np.asarray(m.o, np.float32), kappa=np.asarray(m.kappa, np.float32),
                supply=np.asarray(m.supply, np.float32), G=np.asarray(m.G_bar, np.float32),
                u=np.asarray(m.u, np.float32), ev=ev)


def main(task="full", n=200, n_jobs=4, entropy=ENTROPY):
    n, n_jobs, entropy = int(n), int(n_jobs), int(entropy)
    t0 = time.time()
    eps = Parallel(n_jobs=n_jobs, verbose=2)(delayed(episode)(task, i, entropy) for i in range(n))
    out = {k: np.stack([e[k] for e in eps]) for k in ("o", "kappa", "supply", "G", "u")}
    ev = np.concatenate([np.column_stack([np.full(len(e["ev"]), i), e["ev"]]) for i, e in enumerate(eps)])
    np.savez_compressed(f"outputs/task-27/climate_{task}_{n}.npz", ev=ev, **out)
    print(task, n, f"{time.time() - t0:.0f} s", {k: v.shape for k, v in out.items()})


if __name__ == "__main__":
    main(*sys.argv[1:])
