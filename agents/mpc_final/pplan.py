"""Planned pulses: per grid that feeds fabs, a small MILP chooses how much fuel each terminal -> grid slot releases.

Why timing matters (simulator step 7, ``base_first`` grids): the grid's available output is
``G_av = sum_k min(s_k G, ration_k s_k G, fuel on hand_k) + s_null G``, homes get ``min(y_bar, G_av)`` and fabs only
the leftover. G-bar is about y-bar plus the fabs' full draw, so a grid that is a little short every week never powers
its fabs, while a grid fully supplied in some weeks powers them in those weeks. Fuel is energy either way (homes lose
what the fabs gain), so pulsing pays when a unit of fab energy (R / e wafers, each a chip worth its sink's pi) is worth
more than VOLL. The rationed fuel's output is also cut by ``I_prev / (psi I-bar)`` when last week's grid stock is under
the line, which the plan has to respect: holding fuel at the terminal empties the grid and rations the next week.

The MILP follows, week by week over ``H`` weeks, each controlled fuel's terminal stock and grid stock exactly as the
simulator does (dispatch from last week's terminal stock, terminal arrivals usable the week after, grid output the
three-way min with binaries, burn = output, disposal above storage) and the grid's homes-first split with one binary
per week (fabs get power only in weeks the homes are fully served). Fuels without a terminal slot do not depend on the
plan and are simulated ahead in numpy. It maximises VOLL * homes served + V * fab energy + a value on fuel left at
the end, and the first week's releases are played. Anything that fails leaves the slots as they were.
"""

import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix


def queue_release(obs, lot_keys, chk_pos, tb_k, H):
    """{lot row: array H} of the quantity each queued tanker lot row releases in week + o (task 18, ``kappa_lp``).

    The simulator's default release (chokepoint.py, (10)) drains a chokepoint's queue FIFO by cohort (the week the lots
    reached it), pro rata inside a cohort, at most kappa_tb a week for the tanker pool. A closed chokepoint (open < 0.5)
    releases nothing. Rows of other pools are left out (the caller keeps its old rule for them).
    """
    q = obs["queue_lots.qty"]
    kap = obs["graph_now.kappa.tb"]
    open_now = np.where(obs["graph_now.open.observed"] == 1, obs["graph_now.open"], 1.0)
    by_chk = {}
    for row, (chk_node, k, _lane, _next) in enumerate(lot_keys):
        if int(k) in tb_k and q[row].sum() > 0:
            by_chk.setdefault(chk_node, []).append(row)
    out = {}
    for chk_node, rows in by_chk.items():
        pos = chk_pos.get(chk_node)
        kc = float(kap[pos]) if pos is not None else np.inf
        if pos is not None and open_now[pos] < 0.5:
            kc = 0.0
        sub = q[rows]  # rows x cohorts
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


class PulsePlanner:
    def __init__(self, config, H=8, value_scale=0.5, end_value=0.9, time_limit=0.3, method="enum", enum_H=6,
                 direct_grids=(), kappa=False, split=False):
        self.H, self.value_scale, self.end_value, self.time_limit = int(H), float(value_scale), float(end_value), \
            float(time_limit)
        self.method, self.enum_H = method, int(enum_H)
        static, layout = config["static"], config["layout"]
        inst = static["instance"]
        nodes = inst["nodes"]
        ids = [n["id"] for n in nodes]
        commodities = static["commodities"]["id"]
        edges, slots = static["edges"], static["action_slots"]
        self.edges = edges
        self.psi = float(inst["params"].get("psi", 0.6))
        self.stock_index = {tuple(row): i for i, row in enumerate(layout["stock_slots"])}
        lanes = static["lanes"]
        self.lane_rest = {}
        for li, route in enumerate(lanes["edges"]):
            for j, e in enumerate(route):
                self.lane_rest[(li, e)] = list(route[j + 1:])
        self.lane_index = {lid: i for i, lid in enumerate(lanes["id"])} if "id" in lanes else {}
        self.lot_keys = layout.get("lot_keys")
        self.chk_pos = {node: i for i, node in enumerate(layout["chokepoints"])}
        self.supply_index = {tuple(row): i for i, row in enumerate(layout["supply_slots"])}
        self.kappa = bool(kappa)
        self.split = int(split)
        pools = static["commodities"].get("pool") or []
        self.tb_k = {k for k, p in enumerate(pools) if p == "tb"}
        self.direct_slots = set()
        self.other_use = {}  # (source, k) -> the energy LP's other shipments from that source per week (set by the agent)
        self.direct_arr = {}  # direct slot -> the energy LP's planned arrivals through it (set by the agent)

        # chip value per raw chip: the best pi among the sinks of the packaged chip it becomes
        sk = static["sinks"]
        pi_k = {}
        for k, p in zip(sk["k"], sk["pi"]):
            pi_k[int(k)] = max(pi_k.get(int(k), 0.0), float(p))
        raw_pi = {}
        for o in layout["osats"]:
            for raw, pk in nodes[o]["osat"]["packages"].items():
                kr, kp = commodities.index(raw), commodities.index(pk)
                raw_pi[kr] = max(raw_pi.get(kr, 0.0), pi_k.get(kp, 0.0))

        self.grids = []
        for gpos, g in enumerate(layout["grids"]):
            spec = nodes[g]["grid"]
            if spec.get("priority", "base_first") != "base_first":
                continue
            fabs = []
            for fpos, f in enumerate(layout["fabs"]):
                fab = nodes[f]["fab"]
                if fab.get("grid") != ids[g] or float(fab.get("e", 0.0)) <= 0:
                    continue
                kin = commodities.index(fab["input"])
                fabs.append({"pos": fpos, "node": f, "e": float(fab["e"]), "win": self.stock_index.get((f, kin)),
                             "kin": kin, "pi": raw_pi.get(commodities.index(fab["product"]), 0.0)})
            if not fabs:
                continue
            fuels, null_share = [], 0.0
            for fuel, share in spec["shares"].items():
                if fuel not in commodities:
                    null_share += float(share)
                    continue
                k = commodities.index(fuel)
                gslot = self.stock_index.get((g, k))
                if gslot is None or share <= 0:
                    null_share += float(share)
                    continue
                fuels.append({
                    "k": k, "share": float(share), "gslot": gslot,
                    "thr": self.psi * float(spec.get("ibar", {}).get(fuel, 0.0)) if spec.get("rationed") == fuel else 0.0,
                    "storG": float(nodes[g].get("stock", {}).get(fuel, {}).get("storage", np.inf) or np.inf),
                    "term": None, "tslot": None, "storT": np.inf, "slot": None, "edge": None,
                })
            # terminal -> grid action slots (one per fuel)
            for s, (edge, k) in enumerate(zip(slots["edge"], slots["k"])):
                tail, head = edges["tail"][edge], edges["head"][edge]
                if head != g or nodes[tail].get("type") != "terminal":
                    continue
                for fu in fuels:
                    if fu["k"] == k and self.stock_index.get((tail, k)) is not None:
                        fu.update(term=tail, tslot=self.stock_index[(tail, k)], slot=s, edge=edge,
                                  storT=float(nodes[tail].get("stock", {}).get(commodities[k], {}).get("storage", np.inf)
                                              or np.inf))
            # task 18 (``direct_grids``): the rationed fuel's direct source -> grid pipelines are timed too (CN gets most of
            # its gas straight from src_ru_gas, which the terminal pulse cannot hold back). The source's stock plays the
            # terminal; a release lands after the pipe's tau (1 week on Full), so it is sized for that week
            if ids[g] in direct_grids:
                for s, (edge, k) in enumerate(zip(slots["edge"], slots["k"])):
                    tail, head = edges["tail"][edge], edges["head"][edge]
                    if head != g or nodes[tail].get("type") != "source":
                        continue
                    for fu in fuels:
                        if fu["k"] == k and fu["thr"] > 0 and self.stock_index.get((tail, k)) is not None \
                                and (tail, k) in self.supply_index:
                            stor = nodes[tail].get("stock", {}).get(commodities[k], {}).get("storage", np.inf)
                            fu.setdefault("pipes", []).append({
                                "slot": s, "edge": edge, "src": tail, "sslot": self.stock_index[(tail, k)],
                                "sidx": self.supply_index[(tail, k)], "stor": float(stor or np.inf)})
                            self.direct_slots.add(s)
            if not any(fu["slot"] is not None for fu in fuels):
                continue
            self.grids.append({"node": g, "gpos": gpos, "voll": float(spec.get("voll", 4e6)), "fuels": fuels,
                               "null": null_share, "fabs": fabs})

    # -------------------------------------------------------------- arrivals by destination node
    def arrivals(self, obs, planned=None):
        """{(node, k): array H} of quantities arriving (step 6) in week + o, from the pipeline, the chokepoint queues
        and ``planned`` (the energy LP's future shipments, same format)."""
        H = self.H
        week = int(obs["week"][0])
        tau = obs["graph_now.tau"]
        out = {}

        def add(node, k, o, q):
            if 0 <= o < H and q > 0:
                out.setdefault((node, k), np.zeros(H))[o] += q

        for edge, k, lane, qty, arr, seen, lane_seen in zip(
            obs["pipeline.edge"], obs["pipeline.k"], obs["pipeline.lane"], obs["pipeline.qty"],
            obs["pipeline.arrival_week"], obs["pipeline.qty.observed"], obs["pipeline.lane.observed"],
        ):
            if not seen:
                continue
            rest = self.lane_rest.get((int(lane), int(edge)), []) if lane_seen else []
            dest = self.edges["head"][rest[-1]] if rest else self.edges["head"][int(edge)]
            add(dest, int(k), int(arr) - week + sum(int(tau[e]) for e in rest), float(qty))
        if self.lot_keys is not None and "queue_lots.qty" in obs:
            open_now = np.where(obs["graph_now.open.observed"] == 1, obs["graph_now.open"], 1.0)
            queued = obs["queue_lots.qty"].sum(axis=1)
            drain = queue_release(obs, self.lot_keys, self.chk_pos, self.tb_k, H) if self.kappa else {}
            for row, (chk_node, k, lane_key, next_edge) in enumerate(self.lot_keys):
                if queued[row] <= 0:
                    continue
                if row in drain:
                    lane = self.lane_index.get(lane_key, lane_key) if not isinstance(lane_key, (int, np.integer)) else lane_key
                    rest = self.lane_rest.get((lane, next_edge), []) if lane is not None else []
                    route = [next_edge] + rest
                    lead = sum(int(tau[e]) for e in route)
                    for o, qd in enumerate(drain[row]):
                        add(self.edges["head"][route[-1]], int(k), o + lead, float(qd))
                    continue
                pos = self.chk_pos.get(chk_node)
                if pos is not None and open_now[pos] < 0.5:
                    continue
                lane = self.lane_index.get(lane_key, lane_key) if not isinstance(lane_key, (int, np.integer)) else lane_key
                rest = self.lane_rest.get((lane, next_edge), []) if lane is not None else []
                route = [next_edge] + rest
                add(self.edges["head"][route[-1]], int(k), sum(int(tau[e]) for e in route), float(queued[row]))
        if planned:
            for key, arr in planned.items():
                for o in range(min(H, len(arr))):
                    add(key[0], key[1], o, float(arr[o]))
        return out

    # -------------------------------------------------------------- plan
    def plan(self, obs, planned=None, deadline=None, fab_plan=None):
        """{action slot: release this week} for the terminal -> grid slots of the planned grids."""
        arr = self.arrivals(obs, planned)
        out = {}
        for gr in self.grids:
            if deadline is not None and time.process_time() > deadline:
                break
            try:
                res = self._plan_grid(obs, gr, arr, fab_plan)
            except Exception:
                res = None
            if res:
                out.update(res)
        return out

    def _plan_grid(self, obs, gr, arr, fab_plan=None):
        H = self.H
        gpos = gr["gpos"]
        G = float(obs["graph_now.grid.G_bar"][gpos])
        ybar = float(obs["graph_now.grid.y_bar"][gpos])
        voll = gr["voll"]
        stock, seen = obs["stock.qty"], obs["stock.qty.observed"]
        mask = obs["action_mask"]
        u = obs["graph_now.u"]

        # fab draw per week and the value of one unit of fab energy (VOLL units). With the chip LP's plan: its
        # planned starts and their shadow value per start (R / e starts per energy unit); without it: wafers tracked
        # from the pipeline as if the fab ran full, valued at the pi of the chips they become
        cap_eff, Rf = obs["graph_now.fab.cap_eff"], obs["graph_now.fab.R"]
        ehat = np.zeros(H)
        vsum = np.zeros(H)
        for fb in gr["fabs"]:
            R = float(Rf[fb["pos"]])
            if R <= 0:
                continue
            if fab_plan is not None and fb["pos"] in fab_plan:
                starts, mval = fab_plan[fb["pos"]]
                for t in range(min(H, len(starts))):
                    d = fb["e"] * float(starts[t]) / R
                    ehat[t] += d
                    vsum[t] += d * float(mval[t]) * R / fb["e"]
                continue
            w = float(stock[fb["win"]]) if fb["win"] is not None and seen[fb["win"]] else 0.0
            a = arr.get((fb["node"], fb["kin"]), np.zeros(H))
            c = float(cap_eff[fb["pos"]])
            for t in range(H):
                w += a[t]
                p = min(c, w)
                w -= p
                d = fb["e"] * p / R
                ehat[t] += d
                vsum[t] += d * fb["pi"] * R / fb["e"]
        if ehat.max() <= 1e-9:
            return None
        V = self.value_scale * np.where(ehat > 1e-12, vsum / np.maximum(ehat, 1e-12), 0.0) / voll
        if V.max() <= 1.0:
            return None  # fab energy is never worth more than homes: no reason to pulse

        # uncontrolled fuels: simulated ahead (they do not depend on the plan); controlled ones go to the MILP
        base = np.full(H, gr["null"] * G)
        ctrl = []
        for fu in gr["fuels"]:
            cap = fu["share"] * G
            I = float(stock[fu["gslot"]]) if seen[fu["gslot"]] else 0.0
            aG = arr.get((gr["node"], fu["k"]), np.zeros(H))
            if fu["slot"] is None or not mask[fu["slot"]]:
                Iprev = I
                for t in range(H):
                    pre = Iprev + aG[t]
                    ration = 1.0 if fu["thr"] <= 0 or Iprev >= fu["thr"] else Iprev / fu["thr"]
                    av = min(cap * ration, pre)
                    base[t] += av
                    Iprev = min(pre - av, fu["storG"])
                continue
            T = float(stock[fu["tslot"]]) if seen[fu["tslot"]] else 0.0
            aT = arr.get((fu["term"], fu["k"]), np.zeros(H))
            pipes = []
            for pp in fu.get("pipes", []):
                if not mask[pp["slot"]] or int(obs["graph_now.tau"][pp["edge"]]) != 1:
                    continue
                aG = aG - self.direct_arr.get(pp["slot"], np.zeros(H))[:H]  # replaced by the planner's releases
                pipes.append(dict(pp, S0=float(stock[pp["sslot"]]) if seen[pp["sslot"]] else 0.0,
                                  sup=float(obs["graph_now.supply.avail"][pp["sidx"]]),
                                  oth=self.other_use.get((pp["src"], fu["k"]), np.zeros(H))[:H]))
            pipes.sort(key=lambda pp: -float(u[pp["edge"]]))
            ctrl.append(dict(fu, cap=cap, I0=I, T0=T, aG=np.maximum(aG, 0.0), aT=aT, dpipes=pipes))
        if not ctrl:
            return None
        if self.method == "enum":
            return self._enum(gr, ctrl, base, ehat, ybar, V, obs)
        if any(fu["dpipes"] for fu in ctrl):
            return None  # the MILP models terminals only

        # ---- MILP variables
        n = 0
        idx = {}

        def var(name, t, k=None):
            nonlocal n
            idx[(name, t, k)] = n
            n += 1
            return n - 1

        lo, hi, integ, cost = [], [], [], []

        def new(name, t, k=None, l=0.0, h=np.inf, integer=False, c=0.0):
            v = var(name, t, k)
            lo.append(l); hi.append(h); integ.append(1 if integer else 0); cost.append(c)
            return v

        for t in range(H):
            new("y", t, l=0.0, h=ybar, c=-1.0)
            new("E", t, l=0.0, h=ehat[t], c=-V[t])
            new("z", t, l=0.0, h=1.0, integer=True)
            for j, fu in enumerate(ctrl):
                end = t == H - 1
                ev = -self.end_value if end else 0.0
                rmax = float(u[fu["edge"]])
                new("r", t, j, h=rmax)
                new("T", t, j, h=fu["storT"], c=ev + 1e-6)
                new("dT", t, j, c=1e-3)
                new("I", t, j, h=fu["storG"], c=ev + 1e-6)
                new("dG", t, j, c=1e-3)
                new("av", t, j, h=fu["cap"])
                nb = 3 if (fu["thr"] > 0 and t > 0) else 2
                for b in range(nb):
                    new(f"b{b}", t, j, h=1.0, integer=True)

        rows, cols, vals, rlo, rhi = [], [], [], [], []
        r = 0

        def row(terms, l, h):
            nonlocal r
            for v, c in terms:
                rows.append(r); cols.append(v); vals.append(c)
            rlo.append(l); rhi.append(h)
            r += 1

        for t in range(H):
            y, E, z = idx[("y", t, None)], idx[("E", t, None)], idx[("z", t, None)]
            # homes first: y + E <= base + sum av; E <= ehat z; y >= ybar z
            row([(y, 1.0), (E, 1.0)] + [(idx[("av", t, j)], -1.0) for j in range(len(ctrl))], -np.inf, base[t])
            row([(E, 1.0), (z, -ehat[t])], -np.inf, 0.0)
            row([(y, 1.0), (z, -ybar)], 0.0, np.inf)
            # shared edge capacity
            by_edge = {}
            for j, fu in enumerate(ctrl):
                by_edge.setdefault(fu["edge"], []).append(j)
            for e, js in by_edge.items():
                if len(js) > 1:
                    row([(idx[("r", t, j)], 1.0) for j in js], -np.inf, float(u[e]))
            for j, fu in enumerate(ctrl):
                rv, Tv, dTv, Iv, dGv, av = (idx[(nm, t, j)] for nm in ("r", "T", "dT", "I", "dG", "av"))
                Tp = idx[("T", t - 1, j)] if t > 0 else None
                Ip = idx[("I", t - 1, j)] if t > 0 else None
                T0 = fu["T0"] if t == 0 else 0.0
                I0 = fu["I0"] if t == 0 else 0.0
                # dispatch from last week's terminal stock: r <= T[t-1]
                row([(rv, 1.0)] + ([(Tp, -1.0)] if Tp is not None else []), -np.inf, T0)
                # terminal: T = T[t-1] - r + aT - dT
                row([(Tv, 1.0), (rv, 1.0), (dTv, 1.0)] + ([(Tp, -1.0)] if Tp is not None else []),
                    T0 + fu["aT"][t], T0 + fu["aT"][t])
                # grid: I = I[t-1] + r + aG - av - dG
                row([(Iv, 1.0), (rv, -1.0), (av, 1.0), (dGv, 1.0)] + ([(Ip, -1.0)] if Ip is not None else []),
                    I0 + fu["aG"][t], I0 + fu["aG"][t])
                # av <= on hand: av - r - I[t-1] <= I0 + aG
                pre = [(rv, -1.0)] + ([(Ip, -1.0)] if Ip is not None else [])
                row([(av, 1.0)] + pre, -np.inf, I0 + fu["aG"][t])
                cap = fu["cap"]
                rationed = fu["thr"] > 0
                cap_t = cap * min(1.0, fu["I0"] / fu["thr"]) if rationed and t == 0 else cap
                storG = fu["storG"] if np.isfinite(fu["storG"]) else 1e7
                # tight big-Ms: each bound's own range
                M0 = cap_t
                M1 = (fu["I0"] if t == 0 else storG) + float(u[fu["edge"]]) + fu["aG"][t]
                # av >= cap_t - M0 (1 - b0)
                b0, b1 = idx[("b0", t, j)], idx[("b1", t, j)]
                row([(av, 1.0), (b0, -M0)], cap_t - M0, np.inf)
                # av >= on hand - M1 (1 - b1)  ->  av - r - I[t-1] - M1 b1 >= I0 + aG - M1
                row([(av, 1.0), (b1, -M1)] + pre, I0 + fu["aG"][t] - M1, np.inf)
                bs = [b0, b1]
                if rationed and t > 0:
                    b2 = idx[("b2", t, j)]
                    k_r = cap / fu["thr"]
                    M2 = k_r * storG
                    # av <= cap I[t-1] / thr
                    row([(av, 1.0), (Ip, -k_r)], -np.inf, 0.0)
                    # av >= cap I[t-1] / thr - M2 (1 - b2)
                    row([(av, 1.0), (Ip, -k_r), (b2, -M2)], -M2, np.inf)
                    bs.append(b2)
                row([(b, 1.0) for b in bs], 1.0, 1.0)

        A = coo_matrix((vals, (rows, cols)), shape=(r, n)).tocsr()
        res = milp(np.array(cost), constraints=LinearConstraint(A, np.array(rlo), np.array(rhi)),
                   integrality=np.array(integ), bounds=Bounds(np.array(lo), np.array(hi)),
                   options={"time_limit": self.time_limit, "mip_rel_gap": 1e-3})
        if res.x is None or res.status not in (0, 1):
            return None
        x = res.x
        return {fu["slot"]: max(0.0, float(x[idx[("r", 0, j)]])) for j, fu in enumerate(ctrl)}

    # -------------------------------------------------------------- enumeration
    def _enum(self, gr, ctrl, base, ehat, ybar, V, obs):
        """Every sequence of weekly release modes over ``enum_H`` weeks, simulated exactly (vectorised).

        Modes, the same for every controlled fuel in a week: 0 hold (release nothing), 1 release what makes this
        week's output full and nothing more, 2 the same plus the rationing line psi I-bar left in stock for next week,
        3 release everything (the default).
        """
        H = min(self.enum_H, self.H)
        # pp_split: a 5th mode when the grid has a rationed and an unrationed controlled fuel: the rationed fuel
        # recharges (mode 2) while the others are held at the terminal for a later full week
        split = self.split and any(fu["thr"] > 0 for fu in ctrl) and any(fu["thr"] <= 0 for fu in ctrl)
        modes = (4 + min(self.split, 2)) if split else 4
        N = modes ** H
        seq = (np.arange(N)[:, None] // (modes ** np.arange(H)[None, :])) % modes  # (N, H), week 0 = digit 0
        u = obs["graph_now.u"]
        F = len(ctrl)
        T = [np.full(N, fu["T0"]) for fu in ctrl]
        I = [np.full(N, fu["I0"]) for fu in ctrl]
        fly = [np.zeros(N) for _ in ctrl]  # direct pipes: released last week, lands this week
        S = [[np.full(N, pp["S0"]) for pp in fu["dpipes"]] for fu in ctrl]
        d0 = {}
        value = np.zeros(N)
        r0 = [None] * F
        for t in range(H):
            m_all = seq[:, t]
            av = []
            pre_all = []
            rel_all = []
            for j, fu in enumerate(ctrl):
                cap = fu["cap"]
                thr = fu["thr"]
                ration = np.ones(N) if thr <= 0 else np.minimum(1.0, I[j] / thr)
                cap_t = cap * ration
                have = I[j] + fu["aG"][t] + fly[j]
                m = np.where(m_all == 4, 2 if thr > 0 else 0, np.where(m_all == 5, 1 if thr > 0 else 0, m_all))
                limit = np.minimum(T[j], float(u[fu["edge"]]))
                want = np.where(m == 0, 0.0,
                       np.where(m == 1, np.maximum(cap_t - have, 0.0),
                       np.where(m == 2, np.maximum(cap_t + thr - have, 0.0), limit)))
                rel = np.minimum(want, limit)
                rel_all.append(rel)
                pre = have + rel
                pre_all.append(pre)
                av.append(np.minimum(cap_t, pre))
            # shared edge capacity: scale releases on an edge pro rata, as the simulator's joint clip does
            by_edge = {}
            for j, fu in enumerate(ctrl):
                by_edge.setdefault(fu["edge"], []).append(j)
            for e, js in by_edge.items():
                if len(js) > 1:
                    tot = sum(rel_all[j] for j in js)
                    f = np.where(tot > float(u[e]), float(u[e]) / np.maximum(tot, 1e-12), 1.0)
                    if np.any(f < 1.0):
                        for j in js:
                            pre_all[j] = pre_all[j] - rel_all[j] * (1.0 - f)
                            rel_all[j] = rel_all[j] * f
                            thr = ctrl[j]["thr"]
                            ration = np.ones(N) if thr <= 0 else np.minimum(1.0, I[j] / thr)
                            av[j] = np.minimum(ctrl[j]["cap"] * ration, pre_all[j])
            g = base[t] + sum(av)
            y = np.minimum(ybar, g)
            E = np.minimum(ehat[t], np.maximum(g - y, 0.0))
            load = np.where(g > 0, (y + E) / np.maximum(g, 1e-12), 0.0)
            value += y + V[t] * E
            m_next = seq[:, t + 1] if t + 1 < H else np.ones(N, dtype=int)
            m_next = np.where(m_next == 4, 2, np.where(m_next == 5, 1, m_next))  # pipes carry the rationed fuel
            for j, fu in enumerate(ctrl):
                I[j] = np.minimum(pre_all[j] - av[j] * load, fu["storG"])
                T[j] = np.minimum(T[j] - rel_all[j] + fu["aT"][t], fu["storT"])
                if t == 0:
                    r0[j] = rel_all[j]
                if not fu["dpipes"]:
                    continue
                # pipes: this week's release lands next week, sized by next week's mode (the terminal tops up after)
                thr = fu["thr"]
                cap_n = fu["cap"] * (np.ones(N) if thr <= 0 else np.minimum(1.0, I[j] / thr))
                have_n = I[j] + (fu["aG"][t + 1] if t + 1 < H else 0.0)
                lims = []
                for p_i, pp in enumerate(fu["dpipes"]):
                    S[j][p_i] = np.maximum(S[j][p_i] - (float(pp["oth"][t]) if t < len(pp["oth"]) else 0.0), 0.0)
                    lims.append(np.minimum(S[j][p_i], float(u[pp["edge"]])))
                want = np.where(m_next == 0, 0.0,
                       np.where(m_next == 1, np.maximum(cap_n - have_n, 0.0),
                       np.where(m_next == 2, np.maximum(cap_n + thr - have_n, 0.0), sum(lims))))
                fly[j] = np.zeros(N)
                for p_i, pp in enumerate(fu["dpipes"]):
                    rel = np.minimum(want, lims[p_i])
                    want = want - rel
                    fly[j] = fly[j] + rel
                    S[j][p_i] = np.minimum(S[j][p_i] - rel + pp["sup"], pp["stor"])
                    if t == 0:
                        d0[pp["slot"]] = rel
        value += self.end_value * sum(T[j] + I[j] + fly[j] + sum(S[j]) for j in range(F))
        best = value.max()
        # among (near-)ties prefer the default (release everything) in week 0, then the smaller digit sum
        cand = np.flatnonzero(value >= best - 1e-9 * max(1.0, abs(best)))
        default = cand[seq[cand, 0] == 3]
        b = int(default[0]) if len(default) else int(cand[0])
        out = {fu["slot"]: float(r0[j][b]) for j, fu in enumerate(ctrl)}
        out.update({s_: float(r[b]) for s_, r in d0.items()})
        return out
