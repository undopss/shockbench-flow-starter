"""Task 6: solve the clairvoyant LP of one Full dev episode and sum its served/lost per sink, starts per fab, shed per grid."""
import sys, pickle
from collections import defaultdict
import numpy as np
from shockbench_flow.hosting.tasks import task_generator
from shockbench_flow.disruption.sampler import sample_omega
from shockbench_flow.marks import compute_marks
from shockbench_flow.oracle.lp import ORACLE_METHOD, build_lp, solve_oracle
from shockbench_flow_agent.scoring import _label

ep, out = int(sys.argv[1]), sys.argv[2]
inst, params = task_generator('full')
marks = compute_marks(inst, sample_omega(inst, params, 0, ep, _label(0)))
model = build_lp(inst, marks)
res = solve_oracle(model, method=ORACLE_METHOD)
z = res.x
agg = defaultdict(float)
weekly = defaultdict(lambda: np.zeros(inst_T)) if False else None
T = len(np.asarray(marks.G_bar))
per = {"p": np.zeros((T, len(inst.fabs))), "E": np.zeros((T, len(inst.fabs))), "D": np.zeros((T, len(inst.demands))),
       "U": np.zeros((T, len(inst.demands))), "ysh": np.zeros((T, len(inst.grids)))}
xflow = defaultdict(float)
for i, key in enumerate(model.keys):
    tag = key[0]
    if tag in per:
        per[tag][key[1] - 1 if key[1] >= 1 else key[1], key[2]] += z[i]
    elif tag == "x":
        xflow[(key[2], key[3])] += z[i]
pickle.dump({"per": per, "x": dict(xflow), "J": res.J_cents}, open(out, "wb"))
print("J", res.J_cents, "weeks key sample", model.keys[0])
