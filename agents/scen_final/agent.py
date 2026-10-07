"""The organisers' ``mpc_scen`` baseline behind the flat agent interface: the final version of ``agents/scen``.

``sbfv/`` is shockbench-flow 0.1.2 (MIT, see ``sbfv/LICENSE``) with its imports renamed from ``shockbench_flow``, so it
runs where that package is not installed. Its LP solver ``highspy`` is not on the scoring server either:
``sbfv_highspy/`` is highspy's Python wrapper over SciPy's own copy of the same HiGHS release (1.12.0), and
``fastjsonschema.py`` a stand-in for the instance-schema check. ``data/<task>.pkl`` holds what would otherwise be drawn
in week 1 (``outputs/scen_precompute.py``): naive's F_Q quantiles and the scenario library.

The policy reads the scorer's internal observation, which the agent kit flattens; ``wire_observation`` rebuilds the
fields it reads (week, stock, backlog, pipeline, queue lots, WIP, graph_now, demand forecast, pending prohibitions).
The grouped pipeline and the dense queue lots lose only what the LP never reads (a lot's dispatch week and entry edge
follow from its lane). The action goes back through the package's own ``flat_from_action``.

Safety net: if anything of the above fails (the import, ``Agent(config)``, the policy's reset or a week's act), the
episode continues with our energy MPC (``safe/``, the agent behind submission 964550), from that week on.

Time guard: each week's CPU time is measured with ``time.process_time()``. A week whose act took over ``SLOW_SHARE``
of the budget hands the following weeks to ``safe/`` (the slow week plays the action it already computed). Week 1 is
judged without the policy's one-off reset and against the whole budget: its first solve is about twice a usual week
(measured on the cloud machine: Small 1.07 s against a median of 0.52 s), so a slow start alone does not give up the
episode. The budget is ``config["cpu_budget_s"]`` when the config carries it (shockbench-flow-agent 0.1.2's does
not), else the published per-board budget for the instance's kind (Small 2 s, Full 4 s; that package's
``LIMITS.cpu_budget_s``). Week 1's CPU seconds of setup, reset and first act go to stderr.

Unlike ``agents/scen`` (v1..v3) this version raises nothing on purpose: no diagnostic weeks, no instance-match weeks.
"""

import importlib.util
import os
import pickle
import sys
import time
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# CPU seconds per week by instance kind, as published in shockbench_flow_agent.LIMITS.cpu_budget_s
CPU_BUDGET_S = {"tiny": 2.0, "small": 2.0, "full": 4.0}
# a week over this share of the CPU budget hands the episode to the safe agent; the variable lets a slower machine
# than the scorer's test the policy itself (never set on the server)
SLOW_SHARE = float(os.environ.get("SCEN_SLOW_SHARE", "0.75"))

_spec = importlib.util.spec_from_file_location("scen_final_safe_mpc", HERE / "safe" / "agent.py")
_safe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_safe)
SafeAgent = _safe.Agent

try:
    import sbfv_highspy  # noqa: F401 - SciPy's HiGHS behind highspy's API; the policy imports it at its first solve
    from sbfv.disruption.params import generator_id
    from sbfv.information.flat import FlatLayout, flat_from_action
    from sbfv.instance import load_instance
    from sbfv.instance.schema import WAR_RISK_CLASSES
    from sbfv.omega import seeds
    from sbfv.omega.container import immutable_copy
    from sbfv.policies import scenarios as S_
    from sbfv.policies.mpc_scen import MpcScen
    from sbfv.policies.registry import GeneratorRef, PolicyContext

    DATA = {p.stem: pickle.loads(p.read_bytes()) for p in sorted((HERE / "data").glob("*.pkl"))}
    seeds.KERNELS = False  # numba is not on the server: NumPy's reference path, which numba's kernels copy bit for bit
    IMPORT_ERROR = None
except Exception as exc:  # noqa: BLE001 - the safety net plays instead (module docstring)
    IMPORT_ERROR = exc


def cpu_budget(config, kind):
    """CPU seconds per week: the config's own number when it has one, else the board's for this kind (the smallest
    published one for an unknown kind)."""
    try:
        if config.get("cpu_budget_s") is not None:
            return float(config["cpu_budget_s"])
    except Exception:  # noqa: BLE001
        pass
    return CPU_BUDGET_S.get(kind, min(CPU_BUDGET_S.values()))


def _rows(flat, block, fields, key):
    """The listed rows of a padded block (observed where ``key`` is), as {field: list}; None-valued where unobserved."""
    seen = flat[f"{block}.{key}.observed"].astype(bool)
    out = {}
    for f in fields:
        vals, obs = flat[f"{block}.{f}"][seen].tolist(), flat[f"{block}.{f}.observed"][seen].tolist()
        out[f] = [v if o else None for v, o in zip(vals, obs)]
    return out


def _column(flat, key):
    vals, seen = flat[key].tolist(), flat[f"{key}.observed"].tolist()
    return [v if s else None for v, s in zip(vals, seen)]


def _by_node(flat, prefix, nodes, fields):
    out = {"node": list(nodes)}
    for f in fields:
        out[f] = _column(flat, f"{prefix}.{f}")
    return out


def wire_observation(inst, layout: FlatLayout, flat: dict) -> dict:
    """The internal observation fields the policy reads, rebuilt from the flat one (module docstring)."""
    obs = {"week": int(flat["week"][0])}
    seen = flat["stock.qty.observed"].tolist()
    q = flat["stock.qty"].tolist()
    slots = [(n, k, x) for (n, k), x, s in zip(layout.stock_slots, q, seen) if s]
    obs["stock"] = {"node": [n for n, _, _ in slots], "k": [k for _, k, _ in slots], "qty": [x for _, _, x in slots]}
    seen = flat["backlog.qty.observed"].tolist()
    rows = [(n, k, x) for (n, k), x, s in zip(layout.demands, flat["backlog.qty"].tolist(), seen) if s]
    obs["backlog"] = {"node": [n for n, _, _ in rows], "k": [k for _, k, _ in rows], "qty": [x for _, _, x in rows]}
    obs["pipeline"] = _rows(flat, "pipeline", ("edge", "k", "lane", "qty", "arrival_week"), "edge")
    obs["wip"] = _rows(flat, "wip", ("node", "k", "qty", "out_week"), "node")

    lots = {f: [] for f in ("chokepoint", "k", "qty", "lane", "next_edge", "arrival_week", "dispatch_week",
                            "entry_edge")}
    qty, seen = flat["queue_lots.qty"], flat["queue_lots.qty.observed"]
    for i, w in zip(*np.nonzero(seen)):
        c, k, lane, nxt = layout.lot_keys[i]
        entry = inst.lane_through[(lane, c)][0]
        arrival = int(w) + 1
        for f, v in (("chokepoint", c), ("k", k), ("qty", float(qty[i, w])), ("lane", lane), ("next_edge", nxt),
                     ("arrival_week", arrival), ("dispatch_week", arrival - inst.edges[entry].tau),
                     ("entry_edge", entry)):
            lots[f].append(v)
    obs["queue_lots"] = lots

    if not flat["graph_now.open.observed"].any() and not flat["graph_now.tau.observed"].any():
        obs["graph_now"] = None
    else:
        E, K = flat["graph_now.prohibited"].shape
        pe, pk = np.nonzero(flat["graph_now.prohibited"])
        te, tk = np.nonzero(flat["graph_now.tariff"])
        sup_seen = flat["graph_now.supply.avail.observed"].tolist()
        sup = [(n, k, a) for (n, k), a, s in zip(layout.supply_slots, flat["graph_now.supply.avail"].tolist(), sup_seen)
               if s]
        obs["graph_now"] = {
            "u": _column(flat, "graph_now.u"),
            "c": _column(flat, "graph_now.c"),
            "tau": _column(flat, "graph_now.tau"),
            "prohibited": {"edge": pe.tolist(), "k": pk.tolist()},
            "tariff": {"edge": te.tolist(), "k": tk.tolist(), "rate": flat["graph_now.tariff"][te, tk].tolist()},
            "open": _column(flat, "graph_now.open"),
            "kappa": {pool: _column(flat, f"graph_now.kappa.{pool}") for pool in ("tb", "ct")},
            "war_risk": [None if v is None else WAR_RISK_CLASSES[v] for v in _column(flat, "graph_now.war_risk")],
            "supply": {"node": [n for n, _, _ in sup], "k": [k for _, k, _ in sup], "avail": [a for _, _, a in sup]},
            "fab": _by_node(flat, "graph_now.fab", layout.fabs, ("R", "alpha_bar", "cap_eff")),
            "grid": _by_node(flat, "graph_now.grid", layout.grids, ("G_bar", "y_bar")),
            "osat": _by_node(flat, "graph_now.osat", layout.osats, ("R", "thr_eff")),
        }

    fc_seen = flat["demand_forecast.qty.observed"]
    if fc_seen.any():
        d, h = np.nonzero(fc_seen)
        obs["demand_forecast"] = {
            "node": [layout.demands[i][0] for i in d.tolist()],
            "k": [layout.demands[i][1] for i in d.tolist()],
            "h": h.tolist(),
            "qty": flat["demand_forecast.qty"][d, h].tolist(),
        }
    else:
        obs["demand_forecast"] = None
    obs["pending_prohibitions"] = _rows(flat, "pending_prohibitions", ("edge", "k", "effective_week"), "edge")
    return obs


class Agent:
    def __init__(self, config):
        t = time.process_time()
        self.safe = SafeAgent(config)
        self.budget = cpu_budget(config, None)  # the kind is known once _setup loads the instance
        self.t_setup = 0.0  # CPU seconds of Agent(config), safe/'s included (logged in week 1)
        self.week = 0
        self.failed = False
        self.started = False
        self.t_reset = 0.0  # CPU seconds of the policy's reset in this week's act (week 1 only)
        if IMPORT_ERROR is not None:
            self._fail("import", IMPORT_ERROR)
            return
        try:
            self._setup(config)
        except Exception as exc:  # noqa: BLE001
            self._fail("Agent(config)", exc)
        self.t_setup = time.process_time() - t

    def _fail(self, stage, exc):
        print(f"agents/scen_final: {stage} failed, the safe agent plays on: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        self.failed = True

    def act(self, observation):
        self.week += 1
        start = time.process_time()
        if not self.failed:
            try:
                action = self._act(observation)
            except Exception as exc:  # noqa: BLE001
                self._fail("reset" if not self.started else f"week {self.week}", exc)
            else:
                steady = time.process_time() - start - self.t_reset  # week 1 without the policy's one-off reset
                if self.week == 1:
                    print(f"agents/scen_final: CPU s setup {self.t_setup:.2f}, reset {self.t_reset:.2f}, first act "
                          f"{steady:.2f} (budget {self.budget:g})", file=sys.stderr)
                share = max(1.0, SLOW_SHARE) if self.week == 1 else SLOW_SHARE  # week 1: module docstring
                if steady > share * self.budget:
                    print(f"agents/scen_final: week {self.week} took {steady:.2f} of {self.budget:g} CPU s, the safe "
                          "agent plays the following weeks", file=sys.stderr)
                    self.failed = True
                return action  # already computed: playing it costs nothing more, whereas safe/'s would
        return self.safe.act(observation)

    def _setup(self, config):
        self.static = config["static"]
        self.seed = int(config["policy_seed"])
        self.inst = load_instance(self.static["instance"])
        self.budget = cpu_budget(config, self.inst.kind)
        self.layout = FlatLayout.from_static(self.static, inst=self.inst)
        data = DATA[self.inst.kind]
        ctx = PolicyContext(
            fq_quantile=data["quantiles"],
            generator=GeneratorRef(data["kind"], data["gamma"]),
            fq_replications=data["replications"],
        )
        # the scenario library, drawn offline: put into the package's per-process cache under this instance's key.
        # On Codabench the instance in Static is not the one drawn for (submission 965604: a ValueError when this
        # was a hard check), so the draws go in under whatever key it has
        gen = S_.generator_params(self.inst, ctx.generator)
        gid = generator_id(gen, self.inst)
        for d in data["draws"]:
            S_._DRAWS[(self.inst.content_digest, gid, S_.TAG_MPC_SCEN, d["index"])] = S_.ScenarioDraw(
                index=d["index"],
                entropy_sha256=d["entropy_sha256"],
                generator_id=gid,
                events={k: immutable_copy(v) for k, v in d["events"].items()},
            )
        self.policy = MpcScen(context=ctx)
        self.started = False

    def _act(self, observation):
        obs = wire_observation(self.inst, self.layout, observation)
        if not self.started:  # the policy's reset reads the first observation, as the scorer's rollout gives it
            t = time.process_time()
            self.policy.reset(self.static, obs, self.seed)
            self.t_reset = time.process_time() - t
            self.started = True
        else:
            self.t_reset = 0.0
        flows, override_qty, release_mode = flat_from_action(self.layout, self.policy.act(obs))
        return {"flows": flows, "override_qty": override_qty, "release_mode": release_mode}
