"""Does agents/scen play like the package's mpc_scen? Per-episode cost against outputs/baselines_<task>_<root>_<n>.json.

    python outputs/scen_fidelity.py small 12345 64 8 4    # the first 8 of those 64 episodes, 4 workers
"""

import json
import sys
from pathlib import Path

import numpy as np
from shockbench_flow_agent.scoring import EpisodeSet


def main(task, entropy, n_ref, n_eps, n_jobs):
    entropy, n_ref, n_eps, n_jobs = int(entropy), int(n_ref), int(n_eps), int(n_jobs)
    ref = json.loads(Path(f"outputs/baselines_{task}_{entropy}_{n_ref}.json").read_text())["mpc_scen"]["J"][:n_eps]
    es = EpisodeSet.build(task, list(range(n_eps)), entropy=entropy, n_jobs=n_jobs, verbose=False)
    rows = es.play(str(Path("agents/scen").resolve()), n_jobs=n_jobs)
    J = [r["J_policy_cents"] for r in rows]
    for n, (a, b, r) in enumerate(zip(J, ref, rows)):
        print(f"episode {n}: port {a} cents, mpc_scen {b}, diff {(a - b) / b:+.6%}, fallback weeks {r['fallback_weeks']}"
              f"{', first error ' + r['first_error'] if r['first_error'] else ''}")
    print(f"identical: {sum(a == b for a, b in zip(J, ref))} of {n_eps}; total diff "
          f"{(np.sum(J) - np.sum(ref)) / np.sum(ref):+.6%}; RSS port {es.rss(J)['rss_all']:.4f} vs {es.rss(ref)['rss_all']:.4f}")


if __name__ == "__main__":
    main(*sys.argv[1:])
