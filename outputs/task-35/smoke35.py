"""Task 35 smoke test: play mpc_cq (its params) on one Full dev episode; every week also solve the chip LP with the cq
options on (exceptions surface here, the agent swallows them) and report CPU time and how the week-0 plans differ.

    uv run python outputs/task-35/smoke35.py full 0 3 30
"""
import importlib.util
import sys
import time
from pathlib import Path

import numpy as np


def main(task="full", entropy=0, episode=3, weeks=30):
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _label, _policy_seed, _metered_shim
    from shockbench_flow.disruption.sampler import sample_omega
    from shockbench_flow.hosting.tasks import task_generator
    from shockbench_flow.marks import compute_marks
    from shockbench_flow_agent.shim import load_agent_class

    root = Path("agents/mpc_cq")
    inst, gparams = task_generator(task)
    omega = sample_omega(inst, gparams, int(entropy), int(episode), _label(int(entropy)))
    marks = compute_marks(inst, omega)
    cls = load_agent_class(str(root), "submission_cq_smoke")
    mod = sys.modules[cls.__module__]
    stats = {"off": [], "on": [], "diff": [], "fails": 0}

    class Probe(cls):
        def act(self, observation):
            if int(observation["week"][0]) <= int(weeks) and self.chips is not None:
                ch = self.chips
                t0 = time.process_time(); p0 = ch.plan(observation); t1 = time.process_time()
                ch.cq_edges = ch.cq_drain = ch.cq_kappa = True
                try:
                    p1 = ch.plan(observation)
                except Exception as exc:  # noqa
                    import traceback; traceback.print_exc(); p1 = None
                t2 = time.process_time()
                ch.cq_edges = ch.cq_drain = ch.cq_kappa = False
                stats["off"].append(t1 - t0); stats["on"].append(t2 - t1)
                if p1 is None or p0 is None:
                    stats["fails"] += 1
                else:
                    stats["diff"].append(sum(abs(p1[s] - p0[s]) for s in p0))
            return super().act(observation)

    pseed = _policy_seed(int(entropy), int(episode), NO_ZIP_SHA256)
    traj = rollout(inst, _metered_shim(Probe, None), omega, "standard", pseed, marks=marks, fallback=None)
    print(f"J {traj.J_cents}  chip LP CPU off mean {np.mean(stats['off']):.3f} max {np.max(stats['off']):.3f}  "
          f"on mean {np.mean(stats['on']):.3f} max {np.max(stats['on']):.3f}  fails {stats['fails']}  "
          f"week-0 plan |diff| mean {np.mean(stats['diff']):,.0f} max {np.max(stats['diff']):,.0f}")


if __name__ == "__main__":
    import fire
    fire.Fire(main)
