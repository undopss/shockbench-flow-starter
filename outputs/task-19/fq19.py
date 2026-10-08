"""Fill the F_Q disk cache for this machine's Python version with 4 workers (the home cache is keyed on 3.13.5)."""
import sys, time
from shockbench_flow_agent.scoring import EpisodeSet
for task in sys.argv[1:]:
    t = time.time()
    EpisodeSet.build(task, "dev" if task == "full" else 1, entropy=0, n_jobs=4)
    print(task, f"{time.time() - t:.0f} s", flush=True)
