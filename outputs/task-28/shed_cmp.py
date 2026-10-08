"""Task 28: agent vs oracle vs naive shed per grid on the devpick-6 episodes (from task 20's dev-20 JSON)."""
import json
import numpy as np
g = {r['episode']: r for r in json.load(open('outputs/task-20/gap17v2_full_0_dev_mpc_fab3sell.json'))}
grids = ['tw', 'kr', 'jp', 'cn', 'us', 'eu', 'sea', 'in']
A = np.zeros(8); O = np.zeros(8); N = np.zeros(8)
for e in [2, 5, 0, 1, 53, 26]:
    r = g[e]
    A += np.array(r['detail']['shed']) / 6; O += np.array(r['oracle_detail']['shed']) / 6
    N += np.array(r['naive_detail']['shed']) / 6
    sw = np.array(r['detail']['shed_w']); ow = np.array(r['oracle_detail']['shed_w'])
    print(e, "US shed weeks agent", list(np.nonzero(sw[:, 4] > 1)[0] + 1), "oracle", list(np.nonzero(ow[:, 4] > 1)[0] + 1))
print("grid      naive     agent    oracle (GWh/ep)")
for i, gn in enumerate(grids):
    print(f"{gn:4s} {N[i]:9.0f} {A[i]:9.0f} {O[i]:9.0f}")
