"""The organisers' ``mpc_scen`` baseline behind the flat agent interface.

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
episode continues with our energy MPC (``safe/``, the agent behind submission 964550). Diagnosis: the first failure
also makes the next ``CODE`` weeks raise on purpose, so the board's Fallbacks column per episode reads
10 * (stage - 1) + error class (stages and classes below; 52 per episode means the process itself died); stage 2
(``Agent(config)``) is coded by the step of ``_setup`` that failed instead (1 load the instance, 2 the flat layout,
3 the data of its kind, 4 the policy context, 5 the generator, 6 its id, 7 the draws, 8 the policy). Stage 5 is
a week over ``SLOW_SHARE`` of the CPU budget, its class the CPU seconds rounded up (at most 9), plus the slow week
itself when it was over the budget.
"""

import importlib.util
import math
import os
import pickle
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

STAGE_IMPORT, STAGE_INIT, STAGE_RESET, STAGE_ACT, STAGE_SLOW = 1, 2, 3, 4, 5
# a week over this share of the CPU budget hands the episode to the safe agent (stage 5); the variable lets a slower
# machine than the scorer's test the policy itself (never set on the server)
SLOW_SHARE = float(os.environ.get("SCEN_SLOW_SHARE", "0.75"))
ERROR_CLASSES = (ImportError, OSError, MemoryError, RuntimeError, ValueError, KeyError, TypeError, AttributeError)


def error_code(stage, exc):
    """10 * (stage - 1) + the error class (1 .. 8 in ``ERROR_CLASSES`` order, 9 any other)."""
    cls = next((i + 1 for i, c in enumerate(ERROR_CLASSES) if isinstance(exc, c)), 9)
    return 10 * (stage - 1) + cls


def match_code(inst, gid, data):
    """How the scorer's instance relates to the one the data was drawn for: 0 the same generator id, 1 the same content
    under another hash, 2 + i the content of the i-th other rung (data drawn at the anchor, so approximate), 6 none."""
    if all(d["generator_id"] == gid for d in data["draws"]):
        return 0
    if inst.content_digest == data["content_digest"]:
        return 1
    others = [g for g in sorted(data["rung_digests"]) if g != data["gamma"]]
    for i, g in enumerate(others):
        if inst.content_digest == data["rung_digests"][g]:
            return 2 + i
    return 6


_spec = importlib.util.spec_from_file_location("scen_safe_mpc", HERE / "safe" / "agent.py")
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
        self.safe = SafeAgent(config)
        self.budget = 2.0 if int(config["T"]) <= 52 else 4.0  # CPU seconds per week: Small's board, else Full's
        self.week = 0
        self.code = 0  # weeks still to raise on purpose (module docstring)
        self.failed = False
        self.started = False
        self.flag = 0
        self.step = 0  # the last step of _setup begun: a failure there is coded by step, not by error class
        if IMPORT_ERROR is not None:
            self._fail(STAGE_IMPORT, IMPORT_ERROR)
            return
        try:
            self._setup(config)
        except Exception as exc:  # noqa: BLE001
            self._fail(STAGE_INIT, exc)
            self.code = 10 * (STAGE_INIT - 1) + self.step

    def _fail(self, stage, exc):
        print(f"agents/scen: stage {stage} failed, the safe agent plays on: {type(exc).__name__}: {exc}", file=sys.stderr)
        self.failed = True
        self.code = error_code(stage, exc)

    def act(self, observation):
        self.week += 1
        if not self.failed:
            start = time.process_time()
            try:
                action = self._act(observation)
            except Exception as exc:  # noqa: BLE001
                self._fail(STAGE_RESET if not self.started else STAGE_ACT, exc)
            else:
                used = time.process_time() - start
                if used <= SLOW_SHARE * self.budget:
                    if self.flag > 0:  # the instance diagnosis (match_code): the policy played, naive takes the week
                        self.flag -= 1
                        raise RuntimeError(f"agents/scen instance diagnosis: {self.flag + 1} weeks left to flag")
                    return action
                print(f"agents/scen: week {self.week} took {used:.2f} CPU s, the safe agent plays on", file=sys.stderr)
                self.failed = True
                self.code = 10 * (STAGE_SLOW - 1) + min(9, math.ceil(used))
        action = self.safe.act(observation)
        if self.code > 0:
            self.code -= 1
            raise RuntimeError(f"agents/scen diagnosis: {self.code + 1} weeks left to flag")
        return action

    def _setup(self, config):
        self.step = 1
        self.static = config["static"]
        self.seed = int(config["policy_seed"])
        self.inst = load_instance(self.static["instance"])
        self.step = 2
        self.layout = FlatLayout.from_static(self.static, inst=self.inst)
        self.step = 3
        data = DATA[self.inst.kind]
        self.step = 4
        ctx = PolicyContext(
            fq_quantile=data["quantiles"],
            generator=GeneratorRef(data["kind"], data["gamma"]),
            fq_replications=data["replications"],
        )
        # the scenario library, drawn offline: put into the package's per-process cache under this instance's key.
        # On Codabench the instance in Static is not the one drawn for (submission 965604: a ValueError when this
        # was a hard check), so the draws go in under whatever key it has, and MATCH weeks are flagged (below)
        self.step = 5
        gen = S_.generator_params(self.inst, ctx.generator)
        self.step = 6
        gid = generator_id(gen, self.inst)
        self.flag = match_code(self.inst, gid, data)
        self.step = 7
        for d in data["draws"]:
            S_._DRAWS[(self.inst.content_digest, gid, S_.TAG_MPC_SCEN, d["index"])] = S_.ScenarioDraw(
                index=d["index"],
                entropy_sha256=d["entropy_sha256"],
                generator_id=gid,
                events={k: immutable_copy(v) for k, v in d["events"].items()},
            )
        self.step = 8
        self.policy = MpcScen(context=ctx)
        self.started = False

    def _act(self, observation):
        obs = wire_observation(self.inst, self.layout, observation)
        if not self.started:  # the policy's reset reads the first observation, as the scorer's rollout gives it
            self.policy.reset(self.static, obs, self.seed)
            self.started = True
        flows, override_qty, release_mode = flat_from_action(self.layout, self.policy.act(obs))
        return {"flows": flows, "override_qty": override_qty, "release_mode": release_mode}
