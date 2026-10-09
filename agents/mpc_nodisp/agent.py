"""Energy MPC + chip MPC (``chips.py``) on top of Andrii's demand-aware agent (``fallback.py``).

Every week a linear program plans the fuel shipments (lng, crude, nucfuel) from the sources over the next H weeks so
that each grid keeps fuel to burn: power shed costs VOLL (~4 M USD per unit), against a few hundred USD of freight.
The LP shares each source's limited capacity among the lanes that feed the grids most at risk, routes around closed
chokepoints and pending sanctions, and keeps the rationed fuel above the rationing threshold psi * I-bar. Every other
slot (terminal -> grid, and the chip slots when the chip LP fails or the week runs long) is played by the fallback
agent. The chip LP (``chips.py``) plans every wafer and chip shipment over the next ``chip_H`` weeks. Any error plays
the fallback's action for the part that failed.
"""

import json
import time
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

import importlib.util

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("mpc_fallback", HERE / "fallback.py")
_fallback = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fallback)
FallbackAgent = _fallback.Agent
_cspec = importlib.util.spec_from_file_location("mpc_chips", HERE / "chips.py")
_chips = importlib.util.module_from_spec(_cspec)
_cspec.loader.exec_module(_chips)
_pspec = importlib.util.spec_from_file_location("mpc_pplan", HERE / "pplan.py")
_pplan = importlib.util.module_from_spec(_pspec)
_pspec.loader.exec_module(_pplan)

PARAMS = {
    "H": 12,  # planning horizon in weeks
    "safety_weeks": 3.0,  # extra weeks of burn kept on top of the rationing threshold
    "end_weeks": 3.0,  # weeks of burn wanted in stock at the end of the window
    "ration_cost": 1.0,  # weight of a unit below the rationing line, in VOLL * burn / threshold
    "safety_cost": 0.2,  # same for a unit below the safety stock above it
    "cover_frac": 0.8,  # keep at least this share of the grid's normal days of cover in stock
    "warn_gain": 0.0,  # how much a chokepoint's warning score cuts its lanes' future capacity
    "time_limit": 1.0,  # CPU seconds per week after which the LP is skipped
    "fab_boost": 0.0,
    "pulse_weeks": 1.5,
    "pulse_grids": ["grid_tw", "grid_kr"],  # grid ids the pulse applies to (empty = all)  # experiment: hold terminal->grid fuel until the terminal has this many weeks of burn (0 = off)  # extra VOLL weight on grids feeding fabs (experiment)
    "fab_cap_mode": "observed",  # "energy": plan power-starved fabs (grid shed last week) at their recent starts
    "wafer_buffer": 3.0,  # weeks of nameplate fab starts kept on hand as wafers (soft; 0 = off)
    "buffer_cost": 1000.0,  # USD per wafer and week below that buffer
    "sell_end": False,  # task 19: no wafer buffer for lots that can't reach a sink before the episode ends
    "chip_H": 24,  # chip planning horizon in weeks (wafer -> fab -> OSAT -> sink takes up to ~20)
    "chip_time_limit": 2.0,  # CPU seconds used this week after which the chip LP is skipped (Small 2 s, Full 4 s)
    "pulse_plan": True,  # planned pulses (pplan.py, from mpc_pplan): per fab grid, choose the terminal -> grid releases
    "pp_grids": [],  # grid ids the planner applies to (empty = every base_first grid with fabs); the others keep the pulse
    "pp_H": 8,  # its horizon in weeks
    "pp_value": 20.0,  # fab energy valued at this share of the chips it makes (pi of their sinks)
    "pp_end": 0.9,  # fuel left at the end of the window, in VOLL per unit
    "pp_time": 0.3,  # HiGHS time limit per grid, seconds (pp_method "milp")
    "pp_method": "enum",  # "enum": every sequence of weekly release modes over pp_enum_H weeks; "milp": scipy milp
    "pp_enum_H": 6,
    "pp_deadline": 1.5,  # CPU seconds used this week after which no more grids are planned
    "kappa_lp": False,  # task 18: queued tanker cargo drains at the chokepoint's kappa_tb, and the LP's lanes share it
    "pp_split": False,  # task 18: a planner mode that recharges the rationed fuel and holds the others (crude)
    "pp_direct": [],  # grid ids whose direct source -> grid pipelines the planner also times (task 18; empty = off)
    # task 26 (imitating the clairvoyant plan): it never disposes of fuel and keeps each grid's fuel at the rationing
    # line, the rest at the terminal. "room": a terminal -> grid release never fills the grid above its storage;
    # "target": nor above psi I-bar + imit_margin weeks of burn (the oracle's level). None = off.
    "imit_grid": None,
    "imit_margin": 1.0,  # weeks of burn above the rationing line the grid ends the week with ("target")
    "imit_burn": 0.9,  # share of this week's possible burn counted on when sizing the release (load can be < 1)
    "lp_overflow_cost": 100.0,  # energy LP: USD per unit of fuel planned above the pool's storage (task 26)
    # task 30 (more power for the JP / SEA / CN fabs). Crude starts at 0 at every grid and sits at the CN / EU / JP
    # terminals while the grid's crude segment is short (a fab grid's headroom is smaller than its crude segment, so any
    # crude gap darkens the fabs), and the Gulf / US crude sources throw supply away at their caps.
    "jp_grids": [],  # grid ids the options below apply to (empty = every grid with fabs)
    "jp_safety": {},  # fuel id -> safety weeks of burn in the energy LP's floor at those grids (stock up ahead)
    "jp_fill": [],  # fuel ids whose terminal -> grid release is at least what fills this week's segment (no holding)
    # tanker queues drain onto each next edge at most at its capacity (the simulator's eta_u), in the energy LP and the
    # pulse planner (needs kappa_lp). Without it a queue behind a cut edge was forecast to arrive at once
    "jp_qedge": False,
    # task 35 (chip LP, chips.py): later edges of chip routes are shared (cq_edges), queued chip cargo drains at
    # min(next-edge, kappa_ct) shares (cq_drain), routes share each chokepoint's kappa_ct (cq_kappa)
    "cq_edges": False,
    "cq_drain": False,
    "cq_kappa": False,
    # task 37 (chips.py): lanes through a partly open chokepoint keep their edge capacity (the open fraction only
    # scales the strait's kappa, which cq_kappa shares); sell_buffer: task 19's buffer sized by sellable starts
    "nd_open": False,
    "nd_open_e": False,  # the same for the energy LP's tanker lanes (kappa_lp shares the strait's kappa_tb)
    "sell_buffer": False,
    "sell_frac": 0.9,
    "jp_arrfb": 0.0,  # pulse planner: scale future arrivals by the observed arrived / forecast ratio (EMA weight; 0 = off)
}
if (HERE / "params.json").is_file():
    PARAMS |= json.loads((HERE / "params.json").read_text())


class Agent:
    def __init__(self, config=None):
        self.fallback = FallbackAgent(config)
        self.ok = False
        try:
            self._setup(config)
            self.ok = True
        except Exception:
            pass
        self.pplan = None
        if PARAMS["pulse_plan"]:
            try:
                self.pplan = _pplan.PulsePlanner(config, H=int(PARAMS["pp_H"]), value_scale=PARAMS["pp_value"],
                                                 end_value=PARAMS["pp_end"], time_limit=PARAMS["pp_time"],
                                                 method=PARAMS["pp_method"], enum_H=PARAMS["pp_enum_H"],
                                                 direct_grids=PARAMS["pp_direct"], kappa=PARAMS["kappa_lp"],
                                                 split=PARAMS["pp_split"], qedge=PARAMS["jp_qedge"],
                                                 arrfb=PARAMS["jp_arrfb"])
                if PARAMS["pp_grids"]:
                    ids = [n["id"] for n in config["static"]["instance"]["nodes"]]
                    self.pplan.grids = [g for g in self.pplan.grids if ids[g["node"]] in PARAMS["pp_grids"]]
            except Exception:
                self.pplan = None
        self.planned_arrivals = None
        self.chips = None
        try:
            self.chips = _chips.ChipPlanner(config, H=int(PARAMS["chip_H"]), fab_cap_mode=PARAMS["fab_cap_mode"],
                                            wafer_buffer=PARAMS["wafer_buffer"], buffer_cost=PARAMS["buffer_cost"],
                                            sell_end=PARAMS["sell_end"], cq_edges=PARAMS["cq_edges"],
                                            cq_drain=PARAMS["cq_drain"], cq_kappa=PARAMS["cq_kappa"],
                                            nd_open=PARAMS["nd_open"], sell_buffer=PARAMS["sell_buffer"],
                                            sell_frac=PARAMS["sell_frac"])
        except Exception:
            pass

    def _setup(self, config):
        static, layout = config["static"], config["layout"]
        inst = static["instance"]
        nodes = inst["nodes"]
        node_ids = [n["id"] for n in nodes]
        self.node_ids = node_ids
        self.psi = float(inst["params"].get("psi", 0.6))
        edges, lanes, slots = static["edges"], static["lanes"], static["action_slots"]
        self.edges = edges
        n_edges = len(edges["head"])
        commodities = static["commodities"]["id"]
        self.commodities = list(commodities)

        self.stock_index_early = {tuple(row): i for i, row in enumerate(layout["stock_slots"])}
        # grids: one (grid, fuel) pool per modelled fuel
        self.pools = []  # dicts: grid node, k, share, ibar, rationed, cap, voll, grid index
        grid_nodes = [i for i, n in enumerate(nodes) if n.get("type") == "grid"]
        self.grid_pos = {node: i for i, node in enumerate(layout["grids"])} if "grids" in layout else {}
        for g in grid_nodes:
            spec = nodes[g]["grid"]
            for fuel, share in spec["shares"].items():
                if fuel not in commodities or share <= 0:
                    continue
                k = commodities.index(fuel)
                storage = nodes[g].get("stock", {}).get(fuel, {}).get("storage", np.inf)
                self.pools.append({
                    "grid": g, "k": k, "share": float(share), "deliverable": float(spec["deliverable"]),
                    "ibar": float(spec.get("ibar", {}).get(fuel, 0.0)), "rationed": spec.get("rationed") == fuel,
                    "cap": float(storage), "voll": float(spec.get("voll", 4e6)), "terminal": None,
                    "cover_days": float(spec.get("days_cover", {}).get(fuel, 0.0)),
                })
        self.pool_index = {(p["grid"], p["k"]): i for i, p in enumerate(self.pools)}
        energy_k = {p["k"] for p in self.pools}

        # terminals feeding a grid: their stock counts in that grid's pool
        self.feeds = {}  # (node, k) -> pool index
        for p_i, p in enumerate(self.pools):
            self.feeds[(p["grid"], p["k"])] = p_i
        for e in range(n_edges):
            tail, head = edges["tail"][e], edges["head"][e]
            if nodes[tail].get("type") == "terminal" and nodes[head].get("type") == "grid":
                for k in edges["K"][e] or []:
                    if (head, k) in self.pool_index:
                        p_i = self.pool_index[(head, k)]
                        self.feeds[(tail, k)] = p_i
                        storage = nodes[tail].get("stock", {}).get(commodities[k], {}).get("storage", 0.0)
                        self.pools[p_i]["cap"] += float(storage)

        self.tg_slots = []  # (slot, terminal stock index, weekly burn share key)
        for s_, (edge, k, lane) in enumerate(zip(slots["edge"], slots["k"], slots["lane"])):
            tail, head = edges["tail"][edge], edges["head"][edge]
            if nodes[tail].get("type") == "terminal" and nodes[head].get("type") == "grid" and (head, k) in self.pool_index:
                self.tg_slots.append((s_, self.stock_index_early.get((tail, k)), self.pool_index[(head, k)]))
        self.grid_store = {}  # pool index -> the grid slot's own storage (pool "cap" adds the terminals')
        self.grid_arr_keys = {}  # (grid node, k) -> pool index, for pipelines ending at the grid this week
        for p_i, p in enumerate(self.pools):
            st_ = nodes[p["grid"]].get("stock", {}).get(commodities[p["k"]], {}).get("storage", np.inf)
            self.grid_store[p_i] = float(np.inf if st_ is None else st_)
            self.grid_arr_keys[(p["grid"], p["k"])] = p_i
        self.grid_has_fab = {}
        for f in layout.get("fabs", []):
            g = nodes[f].get("fab", {}).get("grid")
            if g in node_ids:
                self.grid_has_fab[node_ids.index(g)] = 1.0
        chokepoint_pos = {node: i for i, node in enumerate(layout["chokepoints"])}
        pools = static["commodities"].get("pool") or []
        self.tb_k = {k for k, p in enumerate(pools) if p == "tb"}
        self.stock_index = {tuple(row): i for i, row in enumerate(layout["stock_slots"])}
        self.supply_index = {tuple(row): i for i, row in enumerate(layout["supply_slots"])}

        # LP slots: energy slots that leave a source and end at a pool
        self.lp_slots = []  # dicts: slot, k, route, pool, source, chokepoints (positions)
        for s, (edge, k, lane) in enumerate(zip(slots["edge"], slots["k"], slots["lane"])):
            if k not in energy_k:
                continue
            route = list(lanes["edges"][lane]) if lane is not None else [edge]
            source = edges["tail"][route[0]]
            if nodes[source].get("type") != "source":
                continue
            pool = self.feeds.get((edges["head"][route[-1]], k))
            if pool is None:
                continue
            chk = [chokepoint_pos[c] for c in lanes["chokepoints"][lane]] if lane is not None else []
            self.lp_slots.append({"slot": s, "k": k, "route": route, "pool": pool, "source": source, "chk": chk})

        # lanes' remaining edges after each edge, for pipeline and queue arrivals
        self.lane_rest = {}
        for li, route in enumerate(lanes["edges"]):
            for j, e in enumerate(route):
                self.lane_rest[(li, e)] = list(route[j + 1:])
        self.lane_final = {li: edges["head"][route[-1]] for li, route in enumerate(lanes["edges"])}
        self.lane_index = {lid: i for i, lid in enumerate(lanes["id"])} if "id" in lanes else {}
        self.lot_keys = layout.get("lot_keys")
        self.chk_node_pos = chokepoint_pos
        # warning units of chokepoints: "chokepoint chk_x" names in the layout, matched by node id
        self.warn_chk = {}
        for i, unit in enumerate(layout.get("warning_units", [])):  # [kind, index] pairs
            if len(unit) == 2 and unit[0] == "chokepoint" and unit[1] in chokepoint_pos:
                self.warn_chk[chokepoint_pos[unit[1]]] = i

    # ------------------------------------------------------------------ act
    def act(self, observation):
        start = time.process_time()
        self.planned_arrivals = None
        if self.pplan is not None:
            self.pplan.other_use = {}
            self.pplan.direct_arr = {}
        action = self.fallback.act(observation)
        flows = np.array(action["flows"], dtype=float)
        if self.ok:
            try:
                planned = self._plan(observation, flows.copy(), start)
                if planned is not None and np.all(np.isfinite(planned)):
                    flows = planned
            except Exception:
                pass
        if self.chips is not None and time.process_time() - start < PARAMS["chip_time_limit"] * 0.4:
            try:
                plan = self.chips.plan(observation)
                if plan is not None and all(np.isfinite(q) for q in plan.values()):
                    for s, q in plan.items():
                        flows[s] = q
            except Exception:
                pass
        if PARAMS["pulse_weeks"] > 0 and self.ok:
            try:
                G_bar = observation["graph_now.grid.G_bar"]
                stock = observation["stock.qty"]
                for s_, si, p_i in self.tg_slots:
                    p = self.pools[p_i]
                    if PARAMS["pulse_grids"] == "auto":
                        # grids that feed fabs and shed homes last week (homes first: their fabs got no power)
                        gpos = self.grid_pos.get(p["grid"])
                        shed = observation.get("last_week.shed.qty")
                        if (not self.grid_has_fab.get(p["grid"]) or gpos is None or shed is None
                                or not observation["last_week.shed.qty.observed"][gpos] or float(shed[gpos]) <= 1e-6):
                            continue
                    elif PARAMS["pulse_grids"] and self.node_ids[p["grid"]] not in PARAMS["pulse_grids"]:
                        continue
                    gpos = self.grid_pos.get(p["grid"])
                    burn = p["share"] * (float(G_bar[gpos]) if gpos is not None else p["deliverable"])
                    if si is not None and float(stock[si]) < PARAMS["pulse_weeks"] * burn:
                        flows[s_] = 0.0
            except Exception:
                pass
        if self.pplan is not None:
            try:
                rel = self.pplan.plan(observation, self.planned_arrivals, deadline=start + PARAMS["pp_deadline"])
                for s_, q in rel.items():
                    if np.isfinite(q):
                        flows[s_] = q
            except Exception:
                pass
        if PARAMS["jp_fill"] and self.ok:
            try:
                self._jp_fill(observation, flows)
            except Exception:
                pass
        if PARAMS["imit_grid"] and self.ok:
            try:
                self._imit_clip(observation, flows)
            except Exception:
                pass
        action = dict(action)
        action["flows"] = np.maximum(flows, 0.0) * observation["action_mask"]
        return action

    def _jp_grid(self, g):
        if PARAMS["jp_grids"]:
            return self.node_ids[g] in PARAMS["jp_grids"]
        return bool(self.grid_has_fab.get(g))

    def _grid_arrivals(self, obs):
        week = int(obs["week"][0])
        arr = {}
        for edge, k, aw, qty, ok in zip(obs["pipeline.edge"], obs["pipeline.k"], obs["pipeline.arrival_week"],
                                        obs["pipeline.qty"], obs["pipeline.qty.observed"]):
            if ok and int(aw) == week:
                p_i = self.grid_arr_keys.get((self.edges["head"][int(edge)], int(k)))
                if p_i is not None:
                    arr[p_i] = arr.get(p_i, 0.0) + float(qty)
        return arr

    def _jp_fill(self, obs, flows):
        """Task 30: release at least what fills this week's segment of the listed fuels (they are not rationed, so
        holding them at the terminal only sheds homes now and darkens the fabs)."""
        stock, seen = obs["stock.qty"], obs["stock.qty.observed"]
        G_bar = obs["graph_now.grid.G_bar"]
        arr = self._grid_arrivals(obs)
        for s_, si, p_i in self.tg_slots:
            p = self.pools[p_i]
            if self.commodities[p["k"]] not in PARAMS["jp_fill"] or not self._jp_grid(p["grid"]) or si is None:
                continue
            gi = self.stock_index.get((p["grid"], p["k"]))
            if gi is None or not seen[gi] or not seen[si]:
                continue
            gpos = self.grid_pos.get(p["grid"])
            cap = p["share"] * (float(G_bar[gpos]) if gpos is not None else p["deliverable"])
            need = cap - float(stock[gi]) - arr.get(p_i, 0.0)
            if need > 0:
                flows[s_] = max(flows[s_], min(need, float(stock[si])))

    def _imit_clip(self, obs, flows):
        """Task 26: cap each terminal -> grid release so the grid ends the week at most full (or at the target)."""
        week = int(obs["week"][0])
        stock, seen = obs["stock.qty"], obs["stock.qty.observed"]
        G_bar = obs["graph_now.grid.G_bar"]
        arr = {}
        for edge, k, aw, qty, ok in zip(obs["pipeline.edge"], obs["pipeline.k"], obs["pipeline.arrival_week"],
                                        obs["pipeline.qty"], obs["pipeline.qty.observed"]):
            if ok and int(aw) == week:
                p_i = self.grid_arr_keys.get((self.edges["head"][int(edge)], int(k)))
                if p_i is not None:
                    arr[p_i] = arr.get(p_i, 0.0) + float(qty)
        for s_, _si, p_i in self.tg_slots:
            p = self.pools[p_i]
            gi = self.stock_index.get((p["grid"], p["k"]))
            if gi is None or not seen[gi]:
                continue
            I = float(stock[gi])
            gpos = self.grid_pos.get(p["grid"])
            cap = p["share"] * (float(G_bar[gpos]) if gpos is not None else p["deliverable"])
            thr = self.psi * p["ibar"] if p["rationed"] else 0.0
            ration = 1.0 if thr <= 0 or I >= thr else I / thr
            burn = PARAMS["imit_burn"] * cap * ration
            lim = self.grid_store[p_i] - I - arr.get(p_i, 0.0) + burn
            if PARAMS["imit_grid"] == "target":
                lim = min(lim, thr + PARAMS["imit_margin"] * cap + cap * ration - I - arr.get(p_i, 0.0))
            flows[s_] = min(flows[s_], max(lim, 0.0))

    def _plan(self, obs, flows, start):
        H = int(PARAMS["H"])
        week = int(obs["week"][0])
        T_left = H
        P, S = len(self.pools), len(self.lp_slots)
        if P == 0 or S == 0:
            return None
        tau = obs["graph_now.tau"]
        u = obs["graph_now.u"]
        c = obs["graph_now.c"]
        open_now = np.where(obs["graph_now.open.observed"] == 1, obs["graph_now.open"], 1.0)
        mask = obs["action_mask"]
        stock, stock_seen = obs["stock.qty"], obs["stock.qty.observed"]
        G_bar = obs["graph_now.grid.G_bar"]
        warn = obs.get("warning.score")

        # pool stock now and fixed arrivals over the window
        I0 = np.zeros(P)
        for (node, k), p_i in self.feeds.items():
            idx = self.stock_index.get((node, k))
            if idx is not None and stock_seen[idx]:
                I0[p_i] += float(stock[idx])
        fixed_in = np.zeros((P, H))
        for edge, k, lane, qty, arr, seen, lane_seen in zip(
            obs["pipeline.edge"], obs["pipeline.k"], obs["pipeline.lane"], obs["pipeline.qty"],
            obs["pipeline.arrival_week"], obs["pipeline.qty.observed"], obs["pipeline.lane.observed"],
        ):
            if not seen:
                continue
            rest = self.lane_rest.get((int(lane), int(edge)), []) if lane_seen else []
            dest = self.edges["head"][rest[-1]] if rest else self.edges["head"][int(edge)]
            p_i = self.feeds.get((dest, int(k)))
            if p_i is None:
                continue
            off = int(arr) - week + sum(int(tau[e]) for e in rest)
            fixed_in[p_i, min(max(off, 0), H - 1)] += float(qty)
        queue_tb = {}  # chokepoint position -> tanker cargo queued there (kappa_lp)
        if self.lot_keys is not None and "queue_lots.qty" in obs:
            queued = obs["queue_lots.qty"].sum(axis=1)
            drain = _pplan.queue_release(obs, self.lot_keys, self.chk_node_pos, self.tb_k, H, PARAMS["jp_qedge"]) if PARAMS["kappa_lp"] else {}
            for row, (chk_node, k, lane_key, next_edge) in enumerate(self.lot_keys):
                if queued[row] <= 0:
                    continue
                if row in drain:
                    pos = self.chk_node_pos.get(chk_node)
                    if pos is not None:
                        queue_tb[pos] = queue_tb.get(pos, 0.0) + float(queued[row])
                    lane = self.lane_index.get(lane_key, lane_key) if not isinstance(lane_key, (int, np.integer)) else lane_key
                    rest = self.lane_rest.get((lane, next_edge), []) if lane is not None else []
                    route = [next_edge] + rest
                    p_i = self.feeds.get((self.edges["head"][route[-1]], int(k)))
                    if p_i is None:
                        continue
                    lead_q = sum(int(tau[e]) for e in route)
                    for o, qd in enumerate(drain[row]):
                        if o + lead_q < H and qd > 0:
                            fixed_in[p_i, o + lead_q] += float(qd)
                    continue
                pos = self.chk_node_pos.get(chk_node)
                if pos is not None and open_now[pos] < 0.5:
                    continue
                lane = self.lane_index.get(lane_key, lane_key) if not isinstance(lane_key, (int, np.integer)) else lane_key
                rest = self.lane_rest.get((lane, next_edge), []) if lane is not None else []
                route = [next_edge] + rest
                dest = self.edges["head"][route[-1]]
                p_i = self.feeds.get((dest, int(k)))
                if p_i is None:
                    continue
                off = sum(int(tau[e]) for e in route)
                fixed_in[p_i, min(off, H - 1)] += float(queued[row])

        # burn per week, thresholds
        burn = np.zeros(P)
        floor = np.zeros(P)
        thr = np.zeros(P)
        cap = np.zeros(P)
        voll = np.zeros(P)
        for p_i, p in enumerate(self.pools):
            gpos = self.grid_pos.get(p["grid"])
            G = float(G_bar[gpos]) if gpos is not None else p["deliverable"]
            burn[p_i] = p["share"] * G
            thr[p_i] = self.psi * p["ibar"] if p["rationed"] else 0.0
            sw = PARAMS["safety_weeks"]
            if PARAMS["jp_safety"] and self._jp_grid(p["grid"]):
                sw = float(PARAMS["jp_safety"].get(self.commodities[p["k"]], sw))
            floor[p_i] = max(thr[p_i] + sw * burn[p_i],
                             PARAMS["cover_frac"] * p["cover_days"] / 7.0 * burn[p_i])
            cap[p_i] = max(p["cap"], floor[p_i] + burn[p_i])
            voll[p_i] = p["voll"] * (1.0 + PARAMS["fab_boost"] * self.grid_has_fab.get(p["grid"], 0.0))

        # variable layout: x[s, t] (S*H), b[p, t] burn served (P*H), I[p, t] stock (P*H), r[p, t] floor deficit (P*H),
        # o[p, t] overflow (P*H)
        nx = S * H
        nb = P * H
        off_b, off_I, off_r, off_o = nx, nx + nb, nx + 2 * nb, nx + 3 * nb
        off_q = nx + 4 * nb
        off_sf = nx + 5 * nb  # burn the stock could not cover (the grid burns whatever it has: no saving fuel)
        n = nx + 6 * nb
        cost = np.zeros(n)
        lo = np.zeros(n)
        hi = np.full(n, np.inf)

        lead = np.zeros(S, dtype=int)
        for j, ls in enumerate(self.lp_slots):
            route = ls["route"]
            lead[j] = sum(int(tau[e]) for e in route)
            freight = sum(float(c[e]) for e in route)
            slot_cap = min(float(u[e]) for e in route) if mask[ls["slot"]] else 0.0
            open_frac = min((float(open_now[q]) for q in ls["chk"]), default=1.0)
            for t in range(H):
                v = j * H + t
                cost[v] = freight
                factor = (1.0 if open_frac > 1e-9 else 0.0) if PARAMS["nd_open_e"] else open_frac
                if t > 0 and warn is not None and PARAMS["warn_gain"] > 0:
                    for q in ls["chk"]:
                        wi = self.warn_chk.get(q)
                        if wi is not None:
                            factor *= max(0.0, 1.0 - PARAMS["warn_gain"] * float(warn[wi]))
                hi[v] = slot_cap * max(factor, 0.0)

        # pending prohibitions: a slot whose route has an edge banned from week w ships nothing from then on
        if "pending_prohibitions.edge" in obs:
            banned = {}
            for e, k, w, seen in zip(obs["pending_prohibitions.edge"], obs["pending_prohibitions.k"],
                                     obs["pending_prohibitions.effective_week"],
                                     obs["pending_prohibitions.edge.observed"]):
                if seen:
                    key = (int(e), int(k))
                    banned[key] = min(banned.get(key, 10**9), int(w))
            for j, ls in enumerate(self.lp_slots):
                for e in ls["route"]:
                    w = banned.get((e, ls["k"]))
                    if w is not None:
                        for t in range(max(w - week, 0), H):
                            hi[j * H + t] = 0.0

        for p_i in range(P):
            for t in range(H):
                lo[off_b + p_i * H + t] = burn[p_i]  # the simulator burns it whenever the stock allows
                hi[off_b + p_i * H + t] = burn[p_i]
                cost[off_sf + p_i * H + t] = voll[p_i]
                hi[off_I + p_i * H + t] = cap[p_i]
                cost[off_I + p_i * H + t] = 1.0  # a little holding, to not overstock
                # a unit below the rationing floor cuts output ~ burn/floor units, each at VOLL
                cost[off_r + p_i * H + t] = PARAMS["safety_cost"] * voll[p_i] * burn[p_i] / max(floor[p_i], 1.0)
                # below the rationing line output falls by burn / threshold per unit, shed at VOLL
                cost[off_q + p_i * H + t] = PARAMS["ration_cost"] * voll[p_i] * burn[p_i] / max(thr[p_i], 1.0)
                if thr[p_i] <= 0:
                    hi[off_q + p_i * H + t] = 0.0
                cost[off_o + p_i * H + t] = PARAMS["lp_overflow_cost"]
            # end of window: value stock up to end_weeks of burn
            cost[off_I + p_i * H + H - 1] -= 0.05 * voll[p_i] * 0  # kept simple: handled by the floor rows

        rows, cols, vals, rhs_eq = [], [], [], []
        r = 0
        # balance: I[t] - I[t-1] - sum arrivals x + b + o = fixed_in[t]  (I[-1] = I0)
        for p_i in range(P):
            for t in range(H):
                rows += [r, r, r, r]
                cols += [off_I + p_i * H + t, off_b + p_i * H + t, off_o + p_i * H + t, off_sf + p_i * H + t]
                vals += [1.0, 1.0, 1.0, -1.0]
                if t > 0:
                    rows.append(r); cols.append(off_I + p_i * H + t - 1); vals.append(-1.0)
                for j, ls in enumerate(self.lp_slots):
                    if ls["pool"] != p_i:
                        continue
                    t_ship = t - lead[j]
                    if 0 <= t_ship < H:
                        rows.append(r); cols.append(j * H + t_ship); vals.append(-1.0)
                rhs_eq.append(fixed_in[p_i, t] + (I0[p_i] if t == 0 else 0.0))
                r += 1
        A_eq = coo_matrix((vals, (rows, cols)), shape=(r, n)).tocsr()

        rows, cols, vals, rhs_ub = [], [], [], []
        r = 0
        # floor: -I[t] - r[t] <= -floor   (end of window wants end_weeks of burn)
        for p_i in range(P):
            for t in range(H):
                want = floor[p_i] + (PARAMS["end_weeks"] * burn[p_i] if t == H - 1 else 0.0)
                rows += [r, r]; cols += [off_I + p_i * H + t, off_r + p_i * H + t]; vals += [-1.0, -1.0]
                rhs_ub.append(-min(want, cap[p_i]))
                r += 1
                if thr[p_i] > 0:
                    rows += [r, r]; cols += [off_I + p_i * H + t, off_q + p_i * H + t]; vals += [-1.0, -1.0]
                    rhs_ub.append(-min(thr[p_i], cap[p_i]))
                    r += 1
        # shared edge capacity: each edge's slots together <= its capacity
        by_edge = {}
        for j, ls in enumerate(self.lp_slots):
            for e in ls["route"]:
                by_edge.setdefault(e, []).append(j)
        for e, js in by_edge.items():
            if len(js) < 2:
                continue
            for t in range(H):
                for j in js:
                    rows.append(r); cols.append(j * H + t); vals.append(1.0)
                rhs_ub.append(float(u[e]))
                r += 1
        # tanker throughput (kappa_lp): the LP's lanes through a chokepoint share its kappa_tb each week (what already
        # waits there drains at that rate, in fixed_in above). "backlog": new cargo also waits behind the queue
        if PARAMS["kappa_lp"]:
            kap = obs["graph_now.kappa.tb"]
            by_chk = {}
            for j, ls in enumerate(self.lp_slots):
                if ls["k"] in self.tb_k:
                    for q in ls["chk"]:
                        by_chk.setdefault(q, []).append(j)
            for q, js in by_chk.items():
                kc = float(kap[q])
                for t in range(H):
                    if PARAMS["kappa_lp"] == "backlog":
                        for j in js:
                            for tt in range(t + 1):
                                rows.append(r); cols.append(j * H + tt); vals.append(1.0)
                        rhs_ub.append(max(0.0, (t + 1) * kc - queue_tb.get(q, 0.0)))
                    else:
                        for j in js:
                            rows.append(r); cols.append(j * H + t); vals.append(1.0)
                        rhs_ub.append(kc)
                    r += 1
        # source supply: cumulative shipments <= stock + supply per week
        by_source = {}
        for j, ls in enumerate(self.lp_slots):
            by_source.setdefault((ls["source"], ls["k"]), []).append(j)
        supply = obs["graph_now.supply.avail"]
        for (node, k), js in by_source.items():
            idx = self.stock_index.get((node, k))
            s0 = float(stock[idx]) if idx is not None and stock_seen[idx] else 0.0
            sidx = self.supply_index.get((node, k))
            per_week = float(supply[sidx]) if sidx is not None else 0.0
            for t in range(H):
                for j in js:
                    for tt in range(t + 1):
                        rows.append(r); cols.append(j * H + tt); vals.append(1.0)
                rhs_ub.append(s0 + t * per_week)
                r += 1
        A_ub = coo_matrix((vals, (rows, cols)), shape=(r, n)).tocsr()

        if time.process_time() - start > PARAMS["time_limit"]:
            return None
        res = linprog(cost, A_ub=A_ub, b_ub=np.array(rhs_ub), A_eq=A_eq, b_eq=np.array(rhs_eq),
                      bounds=np.column_stack([lo, hi]), method="highs")
        if res.status != 0:
            return None
        x = res.x
        for j, ls in enumerate(self.lp_slots):
            flows[ls["slot"]] = x[j * H]
        if self.pplan is not None:
            # the plan's future shipments, by destination, for the pulse planner (this week's included: not in the
            # pipeline yet)
            planned = {}
            direct = self.pplan.direct_slots
            other = {}  # (source, k) -> shipments per week of the LP's slots the planner does not control
            direct_arr = {}  # direct slot -> its planned arrivals (the planner replaces them with its own)
            for j, ls in enumerate(self.lp_slots):
                key = (self.edges["head"][ls["route"][-1]], ls["k"])
                for t in range(H):
                    o = t + lead[j]
                    q = x[j * H + t]
                    if q <= 1e-9:
                        continue
                    if o < H:
                        planned.setdefault(key, np.zeros(H))[o] += q
                        if ls["slot"] in direct:
                            direct_arr.setdefault(ls["slot"], np.zeros(H))[o] += q
                    if ls["slot"] not in direct:
                        other.setdefault((ls["source"], ls["k"]), np.zeros(H))[t] += q
            self.planned_arrivals = planned
            self.pplan.other_use = other
            self.pplan.direct_arr = direct_arr
        return flows
