"""Dump the Full instance's cost-relevant parameters (task 28)."""
import sys
from collections import Counter
from shockbench_flow.hosting.tasks import task_generator
task = sys.argv[1] if len(sys.argv) > 1 else "full"
inst, params = task_generator(task)
print("T", inst.T, "params", inst.params)
print("nodes by type", Counter(n.type for n in inst.nodes))
print("\nCOMMODITIES id unit pool v override disp")
for k, c in enumerate(inst.commodities):
    print(k, c.id, c.unit, c.pool, c.v, c.override, c.disposal_cost)
print("\nDEMANDS node k dbar pi backlog phi sigma shock")
bl = 0
for d in inst.demands:
    print(inst.nodes[d.node].id, inst.commodities[d.k].id, round(d.dbar, 2), d.pi, d.backlog, d.phi, d.sigma, d.shock)
print("\nFABS")
for f in inst.fabs:
    fb = inst.nodes[f].fab
    print(inst.nodes[f].id, fb)
print("\nOSATS")
for o in inst.osats:
    print(inst.nodes[o].id, inst.nodes[o].osat)
print("\nGRIDS")
for g in inst.grids:
    print(inst.nodes[g].id, inst.nodes[g].grid)
print("\nSTOCK SLOTS node k storage holding salvage supply")
for s in inst.stock_slots:
    print(inst.nodes[s.node].id, inst.commodities[s.k].id, s.storage, s.holding, s.salvage, s.supply)
print("\nEDGES modes", Counter(e.mode for e in inst.edges), "alt_of", sum(e.alt_of is not None for e in inst.edges))
print("lanes", len(inst.lanes), "alt lanes", sum(l.alt_of is not None for l in inst.lanes))
print("action slots", len(inst.action_slots), "override slots", len(inst.override_slots))
for c in inst.chokepoints:
    print(inst.nodes[c].id, inst.nodes[c].chokepoint)
print("prohibitions_at_reset", len(inst.prohibitions_at_reset))
print("grid priorities", Counter(inst.nodes[g].grid.priority for g in inst.grids))
