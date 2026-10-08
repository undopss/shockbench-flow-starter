import sys, time
from shockbench_flow.evaluation.cache import fq_quantiles, default_cache_dir
from shockbench_flow.hosting.tasks import task_generator
from shockbench_flow.policies.naive_fq import REPLICATIONS
t=time.time(); inst, params = task_generator(sys.argv[1]); fq_quantiles(inst, params, REPLICATIONS, cache_dir=str(default_cache_dir())); print(sys.argv[1], "fq done", time.time()-t, flush=True)
