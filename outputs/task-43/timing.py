"""Task 43: CPU per week of the pulse planner and of the whole act, for a params override, on one Full episode.

    uv run python outputs/task-43/timing.py <agent folder> '<params json>' [entropy] [episode] [weeks]
"""
import json, shutil, sys, time
from pathlib import Path
import numpy as np


def main(agent, params, entropy=0, n=0, weeks=40):
    entropy, n, weeks = int(entropy), int(n), int(weeks)
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _label, _metered_shim, _policy_seed
    from shockbench_flow.disruption.sampler import sample_omega
    from shockbench_flow.hosting.tasks import task_generator
    from shockbench_flow.marks import compute_marks
    from shockbench_flow_agent.shim import load_agent_class
    tmp = Path("outputs/task-43/tmp_timing") / str(abs(hash(params)) % 10**8)
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(agent, tmp, ignore=shutil.ignore_patterns("__pycache__"))
    p = json.loads((Path(agent) / "params.json").read_text())
    p.update(json.loads(params))
    (tmp / "params.json").write_text(json.dumps(p))
    inst, gparams = task_generator("full")
    omega = sample_omega(inst, gparams, entropy, n, _label(entropy))
    marks = compute_marks(inst, omega)
    cls = load_agent_class(str(tmp.resolve()), "t_agent")
    mod = sys.modules[cls.__module__]
    PP = mod._pplan.PulsePlanner
    pt, at = [], []
    orig_plan = PP.plan

    def plan(self, *a, **k):
        PP._last = self
        t = time.process_time()
        r = orig_plan(self, *a, **k)
        pt.append(time.process_time() - t)
        return r
    PP.plan = plan
    orig_act = cls.act

    def act(self, obs):
        t = time.process_time()
        r = orig_act(self, obs)
        at.append(time.process_time() - t)
        if len(at) >= weeks:
            raise SystemExit
        return r
    cls.act = act
    shim = _metered_shim(cls, None)
    try:
        rollout(inst, shim, omega, "standard", _policy_seed(entropy, n, NO_ZIP_SHA256), marks=marks, fallback=None)
    except SystemExit:
        pass
    pt, at = np.array(pt), np.array(at)
    pl = getattr(PP, "_last", None)
    if pl is not None and pl.sc_ratio:
        ids = [nd.id for nd in inst.nodes]
        keys = set()
        for gr in pl.grids:
            for fu in gr["fuels"]:
                if fu["term"] is not None:
                    keys |= {(fu["term"], fu["k"]), (gr["node"], fu["k"])}
        for key in sorted(keys):
            h = np.array(pl.sc_ratio.get(key, []))
            if len(h):
                print(f"  {ids[key[0]]:14s} k{key[1]} n {len(h):3d} mean {h.mean():.3f} std {h.std():.3f} "
                      f"zero {np.mean(h < 0.05):.2f} |1-r|>0.1 {np.mean(np.abs(h - 1) > 0.1):.2f}", flush=True)
    print(f"{params}: weeks {len(at)} act max {at.max():.2f} med {np.median(at):.2f} | pplan max {pt.max():.2f} "
          f"med {np.median(pt):.2f}", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
