"""Task 6 probe: play an agent on one Full dev episode and dump per-week fab wafers/starts/energy and grid fuel."""
import sys, pickle
from pathlib import Path
import numpy as np
from shockbench_flow.dynamics.env import rollout
from shockbench_flow.hosting.tasks import task_generator
from shockbench_flow.policies.naive_fq import anchor_policy
from shockbench_flow_agent.local_eval import ANCHOR_REGIME, NO_ZIP_SHA256
from shockbench_flow_agent.scoring import EpisodeSet, _metered_shim, _policy_seed, _world
from shockbench_flow_agent.shim import load_agent_class, unload_agent

task, ep, agent, out = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
es = EpisodeSet.build(task, "dev", entropy=0, n_jobs=1)
_t, entropy, regime, reps, cache = es._spec
inst, omega, marks, fallback = _world(task, entropy, ep, reps, cache)
pseed = _policy_seed(entropy, ep, NO_ZIP_SHA256)
_, params = task_generator(task)
if agent == "naive":
    traj = rollout(inst, anchor_policy(inst, params, reps), omega, ANCHOR_REGIME, pseed, marks=marks, fallback=fallback)
else:
    root = str(Path(agent).resolve())
    shim = _metered_shim(load_agent_class(root, f"submission_{Path(root).stem}"), None)
    traj = rollout(inst, shim, omega, regime, pseed, marks=marks, fallback=fallback)
recs = traj.records
pickle.dump({"stock": np.array([r.stock for r in recs]), "lots": np.array([r.lots_started for r in recs]),
             "energy": np.array([r.energy for r in recs]), "shed": np.array([r.shed for r in recs]),
             "lost": np.array([r.lost for r in recs]), "demand": np.array([r.demand for r in recs]),
             "segment": [r.segment for r in recs], "J": traj.J_cents,
             "G_bar": np.asarray(marks.G_bar), "y_bar": np.asarray(marks.y_bar), "R": np.asarray(marks.R),
             "alpha": np.asarray(marks.alpha_bar)}, open(out, "wb"))
print("J", traj.J_cents)
