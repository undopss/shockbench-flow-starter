"""Chip MPC: one linear program over the next H weeks for every wafer and chip shipment.

The simulator runs fabs and OSATs on its own (a fab starts every wafer on hand up to its capacity, an OSAT packages
every raw chip up to its throughput), so the plan only chooses shipments: wafers from the materials to the fabs, raw
chips from the fabs to the OSATs, finished chips from the OSATs to the sinks. The LP follows each (node, commodity)
stock week by week:

    stock[t] = stock[t-1] + arrivals[t] + produced[t] - shipped[t] - started_or_served[t] - disposed[t]

with shipments arriving after their route's lead time, fab starts turning into raw chips tau_f weeks later, OSAT
starts into finished chips tau_o weeks later, work in process and shipments already under way as fixed arrivals, the
storage cap (stock above it is disposed of at the commodity's disposal cost), and a shipment leaving only stock that
was there at the end of last week, as in the simulator. Every sink is lost-sales: each unit of forecast demand not
served costs its pi (about 50 k USD for leading-edge chips, 10 k for mature ones), against freight of a few USD.

The present graph (capacities, lead times, open fractions, prohibitions, fab capacity and OSAT throughput) is assumed
to persist over the window; announced prohibitions close their slots from their effective week. Demand beyond the
8-week forecast repeats its last observed week. Fabs are assumed to get the energy they ask for (the energy MPC keeps
the grids within ~0.2 % of the clairvoyant plan's power shed).
"""

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

CHIP_TYPES = ("material", "fab", "osat", "sink")


class ChipPlanner:
    def __init__(self, config, H=24, fab_cap_mode="full", recent_weeks=4, growth=1.25, wafer_buffer=0.0,
                 buffer_cost=1000.0, sell_buffer=False, sell_end=False, sell_frac=0.9, kappa_ct=False):
        self.fab_cap_mode, self.recent_weeks, self.growth = fab_cap_mode, recent_weeks, growth
        # keep wafer_buffer weeks of nameplate starts on hand at every fab (soft, buffer_cost USD per missing wafer and
        # week): a fab only starts the wafers it holds, so a week with spare power and no wafers is power thrown away
        self.wafer_buffer, self.buffer_cost = float(wafer_buffer), float(buffer_cost)
        # task 19 (both off by default): sell_buffer solves once without the buffer and, at a fab whose planned starts
        # stay under sell_frac of its LP capacity (its chips can't be sold, not power-limited), shrinks the buffer to
        # wafer_buffer weeks of those planned starts; sell_end drops the buffer in weeks whose lots can't reach a sink
        # before the episode ends (fab tau + OSAT tau + two shipping weeks)
        self.sell_buffer, self.sell_end, self.sell_frac = bool(sell_buffer), bool(sell_end), float(sell_frac)
        # task 25 (off by default): container lots queued at a chokepoint drain FIFO at its kappa_ct (all chip LP
        # commodities are container cargo), and the LP's new shipments through it wait behind that queue
        self.kappa_ct = bool(kappa_ct)
        static, layout = config["static"], config["layout"]
        inst = static["instance"]
        nodes = inst["nodes"]
        self.H = H
        self.T = int(static["T"])
        commodities = static["commodities"]["id"]
        self.edges = static["edges"]
        lanes, slots = static["lanes"], static["action_slots"]
        node_type = [n.get("type") for n in nodes]
        disposal_cost = {c["id"]: float(c.get("disposal_cost", 0.0)) for c in inst["commodities"]}

        # stock positions the LP follows: every (node, k) slot of a material, fab, osat or sink
        self.stock_index = {tuple(row): i for i, row in enumerate(layout["stock_slots"])}
        self.supply_index = {tuple(row): i for i, row in enumerate(layout["supply_slots"])}
        self.pos = []  # dicts: node, k, cap, hold, disp, kind
        self.pos_index = {}
        for (node, k) in self.stock_index:
            kind = node_type[node]
            if kind not in CHIP_TYPES:
                continue
            spec = nodes[node].get("stock", {}).get(commodities[k], {})
            self.pos_index[(node, k)] = len(self.pos)
            self.pos.append({
                "node": node, "k": k, "kind": kind, "cap": float(spec.get("storage", np.inf) or np.inf),
                "hold": float(spec.get("holding_cost", 0.0) or 0.0), "disp": disposal_cost.get(commodities[k], 0.0),
            })
        chip_k = {p["k"] for p in self.pos}

        # fabs: wafer position -> product position, lead time
        self.fabs = []
        for f_pos, node in enumerate(layout["fabs"]):
            fab = nodes[node]["fab"]
            kin, kout = commodities.index(fab["input"]), commodities.index(fab["product"])
            if (node, kin) in self.pos_index and (node, kout) in self.pos_index:
                g = fab.get("grid")
                gpos = None
                if g is not None:
                    gnode = next((i for i, n in enumerate(nodes) if n.get("id") == g), None)
                    gpos = list(layout["grids"]).index(gnode) if gnode in list(layout["grids"]) else None
                self.fabs.append({"pos": f_pos, "in": self.pos_index[(node, kin)], "out": self.pos_index[(node, kout)],
                                  "tau": int(fab["tau"]), "cap0": float(fab["cap0"]), "node": node, "grid_pos": gpos,
                                  "e": float(fab.get("e", 0.0))})
        # osats: (raw position, finished position) pairs sharing one throughput
        self.osats = []
        for o_pos, node in enumerate(layout["osats"]):
            osat = nodes[node]["osat"]
            pairs = []
            for raw, pk in osat["packages"].items():
                kr, kp = commodities.index(raw), commodities.index(pk)
                if (node, kr) in self.pos_index and (node, kp) in self.pos_index:
                    pairs.append((self.pos_index[(node, kr)], self.pos_index[(node, kp)]))
            if pairs:
                self.osats.append({"pos": o_pos, "pairs": pairs, "tau": int(osat["tau"]), "thr0": float(osat["thr"])})
        # sinks: demand row -> position, pi
        self.sinks = []
        sk = static["sinks"]
        pi_of = {(n, k): float(p) for n, k, p in zip(sk["node"], sk["k"], sk["pi"])}
        dbar = {}
        for node, n in enumerate(nodes):
            for kname, d in (n.get("sink", {}) or {}).get("demand", {}).items():
                dbar[(node, commodities.index(kname))] = float(d.get("dbar", 0.0))
        for row, (node, k) in enumerate(layout["demands"]):
            if (node, k) in self.pos_index:
                self.sinks.append({"row": row, "pos": self.pos_index[(node, k)], "pi": pi_of.get((node, k), 0.0),
                                   "dbar": dbar.get((node, k), 0.0)})
        # materials: supply refills the stock up to storage
        self.materials = [i for i, p in enumerate(self.pos) if p["kind"] == "material"]

        # LP slots: chip slots from one followed position to another (a lane counts as one pipe)
        self.lp_slots = []
        for s, (edge, k, lane) in enumerate(zip(slots["edge"], slots["k"], slots["lane"])):
            if k not in chip_k:
                continue
            route = list(lanes["edges"][lane]) if lane is not None else [edge]
            src = self.pos_index.get((self.edges["tail"][route[0]], k))
            dst = self.pos_index.get((self.edges["head"][route[-1]], k))
            if src is None or dst is None:
                continue
            chk = list(lanes["chokepoints"][lane]) if lane is not None else []
            # edges up to and including the one into each chokepoint of the route (its reach time)
            pre = {}
            for i_e, e_ in enumerate(route):
                if self.edges["head"][e_] in chk:
                    pre[self.edges["head"][e_]] = route[:i_e + 1]
            self.lp_slots.append({"slot": s, "k": k, "route": route, "src": src, "dst": dst, "first": route[0],
                                  "chk": chk, "pre": pre})
        self.slots = [ls["slot"] for ls in self.lp_slots]
        self.chk_pos = {node: i for i, node in enumerate(layout["chokepoints"])}
        self.lane_rest = {}
        for li, route in enumerate(lanes["edges"]):
            for j, e in enumerate(route):
                self.lane_rest[(li, e)] = list(route[j + 1:])
        self.lane_index = {lid: i for i, lid in enumerate(lanes["id"])}
        self.lot_keys = layout.get("lot_keys")
        pools = static["commodities"].get("pool") or []
        self.ct_k = {k for k, p in enumerate(pools) if p == "ct"}
        # weeks from an OSAT receiving raw chips to a sink receiving the package: OSAT tau + one shipping week each way
        self.tail_lead = 2 + max((o["tau"] for o in self.osats), default=2)

    def _recent_starts(self, obs, f, week):
        """Mean lots started per week over the last ``recent_weeks`` weeks, read from the fab's work in process."""
        tot, n = 0.0, 0
        for node, qty, out, seen in zip(obs["wip.node"], obs["wip.qty"], obs["wip.out_week"], obs["wip.qty.observed"]):
            if seen and int(node) == f["node"]:
                started = int(out) - f["tau"]
                if week - self.recent_weeks <= started < week:
                    tot += float(qty)
        return tot / max(1, min(self.recent_weeks, week - 1))

    def _ct_release(self, obs, H):
        """{lot row: array H} of what each queued container lot row releases in week + o (FIFO by cohort, pro rata
        inside a cohort, kappa_ct a week; a closed chokepoint releases nothing), as pplan.queue_release for tankers."""
        q = obs["queue_lots.qty"]
        kap = obs["graph_now.kappa.ct"]
        open_now = np.where(obs["graph_now.open.observed"] == 1, obs["graph_now.open"], 1.0)
        by_chk = {}
        for row, (chk_node, k, _lane, _next) in enumerate(self.lot_keys):
            if int(k) in self.ct_k and q[row].sum() > 0:
                by_chk.setdefault(chk_node, []).append(row)
        out = {}
        for chk_node, rows in by_chk.items():
            pos = self.chk_pos.get(chk_node)
            kc = float(kap[pos]) if pos is not None else np.inf
            if pos is not None and open_now[pos] < 0.5:
                kc = 0.0
            sub = q[rows]
            cols = [c for c in range(sub.shape[1]) if sub[:, c].sum() > 0]
            rem = {c: float(sub[:, c].sum()) for c in cols}
            sched = np.zeros((len(rows), H))
            for w in range(H):
                budget = kc
                for c in cols:
                    if budget <= 0:
                        break
                    if rem[c] <= 0:
                        continue
                    take = min(budget, rem[c])
                    sched[:, w] += sub[:, c] * (take / float(sub[:, c].sum()))
                    rem[c] -= take
                    budget -= take
            for i, row in enumerate(rows):
                out[row] = sched[i]
        return out

    # ------------------------------------------------------------------------------------------------------------
    def plan(self, obs):
        """{slot: quantity} for this week's chip slots, or None when the LP does not solve."""
        self.last_pred = None
        week = int(obs["week"][0])
        H = max(1, min(self.H, self.T - week + 1))
        P, S = len(self.pos), len(self.lp_slots)
        tau, u, c = obs["graph_now.tau"], obs["graph_now.u"], obs["graph_now.c"]
        mask = obs["action_mask"]
        open_now = np.where(obs["graph_now.open.observed"] == 1, obs["graph_now.open"], 1.0)
        stock, stock_seen = obs["stock.qty"], obs["stock.qty.observed"]

        I0 = np.zeros(P)
        for i, p in enumerate(self.pos):
            idx = self.stock_index[(p["node"], p["k"])]
            if stock_seen[idx]:
                I0[i] = max(float(stock[idx]), 0.0)

        # fixed arrivals: shipments under way, cargo queued at open chokepoints, fab and OSAT work in process
        fixed = np.zeros((P, H))

        def arrive(pos, off, qty):
            if pos is not None and 0 <= off < H:
                fixed[pos, off] += qty

        for edge, k, lane, qty, arr, seen, lane_seen in zip(
            obs["pipeline.edge"], obs["pipeline.k"], obs["pipeline.lane"], obs["pipeline.qty"],
            obs["pipeline.arrival_week"], obs["pipeline.qty.observed"], obs["pipeline.lane.observed"],
        ):
            if not seen:
                continue
            rest = self.lane_rest.get((int(lane), int(edge)), []) if lane_seen else []
            dest = self.edges["head"][rest[-1]] if rest else self.edges["head"][int(edge)]
            arrive(self.pos_index.get((dest, int(k))), int(arr) - week + sum(int(tau[e]) for e in rest), float(qty))
        queue0 = {}  # chokepoint position -> container cargo queued there (kappa_ct)
        if self.lot_keys is not None and "queue_lots.qty" in obs:
            queued = obs["queue_lots.qty"].sum(axis=1)
            drain = self._ct_release(obs, H) if self.kappa_ct else {}
            for row, (chk_node, k, lane_key, next_edge) in enumerate(self.lot_keys):
                if queued[row] <= 0:
                    continue
                pos = self.chk_pos.get(chk_node)
                if row in drain and pos is not None:
                    queue0[pos] = queue0.get(pos, 0.0) + float(queued[row])
                if pos is not None and open_now[pos] < 0.5 and row not in drain:
                    continue
                lane = self.lane_index.get(lane_key) if isinstance(lane_key, str) else lane_key
                route = [next_edge] + (self.lane_rest.get((lane, next_edge), []) if lane is not None else [])
                dest = self.edges["head"][route[-1]]
                lead_q = sum(int(tau[e]) for e in route)
                if row in drain:
                    for o, qd in enumerate(drain[row]):
                        if qd > 0:
                            arrive(self.pos_index.get((dest, int(k))), o + lead_q, float(qd))
                    continue
                arrive(self.pos_index.get((dest, int(k))), lead_q, float(queued[row]))
        for node, k, qty, out, seen in zip(obs["wip.node"], obs["wip.k"], obs["wip.qty"], obs["wip.out_week"],
                                           obs["wip.qty.observed"]):
            if seen:
                arrive(self.pos_index.get((int(node), int(k))), int(out) - week, float(qty))

        # demand per sink and window week
        fc, fc_seen = obs["demand_forecast.qty"], obs["demand_forecast.qty.observed"]
        dem = np.zeros((len(self.sinks), H))
        for j, sk in enumerate(self.sinks):
            row, last = sk["row"], sk["dbar"]
            for t in range(H):
                if t < fc.shape[1] and fc_seen[row, t]:
                    last = float(fc[row, t])
                dem[j, t] = last
        cap_eff = np.where(obs["graph_now.fab.cap_eff.observed"] == 1, obs["graph_now.fab.cap_eff"], np.nan)
        thr_eff = np.where(obs["graph_now.osat.thr_eff.observed"] == 1, obs["graph_now.osat.thr_eff"], np.nan)
        supply = obs["graph_now.supply.avail"]
        supply_seen = obs["graph_now.supply.avail.observed"]

        # ---- variables: x[s,t] | I[p,t] | d[p,t] disposal | start[f,t] fab | pk[o,pair,t] osat | sv[j,t] served |
        #      lift[m,t] material supply
        nF = len(self.fabs)
        pairs = [(oi, pi) for oi, o in enumerate(self.osats) for pi in range(len(o["pairs"]))]
        nO, nJ, nM = len(pairs), len(self.sinks), len(self.materials)
        off_I = S * H
        off_d = off_I + P * H
        off_f = off_d + P * H
        off_o = off_f + nF * H
        off_s = off_o + nO * H
        off_m = off_s + nJ * H
        off_b = off_m + nM * H
        nB = nF if self.wafer_buffer > 0 else 0
        n = off_b + nB * H
        cost = np.zeros(n)
        hi = np.full(n, np.inf)

        banned = {}
        if "pending_prohibitions.edge" in obs:
            for e, k, w, seen in zip(obs["pending_prohibitions.edge"], obs["pending_prohibitions.k"],
                                     obs["pending_prohibitions.effective_week"],
                                     obs["pending_prohibitions.edge.observed"]):
                if seen:
                    banned[(int(e), int(k))] = min(banned.get((int(e), int(k)), 10**9), int(w))
        lead = np.zeros(S, dtype=int)
        for j, ls in enumerate(self.lp_slots):
            route = ls["route"]
            lead[j] = max(1, sum(int(tau[e]) for e in route))
            freight = sum(float(c[e]) for e in route)
            cap = min(float(u[e]) for e in route) if mask[ls["slot"]] else 0.0
            cap *= max(min((float(open_now[self.chk_pos[q]]) for q in ls["chk"] if q in self.chk_pos), default=1.0),
                       0.0)
            stop = min((banned.get((e, ls["k"]), 10**9) - week for e in route), default=10**9)
            for t in range(H):
                cost[j * H + t] = freight
                hi[j * H + t] = cap if t < stop else 0.0
        for i, p in enumerate(self.pos):
            for t in range(H):
                cost[off_I + i * H + t] = p["hold"]
                hi[off_I + i * H + t] = p["cap"]
                cost[off_d + i * H + t] = p["disp"]
        shed = obs["last_week.shed.qty"] if "last_week.shed.qty" in obs else None
        shed_seen = obs["last_week.shed.qty.observed"] if "last_week.shed.qty.observed" in obs else None
        fab_cap = {}
        if self.fab_cap_mode == "energy2":
            # spare power per grid (deliverable output minus base load) is split among its fabs in proportion to their
            # draw e * p_hat / R (simulator step 7, base_first): cap_f <= R_f * E_f / e_f
            Gb, yb = obs["graph_now.grid.G_bar"], obs["graph_now.grid.y_bar"]
            Rf = np.where(obs["graph_now.fab.R.observed"] == 1, obs["graph_now.fab.R"], 1.0)
            by_grid = {}
            for fi, f in enumerate(self.fabs):
                if f["grid_pos"] is not None and f["e"] > 0:
                    by_grid.setdefault(f["grid_pos"], []).append(fi)
            for g, fis in by_grid.items():
                spare = max(float(Gb[g]) - float(yb[g]), 0.0)
                draws = {}
                for fi in fis:
                    f = self.fabs[fi]
                    c = cap_eff[f["pos"]] if np.isfinite(cap_eff[f["pos"]]) else f["cap0"]
                    r = max(float(Rf[f["pos"]]), 1e-9)
                    draws[fi] = (f["e"] * c / r, c, r)
                tot = sum(d for d, _c, _r in draws.values())
                for fi, (d, c, r) in draws.items():
                    E = spare * d / tot if tot > 0 else 0.0
                    fab_cap[fi] = min(c, r * E / self.fabs[fi]["e"])
        if self.fab_cap_mode == "observed" and week > 1:
            # a fab holding wafers but starting few is limited by power (or damage), not wafers: plan it at what it
            # started recently; a fab without wafers is wafer-limited, so it keeps its nameplate capacity
            for fi, f in enumerate(self.fabs):
                c = cap_eff[f["pos"]] if np.isfinite(cap_eff[f["pos"]]) else f["cap0"]
                recent = self._recent_starts(obs, f, week)
                if I0[f["in"]] > 2.0 * recent + 1.0:
                    fab_cap[fi] = min(c, self.growth * recent + 0.02 * c)
        for fi, f in enumerate(self.fabs):
            cap = cap_eff[f["pos"]] if np.isfinite(cap_eff[f["pos"]]) else f["cap0"]
            if fi in fab_cap:
                cap = fab_cap[fi]
            g = f["grid_pos"]
            if (self.fab_cap_mode in ("energy", "energy2") and g is not None and shed is not None and shed_seen[g]
                    and float(shed[g]) > 1e-6):
                # the grid cut homes last week, so (homes first) this fab got little power: plan with what it
                # actually started over the last weeks (from its work in process), not with its nameplate capacity
                cap = min(cap, self.growth * self._recent_starts(obs, f, week) + 1.0)
            hi[off_f + fi * H: off_f + fi * H + H] = max(cap, 0.0)
        for j, sk in enumerate(self.sinks):
            cost[off_s + j * H: off_s + j * H + H] = -sk["pi"]
            hi[off_s + j * H: off_s + j * H + H] = dem[j]
        for mi, m in enumerate(self.materials):
            p = self.pos[m]
            sidx = self.supply_index.get((p["node"], p["k"]))
            per_week = float(supply[sidx]) if sidx is not None and supply_seen[sidx] else 0.0
            hi[off_m + mi * H: off_m + mi * H + H] = max(per_week, 0.0)

        # ---- balance rows: I[t] - I[t-1] + d[t] + out[t] + start/pack/serve[t] - in[t] - lift[t] = fixed[t] (+I0)
        rows, cols, vals = [], [], []
        rhs = np.zeros(P * H)
        for i in range(P):
            for t in range(H):
                r = i * H + t
                rows += [r, r]
                cols += [off_I + i * H + t, off_d + i * H + t]
                vals += [1.0, 1.0]
                if t > 0:
                    rows.append(r); cols.append(off_I + i * H + t - 1); vals.append(-1.0)
                rhs[r] = fixed[i, t] + (I0[i] if t == 0 else 0.0)
        for j, ls in enumerate(self.lp_slots):
            for t in range(H):
                rows.append(ls["src"] * H + t); cols.append(j * H + t); vals.append(1.0)
                ta = t + lead[j]
                if ta < H:
                    rows.append(ls["dst"] * H + ta); cols.append(j * H + t); vals.append(-1.0)
        for fi, f in enumerate(self.fabs):
            for t in range(H):
                rows.append(f["in"] * H + t); cols.append(off_f + fi * H + t); vals.append(1.0)
                if t + f["tau"] < H:
                    rows.append(f["out"] * H + t + f["tau"]); cols.append(off_f + fi * H + t); vals.append(-1.0)
        for q, (oi, pi) in enumerate(pairs):
            o = self.osats[oi]
            raw, fin = o["pairs"][pi]
            for t in range(H):
                rows.append(raw * H + t); cols.append(off_o + q * H + t); vals.append(1.0)
                if t + o["tau"] < H:
                    rows.append(fin * H + t + o["tau"]); cols.append(off_o + q * H + t); vals.append(-1.0)
        for j, sk in enumerate(self.sinks):
            for t in range(H):
                rows.append(sk["pos"] * H + t); cols.append(off_s + j * H + t); vals.append(1.0)
        for mi, m in enumerate(self.materials):
            for t in range(H):
                rows.append(m * H + t); cols.append(off_m + mi * H + t); vals.append(-1.0)
        A_eq = coo_matrix((vals, (rows, cols)), shape=(P * H, n)).tocsr()

        # ---- inequalities
        rows, cols, vals, b = [], [], [], []
        r = 0
        # a shipment leaves only last week's stock: sum_out[t] <= I[t-1] (I[-1] = I0)
        by_src = {}
        for j, ls in enumerate(self.lp_slots):
            by_src.setdefault(ls["src"], []).append(j)
        for i, js in by_src.items():
            for t in range(H):
                for j in js:
                    rows.append(r); cols.append(j * H + t); vals.append(1.0)
                if t > 0:
                    rows.append(r); cols.append(off_I + i * H + t - 1); vals.append(-1.0)
                    b.append(0.0)
                else:
                    b.append(I0[i])
                r += 1
        # each first edge's capacity is shared by its slots
        by_edge = {}
        for j, ls in enumerate(self.lp_slots):
            by_edge.setdefault(ls["first"], []).append(j)
        for e, js in by_edge.items():
            if len(js) < 2:
                continue
            for t in range(H):
                for j in js:
                    rows.append(r); cols.append(j * H + t); vals.append(1.0)
                b.append(float(u[e]))
                r += 1
        # an OSAT's throughput is shared by its packaged commodities
        for oi, o in enumerate(self.osats):
            qs = [q for q, (oo, _p) in enumerate(pairs) if oo == oi]
            thr = thr_eff[o["pos"]] if np.isfinite(thr_eff[o["pos"]]) else o["thr0"]
            for t in range(H):
                for q in qs:
                    rows.append(r); cols.append(off_o + q * H + t); vals.append(1.0)
                b.append(max(thr, 0.0))
                r += 1
        # kappa_ct: new shipments through a chokepoint join its queue: what reaches it by week t (cumulative) fits in
        # (t + 1) weeks of its container throughput after the cargo already waiting there
        if self.kappa_ct and "graph_now.kappa.ct" in obs:
            kap = obs["graph_now.kappa.ct"]
            by_chk = {}
            for j, ls in enumerate(self.lp_slots):
                for chk_node, pre in ls["pre"].items():
                    q = self.chk_pos.get(chk_node)
                    if q is not None:
                        by_chk.setdefault(q, []).append((j, sum(int(tau[e]) for e in pre)))
            for q, js in by_chk.items():
                kc = float(kap[q])
                if not np.isfinite(kc):
                    continue
                for t in range(H):
                    any_term = False
                    for j, off in js:
                        for tt in range(0, t - off + 1):
                            rows.append(r); cols.append(j * H + tt); vals.append(1.0)
                            any_term = True
                    if not any_term:
                        continue
                    b.append(max(0.0, (t + 1) * kc - queue0.get(q, 0.0)))
                    r += 1
        # wafer buffer: I[in_f, t] + short[f, t] >= wafer_buffer * nameplate (limited by storage)
        buf_rows = []  # (row, fab index, t)
        for fi in range(nB):
            f = self.fabs[fi]
            c0 = cap_eff[f["pos"]] if np.isfinite(cap_eff[f["pos"]]) else f["cap0"]
            want = min(self.wafer_buffer * max(c0, 0.0), 0.95 * self.pos[f["in"]]["cap"])
            if want <= 0:
                continue
            for t in range(H):
                if self.sell_end and week + t + f["tau"] + self.tail_lead > self.T:
                    continue
                rows += [r, r]; cols += [off_I + f["in"] * H + t, off_b + fi * H + t]; vals += [-1.0, -1.0]
                b.append(-want)
                buf_rows.append((r, fi, t))
                cost[off_b + fi * H + t] = self.buffer_cost
                r += 1
        A_ub = coo_matrix((vals, (rows, cols)), shape=(r, n)).tocsr()
        b = np.array(b, dtype=float)
        bounds = np.column_stack([np.zeros(n), hi])

        if self.sell_buffer and buf_rows:
            # pass 1 without the buffer: how many wafers would each fab start if only selling chips counted?
            c1 = cost.copy()
            c1[off_b:off_b + nB * H] = 0.0
            res1 = linprog(c1, A_ub=A_ub, b_ub=b, A_eq=A_eq, b_eq=rhs, bounds=bounds, method="highs")
            if res1.status == 0:
                x1 = res1.x
                for fi in range(nB):
                    st = x1[off_f + fi * H: off_f + fi * H + H]
                    caps = hi[off_f + fi * H: off_f + fi * H + H]
                    if np.max(caps) <= 0 or np.max(st) >= self.sell_frac * np.max(caps):
                        continue
                    want = self.wafer_buffer * float(np.max(st))
                    for (rr, ff, _t) in buf_rows:
                        if ff == fi:
                            b[rr] = max(b[rr], -want)

        res = linprog(cost, A_ub=A_ub, b_ub=b, A_eq=A_eq, b_eq=rhs, bounds=bounds, method="highs")
        if res.status != 0:
            return None
        x = res.x
        self.last_pred = {"I": [float(x[off_I + i * H]) for i in range(P)],
                          "sv": [float(x[off_s + j * H]) for j in range(nJ)],
                          "sv4": [float(sum(x[off_s + j * H + t] for t in range(min(5, H)))) for j in range(nJ)],
                          "dem4": [float(sum(dem[j, :min(5, H)])) for j in range(nJ)],
                          "st": [float(x[off_f + fi * H]) for fi in range(nF)],
                          "d": [float(x[off_d + i * H]) for i in range(P)]}
        return {ls["slot"]: max(float(x[j * H]), 0.0) for j, ls in enumerate(self.lp_slots)}
