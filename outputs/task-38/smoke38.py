"""Task 38 smoke test: play agents/mpc_best (its params.json, every option on) on one Full episode and count, for
every week, chip LP calls that raise or return None (the agent swallows exceptions), and their CPU time.

    uv run python outputs/task-38/smoke38.py full 0 3
"""
import sys
import time
import traceback
from pathlib import Path

import numpy as np


def main(task="full", entropy=0, episode=3, agent="agents/mpc_best"):
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _label, _policy_seed, _metered_shim
    from shockbench_flow.disruption.sampler import sample_omega
    from shockbench_flow.hosting.tasks import task_generator
    from shockbench_flow.marks import compute_marks
    from shockbench_flow_agent.shim import load_agent_class

    inst, gparams = task_generator(task)
    omega = sample_omega(inst, gparams, int(entropy), int(episode), _label(int(entropy)))
    marks = compute_marks(inst, omega)
    cls = load_agent_class(str(Path(agent)), "submission_best_smoke")
    mod = sys.modules[cls.__module__]
    st = {"calls": 0, "exc": 0, "none": 0, "cpu": [], "weeks": set()}

    class Probe(cls):
        def act(self, observation):
            ch = self.chips
            if ch is not None and not getattr(ch, "_wrapped", False):
                orig = ch.plan

                def plan(obs):
                    st["calls"] += 1
                    st["weeks"].add(int(obs["week"][0]))
                    t0 = time.process_time()
                    try:
                        out = orig(obs)
                    except Exception:
                        st["exc"] += 1
                        traceback.print_exc()
                        raise
                    finally:
                        st["cpu"].append(time.process_time() - t0)
                    if out is None:
                        st["none"] += 1
                    return out

                ch.plan = plan
                ch._wrapped = True
            return super().act(observation)

    opts = {k: mod.PARAMS[k] for k in ("fb_kappa_ct", "cq_edges", "cq_drain", "cq_kappa", "nd_open")}
    pseed = _policy_seed(int(entropy), int(episode), NO_ZIP_SHA256)
    traj = rollout(inst, _metered_shim(Probe, None), omega, "standard", pseed, marks=marks, fallback=None)
    print(f"options {opts}")
    print(f"J {traj.J_cents}  chip LP calls {st['calls']} in {len(st['weeks'])} weeks, exceptions {st['exc']}, "
          f"None {st['none']}, CPU mean {np.mean(st['cpu']):.3f} max {np.max(st['cpu']):.3f} s")


if __name__ == "__main__":
    import fire
    fire.Fire(main)
