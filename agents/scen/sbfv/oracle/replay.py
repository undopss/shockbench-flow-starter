"""The replay test (53): a policy trajectory with its realised auxiliaries is feasible in (51) at equal cost.

|res_r| <= 1e-9 max(1, max_j |a_rj z_j|, |b_r|) for every row; |J_LP(z) - J^pi| <= 1e-9 sum |cost terms|; and the
oracle check J^oracle <= J^pi + 1e-7 max(1, |J^pi|) on J of (23) in USD, as (53) is written, never on the per-week
rounded cents of (24) (ORACLE-PRE3-1). Row evaluation only, no solve (§6.2). Replay runs under the fixed NumPy error
state ``marks.FP_ERRORS``, never the caller's (DET-P3-2).

Mapping from ``StepRecord`` fields of week t to columns of (51) (keys as in ``oracle.lp``):
  x[(e, k, lane)]            -> ("x", t, *lp_flow_key(inst, e, k, lane)): a K^ov release out of a chokepoint ->
                                ("x", t, e, k, None), its lanes summed by ``cost.edge_flows`` into x_ek (tanker
                                queues are aggregated, §6.1), as the simulator's cost sums them (23)
  stock[s]                   -> ("I", t, s) at non-chokepoint slots; ("Q", t, c, k, None) at K^ov chokepoint slots
  queue[(c, k, lane)]        -> ("Q", t, c, k, lane) for commodities without override (52); their sum over lanes
                                (``cost.queue_totals``, the simulator's formation of the stock) must equal stock at
                                (c, k) (pseudo-row ("queue_total", t, c, k)); a valid trajectory leaves no residual
  disposal[s], lift[s]       -> ("O", t, s), ("lift", t, s)
  lots_started[f], energy[f] -> ("p", t, f), ("E", t, f)
  packaged[(o, k)]           -> ("xi", t, o, k)
  segment[(g, k)]            -> ("G", t, g, k)
  served_load[g], shed[g]    -> ("y", t, g), ("ysh", t, g)
  served[d], lost[d], backlog[d] -> ("D", t, d), ("U", t, d), ("B", t, d)
A nonzero quantity with no column (a flow the LP forbids, lost sales at a backlog sink, ...) is a violation named
("no_column", t, tag, *key), measured like a bound at 0. ``scrapped``, the requests and the clip log enter no row.
"""

import math
from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix

from sbfv.dynamics.cost import edge_flows, queue_totals
from sbfv.dynamics.state import Trajectory
from sbfv.marks import fixed_fp_errors
from sbfv.oracle.lp import LPModel, lp_cents, lp_usd


ROW_TOL = 1e-9
COST_TOL = 1e-9
ORACLE_TOL = 1e-7


@dataclass(frozen=True)
class ReplayResult:
    feasible: bool  # every row and bound within ROW_TOL (relative)
    worst_residual: float
    worst_row: tuple
    J_lp_cents: int  # the trajectory's J^¢ computed from the LP's cost vector
    J_sim_cents: int  # the simulator's J^¢
    cost_equal: bool  # |J_LP(z) - J^pi| <= COST_TOL sum |cost terms|


@fixed_fp_errors
def trajectory_vector(model: LPModel, traj: Trajectory) -> np.ndarray:
    """The column vector z^pi of a finished trajectory.

    Executed flows by lane, stocks, lane-indexed queues, disposal, lifts, lots started, OSAT starts, segment outputs,
    energy, served and shed load, served, lost and backlog.
    """
    return _vector(model, traj)[0]


@fixed_fp_errors
def replay(model: LPModel, traj: Trajectory) -> ReplayResult:
    """Run (53) on one trajectory, under the fixed NumPy error state ``marks.FP_ERRORS`` (DET-P3-2).

    Raises:
        ValueError: if the episode is unfinished (no terminal credit, or weeks not 1..T), holds a non-finite
            quantity, or comes from another instance or omega than the LP (V3).

    """
    if traj.salvage is None or traj.salvage_cents is None:
        raise ValueError("episode not finished: the trajectory has no terminal credit")
    if (
        traj.instance_hash != model.instance_hash
        or traj.omega_hash != model.omega_hash
        or traj.instance_digest != model.instance_digest
        or traj.marks_digest != model.marks_digest
    ):
        raise ValueError("the trajectory and the LP were built on different instances, omegas or marks (V3)")
    z, extra = _vector(model, traj)
    checks = [
        _rows(model.A_eq, model.b_eq, z, model.eq_name, equality=True),
        _rows(model.A_ub, model.b_ub, z, model.ub_name, equality=False),
        _bounds(model, z),
    ]
    checks.extend(extra)
    worst, row = max(checks, key=lambda c: c[0])
    J_lp, scale = lp_usd(model, z)
    J_sim = trajectory_usd(traj)
    return ReplayResult(
        feasible=bool(worst <= ROW_TOL),
        worst_residual=float(worst),
        worst_row=row,
        J_lp_cents=lp_cents(model, z),
        J_sim_cents=traj.J_cents,
        cost_equal=bool(abs(J_lp - J_sim) <= COST_TOL * scale),
    )


def trajectory_usd(traj: Trajectory) -> float:
    """J^pi of (23) in USD as the simulator sums it: the fsum of the weeks' C_t minus the credit S_T.

    Each C_t is the record's ``costs.total()``; for the trajectory's z^pi, ``lp_usd`` forms the same float (§12, oracle
    cents).

    Raises:
        ValueError: if the episode is unfinished (no terminal credit).

    """
    if traj.salvage is None:
        raise ValueError("episode not finished: the trajectory has no terminal credit")
    return math.fsum(r.costs.total() for r in traj.records) - traj.salvage


def oracle_bound_holds(J_oracle: float, J_pi: float) -> bool:
    """J^oracle <= J^pi + 1e-7 max(1, |J^pi|) of (53), on J of (23) in USD.

    ``J_oracle`` is the LP optimum's J (``OracleResult.J_usd``) and ``J_pi`` the trajectory's (``trajectory_usd``), as
    (53) is written. Never pass the cents of (24): each week is rounded on its own, so two plans with the same J in USD
    differ by up to T + 1 cents, more than the tolerance whenever |J^¢| < 1e7 (ORACLE-PRE3-1).
    """
    return J_oracle <= J_pi + ORACLE_TOL * max(1.0, abs(J_pi))


def _vector(model: LPModel, traj: Trajectory) -> tuple[np.ndarray, list[tuple[float, tuple]]]:
    """z^pi and the extra checks: quantities without a column and lane-indexed queue totals."""
    weeks = [r.week for r in traj.records]
    if weeks != list(range(1, model.T + 1)):
        raise ValueError(f"trajectory weeks {weeks[:3]}... do not cover 1..{model.T}")
    nc, tmpl = model.meta["nc"], model.meta["template"]
    chk, override = model.meta["chokepoints"], model.meta["override"]
    z = np.zeros(len(model.lb))
    extra: list[tuple[float, tuple]] = []

    def finite(t: int, key: tuple, qty) -> float:
        qty = float(qty)
        if not math.isfinite(qty):
            raise ValueError(f"non-finite quantity {qty} at week {t}, {key}")
        return qty

    def put(t: int, key: tuple, qty: float) -> None:
        qty = finite(t, key, qty)
        j = tmpl.get(key)
        if j is None:
            if qty != 0.0:
                extra.append((abs(qty) / max(1.0, abs(qty)), ("no_column", t, *key)))
            return
        z[(t - 1) * nc + j] = qty

    slots = model.meta["slots"]  # (node, k) per stock slot
    flow_key = model.meta["flow_key"]  # ``lp_flow_key`` where it drops the lane: tanker releases aggregate over lanes
    for rec in traj.records:
        t = rec.week
        pieces: dict[tuple, dict[tuple, float]] = {}  # LP flow -> the simulator's lane flows it carries
        for key, q in rec.x.items():
            pieces.setdefault(flow_key.get(key, key), {})[key] = finite(t, ("x", *key), q)
        for col, lanes in pieces.items():
            try:
                (q,) = edge_flows(lanes).values()  # the lanes of one LP flow share (e, k): x_ek of (23), (52)
            except OverflowError:
                raise ValueError(f"non-finite flow at week {t}, {('x', *col)}: its lanes overflow") from None
            put(t, ("x", *col), q)
        lanes: dict[tuple[int, int, int], float] = {}
        for (c, k, lane), q in rec.queue.items():
            if k in override:
                continue
            put(t, ("Q", c, k, lane), q)
            lanes[(c, k, lane)] = finite(t, ("Q", c, k, lane), q)
        try:
            totals = queue_totals(lanes)  # I_ck of (52) as the simulator forms it: exact for a valid trajectory
        except OverflowError:
            raise ValueError(f"non-finite queue total at week {t}: its lane queues overflow") from None
        for s, (node, k) in enumerate(slots):
            if node in chk:
                if k in override:
                    put(t, ("Q", node, k, None), rec.stock[s])
                else:
                    total = totals.get((node, k), 0.0)
                    res = abs(total - float(rec.stock[s])) / max(1.0, abs(total), abs(float(rec.stock[s])))
                    extra.append((res, ("queue_total", t, node, k)))
            else:
                put(t, ("I", s), rec.stock[s])
            put(t, ("O", s), rec.disposal[s])
            put(t, ("lift", s), rec.lift[s])
        for f in range(len(rec.lots_started)):
            put(t, ("p", f), rec.lots_started[f])
            put(t, ("E", f), rec.energy[f])
        for (o, k), q in rec.packaged.items():
            put(t, ("xi", o, k), q)
        for (g, k), q in rec.segment.items():
            put(t, ("G", g, k), q)
        for g in range(len(rec.served_load)):
            put(t, ("y", g), rec.served_load[g])
            put(t, ("ysh", g), rec.shed[g])
        for d in range(len(rec.served)):
            put(t, ("D", d), rec.served[d])
            put(t, ("U", d), rec.lost[d])
            put(t, ("B", d), rec.backlog[d])
    return z, extra


def _rows(A: csr_matrix, b: np.ndarray, z: np.ndarray, name, equality: bool) -> tuple[float, tuple]:
    """Worst relative residual of A z (=|<=) b, with the scale max(1, max_j |a_rj z_j|, |b_r|) of (53)."""
    if A.shape[0] == 0:
        return 0.0, ()
    res = A @ z - b
    prod = np.abs(A.data * z[A.indices])
    maxterm = np.zeros(A.shape[0])
    nonempty = np.diff(A.indptr) > 0
    if prod.size:
        maxterm[nonempty] = np.maximum.reduceat(prod, A.indptr[:-1][nonempty])
    scale = np.maximum(1.0, np.maximum(maxterm, np.abs(b)))
    viol = (np.abs(res) if equality else np.maximum(res, 0.0)) / scale
    i = int(np.argmax(viol))
    return float(viol[i]), name(i)


def _bounds(model: LPModel, z: np.ndarray) -> tuple[float, tuple]:
    """Worst bound violation, relative to max(1, |z_j|) as in the reference code."""
    over = np.where(np.isinf(model.ub), -np.inf, z - model.ub)
    viol = np.maximum(model.lb - z, over) / np.maximum(1.0, np.abs(z))
    i = int(np.argmax(viol))
    return float(viol[i]), ("bound", *model.key(i))
