"""Task 42 smoke: play one Full dev episode with mpc_msg's message options on and count what _msg_obs added."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(ep=0, lag=8, mid=2.0):
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import EpisodeSet, _metered_shim, _policy_seed, _world
    from shockbench_flow_agent.shim import load_agent_class

    es = EpisodeSet.build("full", "dev", entropy=0, n_jobs=1)
    task, entropy, regime, reps, cache = es._spec
    inst, omega, marks, fallback = _world(task, entropy, int(ep), reps, cache)
    cls = load_agent_class(str(Path("agents/mpc_msg").resolve()), "submission_mpc_msg")
    mod = sys.modules[cls.__module__]
    mod.PARAMS.update(msg_ties_lag=int(lag), msg_mid_score=float(mid))
    stats = dict(weeks=0, pend_added=0, warn_raised=0, errors=0)

    class Probe(cls):
        def _msg_obs(self, obs):
            try:
                out = super()._msg_obs(obs)
            except Exception as err:
                stats["errors"] += 1
                print("error", repr(err))
                raise
            stats["weeks"] += 1
            stats["pend_added"] += int(np.sum(out.get("pending_prohibitions.edge.observed", [])) -
                                       np.sum(obs.get("pending_prohibitions.edge.observed", [])))
            stats["warn_raised"] += int(np.sum(np.asarray(out["warning.score"]) != np.asarray(obs["warning.score"])))
            return out

    shim = _metered_shim(Probe, None)
    pseed = _policy_seed(entropy, int(ep), NO_ZIP_SHA256)
    traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=fallback)
    print("edges in static vs instance:", len(inst.edges), "J", traj.J_cents, stats)


if __name__ == "__main__":
    main(*sys.argv[1:])
