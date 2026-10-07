"""Task 6 probe: per grid headroom (G_bar - y_bar) vs the fabs' full-capacity draw, and fab starts, in one episode."""
import json, sys
import numpy as np
from shockbench_flow.hosting.tasks import task_generator
from shockbench_flow.disruption.sampler import sample_omega
from shockbench_flow.marks import compute_marks
from shockbench_flow_agent.scoring import _label

ep = int(sys.argv[1]); bd = sys.argv[2] if len(sys.argv) > 2 else None
inst, params = task_generator('full')
omega = sample_omega(inst, params, 0, ep, _label(0))
m = compute_marks(inst, omega)
nodes = inst.nodes
Gb, yb, R = np.asarray(m.G_bar), np.asarray(m.y_bar), np.asarray(m.R)
ab = np.asarray(m.alpha_bar)
print("weeks", Gb.shape)
for gi, g in enumerate(inst.grids):
    grid = nodes[g].grid
    fis = inst.grid_fabs[gi]
    need = sum(nodes[inst.fabs[fi]].fab.e * nodes[inst.fabs[fi]].fab.cap0 for fi in fis)
    print(f"{nodes[g].id:10s} prio={grid.priority} G_bar={Gb[:,gi].mean():9.1f} y_bar={yb[:,gi].mean():9.1f} "
          f"head={np.mean(Gb[:,gi]-yb[:,gi]):8.1f} min_head={np.min(Gb[:,gi]-yb[:,gi]):8.1f} fab_need={need:8.1f} "
          f"pos_weeks={np.mean(Gb[:,gi]-yb[:,gi]>1e-6):.2f} mean_pos_head={np.mean(np.maximum(Gb[:,gi]-yb[:,gi],0)):8.1f} "
          f"shares={dict((str(k),round(v,2)) for k,v in grid.shares.items())} rationed={grid.rationed} fabs={[nodes[inst.fabs[fi]].id for fi in fis]}")
rows = json.load(open(bd)) if bd else []
r = next((r for r in rows if r['episode'] == ep), None)
for fi, f in enumerate(inst.fabs):
    fab = nodes[f].fab
    cap = (ab[:, fi] * R[:, fi] * fab.cap0).sum()
    s = f"{nodes[f].id:22s} grid={str(fab.grid):8s} e={fab.e:.4f} cap0={fab.cap0:8.0f} tau={fab.tau} sum_cap={cap:10.0f}"
    if r:
        s += f" agent={r['detail']['lots_started'][fi]:10.0f} naive={r['naive_detail']['lots_started'][fi]:10.0f}"
    print(s)
