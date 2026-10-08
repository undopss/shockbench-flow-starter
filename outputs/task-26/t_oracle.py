import time, sys
from shockbench_flow.disruption.sampler import sample_omega
from shockbench_flow.hosting.tasks import task_generator, split_label
from shockbench_flow.marks import compute_marks
from shockbench_flow.oracle.lp import ORACLE_METHOD, build_lp, solve_oracle
task, ent, n = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
t=time.time()
inst, params = task_generator(task)
omega = sample_omega(inst, params, ent, n, split_label(ent)); marks = compute_marks(inst, omega)
print("world", time.time()-t, flush=True); t=time.time()
model = build_lp(inst, marks); print("build", time.time()-t, len(model.columns), model.T, flush=True); t=time.time()
res = solve_oracle(model, method=ORACLE_METHOD); print("solve", time.time()-t, res.J_cents, res.status, flush=True)
