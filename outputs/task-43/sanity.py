"""Task 43: the scenario enumeration raises nothing and plays the same as the one-forecast plan when every future is
the forecast. Plays one Full dev episode for 60 weeks with pp_scen_K, counting exceptions and changed releases."""
import json, shutil, sys, traceback
from pathlib import Path
import numpy as np


def main(K=8, n=0, weeks=60):
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _label, _metered_shim, _policy_seed
    from shockbench_flow.disruption.sampler import sample_omega
    from shockbench_flow.hosting.tasks import task_generator
    from shockbench_flow.marks import compute_marks
    from shockbench_flow_agent.shim import load_agent_class
    tmp = Path("outputs/task-43/tmp_sanity")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree("agents/mpc_cpu", tmp, ignore=shutil.ignore_patterns("__pycache__"))
    p = json.loads(Path("agents/mpc_best/params.json").read_text()) | {"pulse_weeks": 1.0, "pp_scen_K": int(K)}
    (tmp / "params.json").write_text(json.dumps(p))
    inst, gparams = task_generator("full")
    omega = sample_omega(inst, gparams, 0, int(n), _label(0))
    cls = load_agent_class(str(tmp.resolve()), "s_agent")
    PP = sys.modules[cls.__module__]._pplan.PulsePlanner
    stats = {"calls": 0, "exc": 0, "scen": 0, "changed": 0}
    orig = PP._enum

    def en(self, gr, ctrl, base, ehat, ybar, V, obs):
        stats["calls"] += 1
        try:
            res = orig(self, gr, ctrl, base, ehat, ybar, V, obs)
        except Exception:
            stats["exc"] += 1
            traceback.print_exc()
            raise
        on = self.scen_on
        self.scen_on = False
        det = orig(self, gr, ctrl, base, ehat, ybar, V, obs)
        self.scen_on = on
        if any(abs(res[k] - det[k]) > 1e-6 for k in res):
            stats["changed"] += 1
        return res
    PP._enum = en
    orig_act = cls.act
    cnt = [0]

    def act(self, obs):
        cnt[0] += 1
        if cnt[0] > int(weeks):
            raise SystemExit
        return orig_act(self, obs)
    cls.act = act
    try:
        rollout(inst, _metered_shim(cls, None), omega, "standard", _policy_seed(0, int(n), NO_ZIP_SHA256),
                marks=compute_marks(inst, omega), fallback=None)
    except SystemExit:
        pass
    print(stats, flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
