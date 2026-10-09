Status: measuring (Full devpick, mpc_jpow)

Plan: agents/mpc_cq = mpc_jpow + three chip-LP options in chips.py (off by default): cq_edges (shared capacity rows on every later edge of chip routes, net of cargo already bound for it), cq_drain (queued chip cargo drains FIFO at min(next-edge, kappa_ct) shares, like jp_qedge), cq_kappa (routes share kappa_ct at each chokepoint). Static count: 29 (commodity, later edge) groups shared by chip routes with different first edges (matches Andrii). Smoke test on Full dev ep 3: options on solve every week, chip LP CPU 0.15 s mean / 0.23 max (same as off).
