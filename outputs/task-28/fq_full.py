import time
t=time.time()
from shockbench_flow_agent.scoring import EpisodeSet, _world
es = EpisodeSet.build("full", [2], entropy=0, n_jobs=1)
task, entropy, regime, reps, cache = es._spec
_world(task, entropy, 2, reps, cache)
print("done", time.time()-t, flush=True)
