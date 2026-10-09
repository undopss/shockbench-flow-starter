"""Task 28: static ceilings read straight from the instance (no episode needed)."""
import sys
from shockbench_flow.hosting.tasks import task_generator
from shockbench_flow.dynamics.sim import initial_stock
task = sys.argv[1] if len(sys.argv) > 1 else "full"
inst, _ = task_generator(task)
N, K = inst.nodes, inst.commodities
sup = set(inst.supply_nodes)
I0 = initial_stock(inst)
smax = sum((s.storage or 0) * s.salvage for s in inst.stock_slots if s.node not in sup)
print(f"salvage if every non-supply slot ends at I^max: {smax/1e12:.5f} T")
print("\nGRID headroom: G-bar - y-bar vs fab nameplate draw (GWh/wk)")
for gi, g in enumerate(inst.grids):
    gr = N[g].grid
    draw = sum(N[inst.fabs[fi]].fab.e * N[inst.fabs[fi]].fab.cap0 for fi in inst.grid_fabs[gi])
    print(f"  {N[g].id:8s} G-bar {gr.deliverable:9.0f} y-bar {gr.base_load:9.0f} headroom {gr.deliverable-gr.base_load:7.0f} "
          f"fab draw {draw:6.0f} at alpha 1.25 {1.25*draw:6.0f}  shares {dict((K[k].id if k is not None else None, v) for k, v in gr.shares.items())}")
    for k in gr.fuels:
        s = inst.slot_index[(g, k)]
        burn = gr.shares[k] * gr.deliverable
        print(f"      {K[k].id:8s} burn {burn:9.1f}/wk  I0 {I0[s]:11.0f} ({I0[s]/burn:5.1f} wk)  I^max {inst.stock_slots[s].storage:11.0f}"
              f" ({inst.stock_slots[s].storage/burn:5.1f} wk)  psi*Ibar {inst.params.psi*gr.ibar.get(k, 0):9.0f}")
print("\nsupply of fuel per week (sources) vs burn")
tot = {}
for s in inst.stock_slots:
    if s.node in sup:
        tot[K[s.k].id] = tot.get(K[s.k].id, 0) + s.supply
burn = {}
for g in inst.grids:
    gr = N[g].grid
    for k in gr.fuels:
        burn[K[k].id] = burn.get(K[k].id, 0) + gr.shares[k] * gr.deliverable
for k in tot:
    print(f"  {k:8s} supply {tot[k]:11.0f}/wk   nominal burn {burn.get(k, 0):11.0f}/wk")
