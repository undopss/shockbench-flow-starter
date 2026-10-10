import sys, time
from shockbench_flow_agent.scoring import EpisodeSet
t = time.time()
for root in sys.argv[1:]:
    es = EpisodeSet.build("full", 20, entropy=int(root), n_jobs=3)
    print(root, "ready", round(time.time() - t), flush=True)
