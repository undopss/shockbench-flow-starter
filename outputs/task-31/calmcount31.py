"""Task 31: count the weeks mpc_calm's switch calls calm on one Full episode (and check it raises nothing).

    uv run python outputs/task-31/calmcount31.py full 0 2 <agent folder with calm_switch set>
"""
import sys
from pathlib import Path


def main(task, entropy, n, agent_root):
    from shockbench_flow.disruption.sampler import sample_omega
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow.hosting.tasks import task_generator
    from shockbench_flow.marks import compute_marks
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _label, _metered_shim, _policy_seed
    from shockbench_flow_agent.shim import load_agent_class

    entropy, n = int(entropy), int(n)
    inst, gparams = task_generator(task)
    omega = sample_omega(inst, gparams, entropy, n, _label(entropy))
    cls = load_agent_class(str(Path(agent_root).resolve()), "submission_calmcount")
    log = []
    orig_calm, orig_apply = cls._calm, cls._apply_calm

    def calm(self, obs):
        c = orig_calm(self, obs)
        log.append(int(c))
        return c

    def apply(self, obs):
        orig_apply(self, obs)  # unguarded here, so an exception shows
    cls._calm, cls._apply_calm = calm, apply
    traj = rollout(inst, _metered_shim(cls, None), omega, "standard", _policy_seed(entropy, n, NO_ZIP_SHA256),
                   marks=compute_marks(inst, omega), fallback=None)
    print("J", traj.J_cents / 1e14, "T; calm weeks", sum(log), "of", len(log), "".join(map(str, log)))


if __name__ == "__main__":
    main(*sys.argv[1:])
