"""Tanker release priorities at chokepoints (``override_qty`` / ``release_mode``), used when ``tanker_mode`` is "lp".

Tanker cargo (lng, crude) queued at a chokepoint is normally released by the default rule: each lot onto its own lane's
next edge, FIFO by arrival cohort, pro rata inside a cohort, up to that edge's capacity u and the chokepoint's tanker
throughput kappa_tb. Cargo whose next edge is narrow stays parked for the whole episode while other out-edges are idle.

An override slot (c, k, out edge, lane) releases cargo of k queued at c, FIFO whatever lane it came on, onto the slot's
lane: the queue of (c, k) is one pool that can go to any destination the slots reach. Every week a small LP chooses the
release per slot:

    max  sum_s (release_value - lead_cost * lead_s) y_s + sum_s (w_s - lead_cost * lead_s) r_s - overflow_cost * sum z
    s.t. y_s <= own cargo of slot s (lots whose lane and next edge are the slot's: what the default rule sends there)
         r_s only for a slot whose destination pool (grid, fuel) is short: its stock plus the next ``need_weeks`` of
             arrivals below its floor (rationing line + safety stock); w_s = 1 + fab_bonus at grids that power fabs
         sum_{s of (c,k)} (y_s + r_s) <= queued content of (c, k), this week's arrivals included
         sum_{s on out edge e} (y_s + r_s) <= u_e,  sum_{s at c} (y_s + r_s) <= kappa_tb[c]
         sum_{s through later edge e'} (y_s + r_s) - z_e' <= u_e' - (cargo already queued for e') / drain_weeks
         sum_{s through later chokepoint c'} (y_s + r_s) - z_c' <= kappa_tb[c'] - (tanker cargo queued at c') / drain_weeks

release_value > every overflow a slot can collect > w: each lot goes its own way first, as the default rule sends it
(the energy LP planned those lanes); only cargo its own edge cannot take this week is redirected, and only to a short
pool. Every pair (c, k) with content at an open chokepoint goes to mode 1 (override); the others keep the default.
"""

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix


class TankerPlanner:
    def __init__(self, config, agent):
        static, layout = config["static"], config["layout"]
        edges, lanes = static["edges"], static["lanes"]
        self.pairs = [tuple(p) for p in layout["release_pairs"]]  # (chokepoint node, k)
        self.pair_index = {p: i for i, p in enumerate(self.pairs)}
        self.chk_pos = {node: i for i, node in enumerate(layout["chokepoints"])}
        ov = static["override_slots"]
        self.n_ov = len(ov["k"])
        self.lot_keys = layout["lot_keys"]
        self.slots = []  # dicts: slot, pair, k, chk pos, out edge, rest edges, later chokepoint positions, pool
        for s in range(self.n_ov):
            c, k, e, lane = int(ov["chokepoint"][s]), int(ov["k"][s]), int(ov["out_edge"][s]), ov["lane"][s]
            rest = list(agent.lane_rest.get((int(lane), e), [])) if lane is not None else []
            dest = edges["head"][rest[-1]] if rest else edges["head"][e]
            later = [self.chk_pos[edges["tail"][r]] for r in rest if edges["tail"][r] in self.chk_pos]
            self.slots.append({
                "slot": s, "pair": self.pair_index[(c, k)], "k": k, "chk": self.chk_pos[c], "edge": e,
                "rest": rest, "later": later, "pool": agent.feeds.get((dest, k)),
            })
        self.grid_has_fab = agent.grid_has_fab
        self.edge_head = [int(h) for h in edges["head"]]
        self.lane_rest = agent.lane_rest
        self.slot_by_key = {(int(ov["chokepoint"][s]), int(ov["k"][s]), int(ov["out_edge"][s]),
                             None if ov["lane"][s] is None else int(ov["lane"][s])): s for s in range(self.n_ov)}
        self.pools = agent.pools

    def plan(self, obs, need, params):
        """(override_qty, release_mode, releases) for this week; releases = [(pool, lead weeks, qty)]."""
        P = len(self.pairs)
        mode = np.zeros(P, dtype=np.int64)
        qty = np.zeros(self.n_ov)
        lots = obs["queue_lots.qty"].sum(axis=1)
        content = np.zeros(P)
        queued_next = {}  # next edge -> cargo already queued for it (all commodities)
        queued_chk = {}  # chokepoint position -> tanker cargo already queued there
        own = np.zeros(self.n_ov)  # cargo whose own lane and next edge are this slot's
        for row, (c, k, lane, e) in enumerate(self.lot_keys):
            q = float(lots[row])
            if q <= 0:
                continue
            s_own = self.slot_by_key.get((int(c), int(k), int(e), None if lane is None else int(lane)))
            if s_own is not None:
                own[s_own] += q
            queued_next[int(e)] = queued_next.get(int(e), 0.0) + q
            if (int(c), int(k)) in self.pair_index:
                queued_chk[self.chk_pos[int(c)]] = queued_chk.get(self.chk_pos[int(c)], 0.0) + q
            p = self.pair_index.get((int(c), int(k)))
            if p is not None:
                content[p] += q
        # cargo reaching a chokepoint this week joins its queue before the release (step 1): it counts too, or the
        # override would hold every arrival for a week
        week = int(obs["week"][0])
        for e, k, lane, q, arr, seen, lane_seen in zip(
            obs["pipeline.edge"], obs["pipeline.k"], obs["pipeline.lane"], obs["pipeline.qty"],
            obs["pipeline.arrival_week"], obs["pipeline.qty.observed"], obs["pipeline.lane.observed"],
        ):
            if not seen or int(arr) > week:
                continue
            p = self.pair_index.get((self.edge_head[int(e)], int(k)))
            if p is None:
                continue
            content[p] += float(q)
            rest = self.lane_rest.get((int(lane), int(e))) if lane_seen else None
            if rest:
                s_own = self.slot_by_key.get((self.edge_head[int(e)], int(k), int(rest[0]), int(lane)))
                if s_own is not None:
                    own[s_own] += float(q)
                queued_next[rest[0]] = queued_next.get(rest[0], 0.0) + float(q)
                queued_chk[self.chk_pos[self.edge_head[int(e)]]] = (
                    queued_chk.get(self.chk_pos[self.edge_head[int(e)]], 0.0) + float(q))
        if content.max(initial=0.0) <= params["min_queue"]:
            return qty, mode, []
        u, tau = obs["graph_now.u"], obs["graph_now.tau"]
        u_seen = obs["graph_now.u.observed"]
        kap = obs["graph_now.kappa.tb"]
        kap_seen = obs["graph_now.kappa.tb.observed"]
        omask = obs["override_mask"]
        open_now = np.where(obs["graph_now.open.observed"] == 1, obs["graph_now.open"], 1.0)
        drain = max(float(params["drain_weeks"]), 1.0)

        live = []
        for sl in self.slots:
            p = sl["pair"]
            if content[p] <= params["min_queue"] or not omask[sl["slot"]] or not kap_seen[sl["chk"]]:
                continue
            if open_now[sl["chk"]] <= 0 or sl["pool"] is None:
                continue
            if not all(u_seen[e] for e in [sl["edge"]] + sl["rest"]):
                continue
            live.append(sl)
        if not live:
            return qty, mode, []

        # columns: per live slot its own cargo (lots whose lane and next edge are the slot's: what the default rule
        # would send there) and, to a pool that is short, cargo redirected from the pair's other lanes; then one
        # overflow per soft row
        cols_of = []  # (live index, own?)
        cost, ub = [], []
        for j, sl in enumerate(live):
            pool = self.pools[sl["pool"]]
            lead = int(tau[sl["edge"]]) + sum(int(tau[e]) for e in sl["rest"])
            cols_of.append((j, True))
            cost.append(-(params["release_value"] - params["lead_cost"] * lead))
            ub.append(own[sl["slot"]])
            if need[sl["pool"]]:
                w = 1.0 + params["fab_bonus"] * self.grid_has_fab.get(pool["grid"], 0.0)
                cols_of.append((j, False))
                cost.append(-(w - params["lead_cost"] * lead))
                ub.append(np.inf)
        n = len(cost)
        rows, cols, vals, rhs = [], [], [], []
        r = 0

        def add(js, b, soft=False):
            nonlocal r
            for j in js:
                rows.append(r); cols.append(j); vals.append(1.0)
            if soft:
                rows.append(r); cols.append(len(cost)); vals.append(-1.0)
                cost.append(params["overflow_cost"])
                ub.append(np.inf)
            rhs.append(max(float(b), 0.0))
            r += 1

        by_pair, first, later_e, later_c = {}, {}, {}, {}
        for j, (li, _own) in enumerate(cols_of):
            sl = live[li]
            by_pair.setdefault(sl["pair"], []).append(j)
            first.setdefault(("e", sl["edge"]), []).append(j)
            first.setdefault(("c", sl["chk"]), []).append(j)
            for e in sl["rest"]:
                later_e.setdefault(e, []).append(j)
            for q in sl["later"]:
                later_c.setdefault(q, []).append(j)
        for p, js in by_pair.items():
            add(js, content[p])
        for (kind, i), js in first.items():  # hard: this week's out edge and this chokepoint's throughput
            add(js, float(u[i]) if kind == "e" else float(kap[i]))
        for e, js in later_e.items():  # soft: the rate later edges can carry, less what already waits for them
            add(sorted(set(js)), float(u[e]) - queued_next.get(e, 0.0) / drain, soft=True)
        for q, js in later_c.items():
            add(sorted(set(js)), float(kap[q]) - queued_chk.get(q, 0.0) / drain, soft=True)
        cost = np.array(cost)
        A = coo_matrix((vals, (rows, cols)), shape=(r, len(cost))).tocsr()
        res = linprog(cost, A_ub=A, b_ub=np.array(rhs), bounds=list(zip([0.0] * len(ub), ub)), method="highs")
        if res.status != 0:
            return np.zeros(self.n_ov), np.zeros(P, dtype=np.int64), []
        releases = []
        for sl in live:
            mode[sl["pair"]] = 1
        for j, (li, _own) in enumerate(cols_of):
            sl = live[li]
            x = max(float(res.x[j]), 0.0)
            qty[sl["slot"]] += x
            if x > 0:
                lead = int(tau[sl["edge"]]) + sum(int(tau[e]) for e in sl["rest"])
                releases.append((sl["pool"], lead, x, sl["pair"]))
        return qty, mode, releases
