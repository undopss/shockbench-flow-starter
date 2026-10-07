"""Task 6: per-week view of one fab under several runs (pickles from probe_week.py)."""
import pickle, sys
import numpy as np
from shockbench_flow.hosting.tasks import task_generator
inst, _ = task_generator('full'); nodes = inst.nodes; ks = [c.id for c in inst.commodities]
slot = {(s.node, s.k): i for i, s in enumerate(inst.stock_slots)}
D = {n: pickle.load(open(p, 'rb')) for n, p in zip(sys.argv[2::2], sys.argv[3::2])}
fi = [nodes[f].id for f in inst.fabs].index(sys.argv[1])
f = inst.fabs[fi]; fab = nodes[f].fab
gi = list(inst.grids).index(fab.grid); grid = nodes[fab.grid].grid
print(sys.argv[1], 'grid', nodes[fab.grid].id, 'cap0', fab.cap0, 'fuels', [ks[k] for k in grid.fuels])
win = slot[(f, fab.input)]
for name, d in D.items():
    print(f"--- {name}: J={d['J']/100:.4e}")
    print("wk  head   wafers   starts   E_fab   shed  " + "  ".join(f"{ks[k]}_stk" for k in grid.fuels))
    for t in range(0, d['lots'].shape[0], 4):
        head = d['G_bar'][t, gi] - d['y_bar'][t, gi]
        fs = "  ".join(f"{d['stock'][t, slot[(fab.grid, k)]]:9.0f}" for k in grid.fuels)
        print(f"{t+1:3d} {head:6.0f} {d['stock'][t, win]:9.0f} {d['lots'][t, fi]:8.0f} {d['energy'][t, fi]:7.1f} {d['shed'][t, gi]:7.0f}  {fs}")
