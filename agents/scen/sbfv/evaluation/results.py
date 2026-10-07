"""The runner's frozen results and tables (milestone M4, stream "runner").

The §6.3 reference row, per-policy runs, RSS (55)-(56), the decomposition (57) and the separation report (design §6.3,
§7.1-7.3, §2.6 "Separation"; Q55, Q62, Q82).

Readings (design §12 M4 rows "Runner" and "Separation report", and the rows under the bold head row "M4 stream
runner"):

- every quantity scored is integer cents (24); RSS by ``scoring.rss`` in exact Fractions; D_n = J^naive - J^oracle can
  be slightly negative (down to about -27 cents on `tiny`, per-week rounding) and stays in the pooled sums; negatives
  are never clipped; every pooled display divides by D-bar = sum_s p_s D-bar_s (§7.6);
- an episode whose sealed LP is not optimal (the oracle on omega or on omega^0) is excluded for every policy and
  counted by cause (``EXCLUSION_CAUSES``, ``exclusion_cause``), never zero-filled (§6.3), so pairing is kept; a stratum
  emptied by exclusions makes that policy's RSS_G undefined with its reason, never a crash in the middle of a run;
- **one RSS rule** (M4 re-gate ORACLE-M4R-02 = INT-M4R2-05 = SIMP-M4R2-02): ``episode_rss`` computes (55) per stratum
  and (56) pooled from per-episode records for every scorer: this module's ``rss_table`` (M4's runner), the trusted
  scorer and the board (``hosting.trusted.rss_table``) and the kit's ``scripts/python/eval_submission.py``, so a
  participant's local score is the official one on the same episodes (design §12 "One RSS rule");
- a V5 failure (replay (53) infeasible or cost-unequal, or the oracle bound) of the anchor is a bug: the run records it
  and its entry point exits 1; a reference baseline's crash or V5 failure nulls that policy's RSS with its reason,
  never substituted or zero-filled;
- the references of one episode (the anchor on omega and omega^0, ``nd`` on omega^0) are ``PolicyRun`` objects under
  the labels ``ANCHOR``, ``ANCHOR0`` and ``ND0``, replayed (53) in their own LP with their own oracle's bound; ``nd``
  crashing on omega^0 (or not built) leaves ``J_nd0_cents`` None and the (57) shares undefined with the reason, while
  D and every RSS stay defined; ``nd`` failing V5 on omega^0 in a kept episode leaves the shares undefined with the
  reason in the same way (the row keeps ``J_nd0_cents``: the failure is listed, nothing substituted), and so does an
  anchor V5 failure;
- episodes without strata (plain range mode, injected lists) form one stratum of weight 1, so (55) over all of them
  is reported and (56) is not claimed ("stratified": False);
- a rung is one generator (the rows' ``generator_id``); every run and reference carries its rung
  (``PolicyRun.generator_id``), so a result joined over rungs, which repeats episode indices on the difficulty ladder
  (§7.4, Q88), is split by (rung, episode) (``split_rungs``), never by index alone, and input a run could be placed
  from only by guessing is refused; ``rss_table`` is one rung's table and the separation report one block per rung;
- the separation report on `tiny` covers every baseline under prediction_free and standard per rung, with (58) and the
  one-sided (61) for the §2.6 adjacent pairs (``SEPARATION_PAIRS``), in the declared direction and in the other (a
  significant reversal is a failure, §2.6), and the §7.3 skew diagnostics beside each; `tiny`
  is a correctness fixture (Q82): its RSS is reported, not claimed, and ``hindsight_consensus`` is labelled "not
  budget-compliant"; a baseline whose every run raised a stub's ``NotImplementedError("M4 stream <name>")`` is
  labelled "not built"; eta_n is deferred to M6.

M5 (stream "ladders"; design §2.6, §7.3-7.4; §12 rows under "M5 stream ladders"): the fixture note is `tiny`'s only
(``fixture_note``, read from ``setup["instance_kind"]``; a result that does not record its kind keeps the note, the
M4 behaviour), and the ladder reports: the difficulty ladder's delta_r per rung with (64)'s tests and family F-knob
(``ladder_report``), the size ladder's unpaired tests on (73) and (64), reported and never gated
(``size_ladder_report``; the owner's answer of 2026-09-29), family F-size from each gated size's
pair tests (``pair_test``, ``f_size_report``), the per-rung pooled RSS (``per_rung_rss``, reported, never gated) and
the transfer check (``transfer_report``, no threshold).
"""

import dataclasses
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction

from sbfv.dynamics.env import took_fallback
from sbfv.dynamics.state import Trajectory
from sbfv.evaluation import ladders
from sbfv.evaluation.timings import StepTimings
from sbfv.oracle.replay import oracle_bound_holds, replay, trajectory_usd
from sbfv.policies.registry import BASELINES, NOT_BUDGET_COMPLIANT
from sbfv.scoring import inference
from sbfv.scoring.rss import STRATUM_WEIGHTS, rss_pooled, rss_stratum


EXCLUSION_CAUSES = ("oracle_not_optimal", "oracle0_not_optimal")  # a sealed LP of (57) with no optimal point (§6.3)
# the §2.6 adjacent pairs (better, worse): one-sided (61) with d_n = J^worse_n - J^better_n, H1: T > 0
SEPARATION_PAIRS = (("mpc_scen", "mpc_det"), ("mpc_det", "greedy_lp"))
REPORT_REGIMES = ("prediction_free", "standard")  # the anchor's regime and the proposed ranked one (Q13)
ANCHOR_REGIME = "prediction_free"  # the anchor of (55) plays prediction-free whatever the policies play (Q10)
ANCHOR, ANCHOR0, ND0 = "anchor", "anchor[omega0]", "nd[omega0]"  # the references' run labels (module docstring)
ANCHOR_LABELS = (ANCHOR, ANCHOR0)  # a V5 failure under either makes ``EvalResult.anchor_failed`` true
NOT_BUILT = "NotImplementedError: M4 stream "  # the failure text of a stub (every M4 stub raises it, naming its owner)
FIXTURE_NOTE = "tiny is a correctness fixture (Q82): its RSS and separation are reported, not claimed"
ANCHOR_FAILED = "the anchor failed V5 (a bug, §6.2): no RSS is defined"  # ``rss_reason``'s first rule
FIXTURE_KINDS = ("tiny",)  # the instance kinds whose reports carry ``FIXTURE_NOTE`` (Q82)


def fixture_note(kind: str | None) -> str | None:
    """``FIXTURE_NOTE`` for `tiny` (and for a result that does not record its kind), None for `small` and `full`."""
    return FIXTURE_NOTE if kind is None or kind in FIXTURE_KINDS else None


@dataclass(frozen=True)
class ReplayChecks:
    """V5 for one trajectory: replay (53) and the oracle bound (None unless the oracle is optimal; §6.3)."""

    feasible: bool
    worst_residual: float
    worst_row: tuple[str, ...]
    cost_equal: bool
    cents_equal: bool  # J_LP^¢(z^pi) == J^pi¢ (§12 "Oracle cents and replay scope")
    oracle_bound_holds: bool | None  # J^oracle <= J^pi + 1e-7 max(1, |J^pi|) in USD, (53)

    @property
    def failures(self) -> tuple[str, ...]:
        """The checks that failed; a bound not checked (oracle not optimal) is not a failure."""
        out = []
        if not self.feasible:
            out.append(f"replay (53) infeasible, worst row {list(self.worst_row)} at {self.worst_residual:.3g}")
        if not self.cost_equal:
            out.append("replay (53) cost not equal to the simulator's J")
        if not self.cents_equal:
            out.append("J_LP in cents (24) not equal to the trajectory's J^¢")
        if self.oracle_bound_holds is False:
            out.append("oracle bound J^oracle <= J^pi + 1e-7 max(1, |J^pi|) fails (J in USD, (53))")
        return tuple(out)


@dataclass(frozen=True)
class ReferenceRow:
    """The per-episode row §6.3 seals in M6, in integer cents (24): oracle and naive on omega, and the (57) references.

    ``excluded`` names an ``EXCLUSION_CAUSES`` entry, or None. ``oracle_solver`` and ``oracle0_solver`` are the linprog
    methods whose results the row keeps (``oracle.lp.OracleResult.solver``: highs-ds where §6.3's fallback re-solved a
    status-4 highs-ipm; beside the status, an exclusion's cause). The decomposition properties are exact integer
    identities: D == D_dem + D_ins + D_dmg. ``J_nd0_cents`` is None when ``nd`` did not finish on omega^0 (a crash, or
    not built): then ``D_dem`` and ``D_ins`` raise and the (57) shares are undefined, never zero-filled.
    """

    episode: int
    stratum: int | None  # 1-based harm stratum (44); None in plain range mode
    harm: float | None
    omega_hash: str
    generator_id: str
    oracle_status: int
    oracle_method: str
    oracle_solver: str  # the method whose result is kept: highs-ds where the fallback re-solved (§6.3)
    oracle_seconds: float  # outside every hash
    J_oracle_cents: int | None
    J_oracle_usd: float | None
    J_naive_cents: int
    naive_sha256: str
    naive_invalid: int
    naive_d9: int
    oracle0_status: int
    oracle0_solver: str
    J_oracle0_cents: int | None
    J_naive0_cents: int
    J_nd0_cents: int | None
    excluded: str | None = None

    def _need(self, *names: str) -> None:
        missing = [n for n in names if getattr(self, n) is None]
        if missing:
            raise ValueError(f"episode {self.episode}: {missing} undefined (excluded: {self.excluded}); never 0-filled")

    @property
    def D(self) -> int:
        """D_n = J^naive - J^oracle (55)."""
        self._need("J_oracle_cents")
        return self.J_naive_cents - self.J_oracle_cents

    @property
    def D_dem(self) -> int:
        """J^nd(omega^0) - J^oracle(omega^0) (57)."""
        self._need("J_nd0_cents", "J_oracle0_cents")
        return self.J_nd0_cents - self.J_oracle0_cents

    @property
    def D_ins(self) -> int:
        """J^naive(omega^0) - J^nd(omega^0) (57)."""
        self._need("J_nd0_cents")
        return self.J_naive0_cents - self.J_nd0_cents

    @property
    def D_dmg(self) -> int:
        """[J^naive(omega) - J^naive(omega^0)] - [J^oracle(omega) - J^oracle(omega^0)] (57)."""
        self._need("J_oracle_cents", "J_oracle0_cents")
        return (self.J_naive_cents - self.J_naive0_cents) - (self.J_oracle_cents - self.J_oracle0_cents)


@dataclass(frozen=True)
class PolicyRun:
    """One policy on one episode under one regime: J, its V5 checks, §9.3 counts, telemetry sums and timings.

    ``generator_id`` is the run's rung (its generator, a rung of a §2.6 ladder; not the LP status ladder of
    ``ladder_rungs``): the ``generator_id`` of its episode's ``ReferenceRow`` (omega's), which ``evaluate`` fills on
    every run and reference, the omega^0 references included. A result joined over rungs repeats episode indices (§7.4,
    Q88), so a run is placed by (rung, episode), never by its index alone (``split_rungs``). None on a hand-built run,
    which is then placed by its index where that is unambiguous.
    """

    policy: str
    regime: str
    episode: int
    J_cents: int | None  # None when the run failed (``failed``)
    J_usd: float | None
    trajectory_sha256: str | None
    checks: ReplayChecks | None
    invalid_entries: int
    d9_substitutions: int
    failed: str | None  # the exception or Trajectory.failed of a crashed run; never substituted
    cents_per_week: tuple[int, ...]  # C^¢_t, t = 1..T
    salvage_cents: int | None  # S^¢_T
    internal_fallback_weeks: int = 0  # weeks an LP baseline played naive after every rung failed (StepTelemetry)
    scenarios_failed: int = 0
    ladder_rungs: Mapping[str, int] = field(default_factory=dict)  # rung -> attempts that ended on it
    timings: StepTimings | None = None  # outside every hash
    generator_id: str | None = None  # the run's rung: its episode row's generator_id (class docstring)


@dataclass(frozen=True)
class EvalResult:
    """A whole evaluation: rows, runs, exclusions, V5 failures, machine record, command and (asked) V24 records.

    ``records`` is filled only by ``evaluate(store_actions=True)`` (``runner.run_episode_task``); ``references`` holds
    each episode's reference runs (``ANCHOR``, ``ANCHOR0``, ``ND0``), in episode order; ``setup`` names the split, the
    generator and its ``generator_id``, the cut points and their draws, N_s, the policies and regimes and E_split's
    SHA-256 (never E_split).
    """

    rows: tuple[ReferenceRow, ...]
    runs: tuple[PolicyRun, ...]
    exclusions: Mapping[str, int]
    v5_failures: tuple[str, ...]  # "<policy> <regime> ep<n>: <failure>", anchor failures first
    machine: Mapping[str, object]
    command: str
    records: tuple = ()  # (policy, regime, episode, ConformanceRecord), in run order; () unless store_actions
    references: tuple[PolicyRun, ...] = ()
    setup: Mapping[str, object] = field(default_factory=dict)

    @property
    def anchor_failed(self) -> bool:
        """Whether the anchor failed V5 on any episode (the entry point then exits 1)."""
        return any(f.split(" ", 1)[0] in ANCHOR_LABELS for f in self.v5_failures)


def oracle_optimal(result) -> bool:
    """Whether an oracle solve (``oracle.lp.OracleResult``) has an optimal point and its cents (§6.3)."""
    return result.status == 0 and result.J_cents is not None


def exclusion_cause(oracle, oracle0) -> str | None:
    """The §6.3 exclusion of an episode from its sealed oracle solves on omega and on omega^0, or None.

    ``EXCLUSION_CAUSES[0]`` when the solve on omega is not optimal, else ``EXCLUSION_CAUSES[1]`` when the one on
    omega^0 is not (the (57) references are sealed with the row, §6.3), else None: the one rule of M4's runner, the
    trusted scorer and the kit's local evaluation (module docstring, 'one RSS rule').
    """
    if not oracle_optimal(oracle):
        return EXCLUSION_CAUSES[0]
    if not oracle_optimal(oracle0):
        return EXCLUSION_CAUSES[1]
    return None


def episode_rss(episodes: Sequence[Mapping], weights: Sequence[float] = STRATUM_WEIGHTS, *, reason: str | None = None):
    """RSS (55) per stratum and (56) pooled of per-episode records: every scorer's rule (module docstring).

    Each record carries ``stratum`` (1..len(``weights``)), ``excluded`` (None or an ``EXCLUSION_CAUSES`` entry) and,
    where it is kept, the integer cents ``J_policy_cents``, ``J_naive_cents`` and ``J_oracle_cents``. An excluded
    episode is dropped (§6.3); every kept one enters numerator and denominator whatever the sign of its D_n (§7.1,
    never clipped). RSS_s is None where the stratum has no kept episode or its sum of D_n is not positive, RSS_G None
    where a weighted stratum is empty or the denominator is not positive, each with its reason; ``reason`` (a check
    that failed, ``rss_reason``) makes every value None with it. Records keep their order, so the exact Fractions of
    ``scoring.rss`` see the same sums whoever calls.

    Returns:
        ``{"pooled", "pooled_reason", "strata": {"<s>": {"n", "rss", "reason"}}, "weights"}``, n the kept episodes.

    Raises:
        ValueError: on an ``excluded`` value outside None and ``EXCLUSION_CAUSES``.

    """
    unknown = sorted({str(e["excluded"]) for e in episodes if e["excluded"] not in (None, *EXCLUSION_CAUSES)})
    if unknown:
        raise ValueError(f"unknown exclusion causes {unknown}: one of {EXCLUSION_CAUSES} or None (§6.3)")
    kept = [e for e in episodes if e["excluded"] is None]
    strata = {}
    for s in range(1, len(weights) + 1):
        es = [e for e in kept if e["stratum"] == s]
        rss, why = None, reason
        if why is None and not es:
            why = "no kept episode (§6.3 exclusions) in this stratum"
        elif why is None:
            try:
                rss = rss_stratum(*_cents(es))
            except ValueError as err:
                why = str(err)
        strata[str(s)] = {"n": len(es), "rss": rss, "reason": why}
    pooled, why = None, reason
    if why is None:
        try:
            pooled = rss_pooled(*_cents(kept), [e["stratum"] for e in kept], weights)
        except ValueError as err:
            why = str(err)
    return {"pooled": pooled, "pooled_reason": why, "strata": strata, "weights": list(weights)}


def _cents(episodes: Sequence[Mapping]) -> tuple[list, list, list]:
    """(J^pi, J^naive, J^oracle) of the records, in order."""
    keys = ("J_policy_cents", "J_naive_cents", "J_oracle_cents")
    return tuple([e[k] for e in episodes] for k in keys)


def replay_checks(model, traj: Trajectory, J_oracle_usd: float | None, optimal: bool) -> ReplayChecks:
    """Replay (53) of ``traj`` in ``model`` and the oracle bound in USD (never on cents; §12 "Oracle cents").

    The package home of ``run_episode``'s ``_checks``; ``run_episode`` keeps its own until its pins are shown to hold
    through this one.
    """
    rep = replay(model, traj)
    bound = oracle_bound_holds(J_oracle_usd, trajectory_usd(traj)) if optimal else None  # never zero-filled (§6.3)
    return ReplayChecks(
        feasible=rep.feasible,
        worst_residual=rep.worst_residual,
        worst_row=tuple(str(x) for x in rep.worst_row),
        cost_equal=rep.cost_equal,
        cents_equal=rep.J_lp_cents == traj.J_cents,
        oracle_bound_holds=bound,
    )


def substitution_counts(traj: Trajectory) -> tuple[int, int]:
    """(invalid entries, D9 substitutions) of §9.3, as ``run_episode._counts`` (``dynamics.env.took_fallback``).

    A week whose first ``invalid`` line is a whole-week failure counts one substitution, and its other lines (the
    fallback's own) are not the policy's entries; every line of any other week is one entry the policy sent invalid.
    """
    d9 = [took_fallback(r) for r in traj.records]
    invalid = sum(len(r.invalid) for r, sub in zip(traj.records, d9, strict=True) if not sub)
    return invalid, sum(d9)


def run_failures(run: PolicyRun) -> tuple[str, ...]:
    """The V5 failures of one run, as ``EvalResult.v5_failures`` lines ("<policy> <regime> ep<n>: <failure>")."""
    if run.checks is None:
        return ()
    return tuple(f"{run.policy} {run.regime} ep{run.episode}: {f}" for f in run.checks.failures)


# ----- tables ---------------------------------------------------------------------------------------------------------
def base_name(policy: str) -> str:
    """The baseline a run name belongs to: ``mpc_det[H=L+4]`` -> ``mpc_det`` (registry names are unchanged)."""
    return policy.split("[", 1)[0]


def policy_order(policy: str) -> tuple:
    """Report order: ``registry.BASELINES`` order by base name, the canonical name before its variants, then others."""
    base = base_name(policy)
    rank = BASELINES.index(base) if base in BASELINES else len(BASELINES)
    return rank, base, policy != base, policy


def label(policy: str) -> str | None:
    """The label "not budget-compliant" of ``registry.NOT_BUDGET_COMPLIANT`` and their variants, else None (§8.2)."""
    return "not budget-compliant" if base_name(policy) in NOT_BUDGET_COMPLIANT else None


def _strata(rows: Sequence[ReferenceRow], weights: Sequence[float]) -> tuple[dict[int, int], tuple[float, ...], bool]:
    """Episode -> stratum label, the weights and whether the rows are stratified (module docstring).

    Raises:
        ValueError: if some rows carry a stratum and others do not.

    """
    kinds = {r.stratum is None for r in rows}
    if len(kinds) > 1:
        raise ValueError("rows mix stratified and unstratified episodes")
    if kinds == {True}:
        return {r.episode: 1 for r in rows}, (1.0,), False
    return {r.episode: int(r.stratum) for r in rows}, tuple(weights), True


def _float(x: Fraction | float | None) -> float | None:
    """A finite float, or None (JSON has no NaN or infinity)."""
    if x is None:
        return None
    v = float(x)
    return v if math.isfinite(v) else None


def _shares(
    rows: Sequence[ReferenceRow], label_of: Mapping[int, int], weights, result: EvalResult
) -> tuple[dict | None, str | None]:
    """The (57) shares per stratum and pooled over D-bar, or None with the reason (module docstring).

    Undefined when the anchor failed V5, when ``nd`` did not finish on omega^0, or when its ``ND0`` reference failed V5
    on a kept episode (``rows`` are the kept ones): a figure never rests on a trajectory the replay (53) rejected.
    """
    if result.anchor_failed:
        return None, "the anchor failed V5 (a bug, §6.2): the (57) decomposition is undefined"
    missing = [r.episode for r in rows if r.J_nd0_cents is None]
    if missing:
        return None, f"nd did not finish on omega^0 in episodes {missing}: the (57) decomposition is undefined"
    kept = {r.episode for r in rows}
    failed = sorted(
        {ref.episode for ref in result.references if ref.policy == ND0 and ref.episode in kept and run_failures(ref)}
    )
    if failed:
        return None, f"nd[omega0] failed V5 in episodes {failed}: the (57) decomposition is undefined"
    parts = ("demand", "insurance", "damage")
    per, pooled_num, pooled_den = {}, dict.fromkeys(parts, Fraction(0)), Fraction(0)
    p = [Fraction(str(w)) for w in weights]
    for s in range(1, len(p) + 1):
        group = [r for r in rows if label_of[r.episode] == s]
        if not group:
            per[s] = None
            continue
        sums = {"demand": sum(r.D_dem for r in group), "insurance": sum(r.D_ins for r in group)}
        sums["damage"] = sum(r.D_dmg for r in group)
        D = sum(r.D for r in group)
        per[s] = {k: _float(Fraction(v, D)) if D else None for k, v in sums.items()}
        per[s]["disruption"] = _float(Fraction(sums["insurance"] + sums["damage"], D)) if D else None
        for k in parts:
            pooled_num[k] += p[s - 1] * Fraction(sums[k], len(group))
        pooled_den += p[s - 1] * Fraction(D, len(group))
    empty = any(per[s] is None and p[s - 1] > 0 for s in per)  # pooled over D-bar needs every weighted stratum
    ok = pooled_den and not empty
    pooled = {k: _float(v / pooled_den) if ok else None for k, v in pooled_num.items()}
    pooled["disruption"] = _float((pooled_num["insurance"] + pooled_num["damage"]) / pooled_den) if ok else None
    return {"per_stratum": per, "pooled": pooled}, None


def _runs_by_policy(runs: Sequence[PolicyRun]) -> dict[tuple[str, str], dict[int, PolicyRun]]:
    """(policy, regime) -> episode -> run, of one rung's runs (``split_rungs`` refuses two runs with one key)."""
    out: dict[tuple[str, str], dict[int, PolicyRun]] = {}
    for run in runs:
        out.setdefault((run.policy, run.regime), {})[run.episode] = run
    return dict(sorted(out.items(), key=lambda kv: (policy_order(kv[0][0]), kv[0][1])))


def _refused(what: str) -> ValueError:
    return ValueError(f"{what}: refused, never guessed (a run is placed by its (rung, episode); ORACLE-M4R-01)")


def split_rungs(result: EvalResult) -> tuple[tuple[str, EvalResult], ...]:
    """The result per rung, in the rows' order of first appearance: (generator_id, that rung's part of the result).

    A rung is one generator (``ReferenceRow.generator_id``: one ``evaluate`` is one rung). The difficulty ladder
    evaluates every rung on the same keys (§7.4, Q88), so a result joined over rungs repeats episode indices, and a run
    or reference is placed by (rung, episode), never by its index alone: its rung is its ``PolicyRun.generator_id``, or,
    for a run without one (hand-built), the rung of the one row with its index. A part keeps its rung's rows, runs,
    references and V24 records in their order (a record by the row whose episode and omega it replays), exclusions
    counted from its rows, and the V5 lines of its runs and references: a line goes to the rung whose runs fail with
    it, and a line no run fails with to the one rung whose rows carry its episode. A joined result carries one
    ``setup`` and one ``command`` (its first part's): a part keeps them when the setup names its generator
    (``setup["generator_id"]``) or names none, and any other part has none ({} and ""), never another rung's. A result
    of one rung comes back whole, every line kept. ``rss_table`` is one rung's table and ``separation_report`` gives one
    block per part.

    Raises:
        ValueError: on input a run could be placed from only by guessing: two rows with one (generator_id, episode); a
            run or reference without a generator_id whose index rows of two rungs carry; a run or reference whose
            episode no row of its rung carries; two runs of one (policy, regime), or two references of one label, on
            one (rung, episode); on two rungs, a V5 line several rungs' runs fail with but not once per failing run,
            one no run fails with whose episode no row or the rows of two rungs carry, or a V24 record whose episode
            and omega no row carries.

    """
    rows: dict[str, list[ReferenceRow]] = {}
    rungs_of: dict[int, list[str]] = {}
    keys: set[tuple[str, int]] = set()
    for r in result.rows:
        if (r.generator_id, r.episode) in keys:
            raise _refused(f"two rows of rung {r.generator_id[:12]}... carry episode {r.episode}")
        keys.add((r.generator_id, r.episode))
        rows.setdefault(r.generator_id, []).append(r)
        rungs_of.setdefault(r.episode, []).append(r.generator_id)

    def place(runs: Sequence[PolicyRun], what: str) -> dict[str, list[PolicyRun]]:
        out: dict[str, list[PolicyRun]] = {g: [] for g in rows}
        seen = set()
        for x in runs:
            name = f"{what} {x.policy} {x.regime} ep{x.episode}"
            gid = x.generator_id
            if gid is None:
                owners = rungs_of.get(x.episode, [])
                if len(owners) > 1:
                    raise _refused(f"{name} carries no generator_id and rows of {len(owners)} rungs carry its episode")
                gid = owners[0] if owners else None
            if (gid, x.episode) not in keys:
                raise _refused(f"{name}: no row of its rung ({str(gid)[:12]}...) carries its episode")
            if (key := (x.policy, x.regime, gid, x.episode)) in seen:
                raise _refused(f"two {what}s {x.policy} {x.regime} ep{x.episode} on rung {gid[:12]}...")
            seen.add(key)
            out[gid].append(x)
        return out

    runs, refs = place(result.runs, "run"), place(result.references, "reference")
    if len(rows) <= 1:
        return tuple((gid, result) for gid in rows)
    records: dict[str, list] = {g: [] for g in rows}
    by_omega = {(r.episode, r.omega_hash): r.generator_id for r in result.rows}
    for rec in result.records:  # (policy, regime, episode, ConformanceRecord): placed by the omega it replays
        if (gid := by_omega.get((rec[2], rec[3].omega_hash))) is None:
            raise _refused(f"V24 record {rec[0]} {rec[1]} ep{rec[2]}: no row carries its omega")
        records[gid].append(rec)
    fails = {g: Counter(f for x in (*refs[g], *runs[g]) for f in run_failures(x)) for g in rows}
    owners: dict[str, list[str]] = {}
    for line, count in Counter(result.v5_failures).items():
        by = [g for g in rows if fails[g][line]]
        if len(by) == 1:
            owners[line] = by * count
        elif by and count == sum(fails[g][line] for g in by):
            owners[line] = [g for g in by for _ in range(fails[g][line])]
        elif by:
            raise _refused(f"V5 line {line!r}: the runs of {len(by)} rungs fail with it, not once per failing run")
        elif len(eps := rungs_of.get(_episode_of(line), [])) == 1:
            owners[line] = eps * count
        else:
            raise _refused(f"V5 line {line!r} of no run names an episode the rows of {len(eps)} rungs carry")
    lines: dict[str, list[str]] = {g: [] for g in rows}
    for line in result.v5_failures:
        lines[owners[line].pop(0)].append(line)
    named = result.setup.get("generator_id")  # the rung the setup and command describe (None: no generator named)
    return tuple(
        (
            gid,
            dataclasses.replace(
                result,
                rows=tuple(rows[gid]),
                runs=tuple(runs[gid]),
                references=tuple(refs[gid]),
                v5_failures=tuple(lines[gid]),
                exclusions={c: sum(r.excluded == c for r in rows[gid]) for c in EXCLUSION_CAUSES},
                records=tuple(records[gid]),
                setup=result.setup if named in (None, gid) else {},
                command=result.command if named in (None, gid) else "",
            ),
        )
        for gid in rows
    )


def v5_problem(episode: int, failures: Sequence[str]) -> str:
    """One ``_problems`` line: the run on ``episode`` failed V5 with ``failures`` (``ReplayChecks.failures``)."""
    return f"ep{episode}: V5 failed ({'; '.join(failures)})"


def rss_reason(anchor_failed: bool, problems: Sequence[str]) -> str | None:
    """Why a policy has no RSS (55)-(56), or None: the anchor failed V5 on any episode, else its unscorable runs.

    The rule of ``rss_table`` (design §12 "References and exclusions (M4 runner)", "Failed runs (M4 runner)"), which
    the trusted scorer applies too (``hosting.trusted.rss_table``): a failing episode nulls the RSS with its reason and
    is never dropped on its own, which would score the policy on the episodes it chose.
    """
    if anchor_failed:
        return ANCHOR_FAILED
    return "; ".join(problems) if problems else None


def _problems(by_ep: Mapping[int, PolicyRun], episodes: Sequence[int]) -> list[str]:
    """Why a policy's runs cannot be scored on these episodes: missing, failed or V5-failing runs (none substituted)."""
    out = []
    for n in episodes:
        run = by_ep.get(n)
        if run is None:
            out.append(f"ep{n}: no run")
        elif run.failed is not None:
            out.append(f"ep{n}: failed ({run.failed})")
        elif run.checks is not None and run.checks.failures:
            out.append(v5_problem(n, run.checks.failures))
    return out


def rss_table(result: EvalResult, weights: Sequence[float] = STRATUM_WEIGHTS) -> list[dict]:
    """Per (policy, regime): RSS_s (55) per stratum, RSS_G (56), N_s, exclusions, the (57) shares per stratum.

    Excluded episodes are dropped for every policy (pairing kept); an undefined RSS_G carries its reason; the
    disruption share (D_ins + D_dmg) / D accompanies every RSS_G (§7.2). Rows in ``policy_order``, then regime. RSS_s
    and RSS_G are ``episode_rss`` of the policy's records (the one rule, module docstring).

    One rung's table: the runs are placed by (rung, episode) (``split_rungs``, whose refusals apply), and a result of
    two rungs is refused, since an RSS pooled over rungs is no quantity of the design (along a ladder RSS is reported
    per rung, §2.6); ``separation_report`` gives one table per rung.

    Raises:
        ValueError: on rows of more than one ``generator_id``, and as ``split_rungs``.

    """
    parts = split_rungs(result)
    if len(parts) > 1:
        gids = [f"{gid[:12]}..." for gid, _ in parts]
        raise ValueError(f"rss_table is one rung's table, the result holds {len(parts)} rungs {gids}: split_rungs")
    label_of, w, stratified = _strata(result.rows, weights)
    kept = [r for r in result.rows if r.excluded is None]
    episodes = [r.episode for r in kept]
    n_s = [sum(label_of[n] == s for n in episodes) for s in range(1, len(w) + 1)]
    shares, share_reason = _shares(kept, label_of, w, result)
    table = []
    for (policy, regime), by_ep in _runs_by_policy(result.runs).items():
        problems = _problems(by_ep, episodes)
        row = {
            "policy": policy,
            "regime": regime,
            "label": label(policy),
            "built": not (by_ep and all((r.failed or "").startswith(NOT_BUILT) for r in by_ep.values())),
            "stratified": stratified,
            "episodes": len(episodes),
            "N_s": n_s,
            "excluded": dict(result.exclusions),
            "rss_s": [None] * len(w),
            "rss_G": None,
            "rss_G_reason": rss_reason(result.anchor_failed, problems),
            "failed_runs": sum(r.failed is not None for r in by_ep.values()),
            "v5_failures": sum(bool(r.checks and r.checks.failures) for r in by_ep.values()),
            "invalid_entries": sum(r.invalid_entries for r in by_ep.values()),
            "d9_substitutions": sum(r.d9_substitutions for r in by_ep.values()),
            "internal_fallback_weeks": sum(r.internal_fallback_weeks for r in by_ep.values()),
            "scenarios_failed": sum(r.scenarios_failed for r in by_ep.values()),
            "shares": shares,
            "disruption_share": None if shares is None else shares["pooled"]["disruption"],
            "shares_reason": share_reason,
        }
        if row["rss_G_reason"] is None:  # every kept episode has a scorable run (``_problems``)
            records = [
                {
                    "stratum": label_of[r.episode],
                    "excluded": None,
                    "J_policy_cents": by_ep[r.episode].J_cents,
                    "J_naive_cents": r.J_naive_cents,
                    "J_oracle_cents": r.J_oracle_cents,
                }
                for r in kept
            ]
            scored = episode_rss(records, w)
            row["rss_s"] = [scored["strata"][str(s)]["rss"] for s in range(1, len(w) + 1)]
            row["rss_G"], row["rss_G_reason"] = scored["pooled"], scored["pooled_reason"]
        table.append(row)
    return table


def _pair(result: EvalResult, better: str, worse: str, regime: str, weights, B: int, entropy: int) -> dict:
    """(58) and both one-sided (61) of one §2.6 pair under one regime, with the §7.3 diagnostics (or the reason).

    ``p`` tests the declared direction ("greater": ``better`` is the better one) and ``p_reversal`` the other ("less",
    on the same flips), since §2.6 counts a significant reversal as a failure (SPEC-M4R2-02).
    """
    out = {"better": better, "worse": worse, "regime": regime, "alternative": "greater", "B": B, "n": 0}
    out |= {"delta_hat": None, "p": None, "p_reversal": None, "diagnostics": None, "reason": None}
    if result.anchor_failed:
        out["reason"] = "the anchor failed V5 (a bug, §6.2)"
        return out
    by = _runs_by_policy(result.runs)
    missing = [p for p in (better, worse) if (p, regime) not in by]
    if missing:
        out["reason"] = f"{missing} not in this evaluation under {regime}"
        return out
    label_of, w, _stratified = _strata(result.rows, weights)
    kept = [r for r in result.rows if r.excluded is None]
    episodes = [r.episode for r in kept]
    problems = [f"{p} {q}" for p in (better, worse) for q in _problems(by[(p, regime)], episodes)]
    if problems:
        out["reason"] = "pairing broken, no episode dropped selectively: " + "; ".join(problems)
        return out
    J_A = [by[(better, regime)][n].J_cents for n in episodes]
    J_B = [by[(worse, regime)][n].J_cents for n in episodes]
    D = [r.D for r in kept]
    labels = [label_of[n] for n in episodes]
    out["n"] = len(episodes)
    try:
        out["delta_hat"] = inference.delta_hat(J_A, J_B, D, labels, w)
        ups = inference.residuals(J_A, J_B, D, labels, w)
    except ValueError as err:
        out["reason"] = str(err)
        return out
    d = [b - a for a, b in zip(J_A, J_B, strict=True)]
    out["p"] = inference.sign_flip(d, labels, weights=w, B=B, entropy=entropy, alternative="greater")
    out["p_reversal"] = inference.sign_flip(d, labels, weights=w, B=B, entropy=entropy, alternative="less")
    diag = inference.skew_diagnostics(D, ups, labels)
    out["diagnostics"] = {s: {k: _float(v) for k, v in m.items()} for s, m in diag.items()}
    return out


def separation_report(
    result: EvalResult,
    *,
    pairs: Sequence[tuple[str, str]] = SEPARATION_PAIRS,
    regimes: Sequence[str] = REPORT_REGIMES,
    B: int | None = None,
    entropy: int,
) -> dict:
    """The M4 ladder report: every baseline by RSS_G per rung and regime, and (58) and one-sided (61) per pair.

    The pairs have a declared direction (§2.6), so ``inference.sign_flip`` is called with ``alternative="greater"``
    (its default is the two-sided (61)) for ``p``, and with ``alternative="less"`` on the same flips for
    ``p_reversal``: §2.6 counts a significant reversal as a failure, so the report shows both, and a reader tells a
    non-separation (both large) from a near-significant reversal (SPEC-M4R2-02). No threshold is applied here: `tiny`
    is a correctness fixture (Q82), and the F-size family's Holm step is M5's.

    For each pair also the §7.3 diagnostics (ESS, top-5 share, skewness of upsilon), plus D9 counts and the
    "not budget-compliant" labels. ``B`` defaults to ``scoring.inference.B_FLIPS``; ``entropy`` is the report's fixed
    evaluation entropy (never an E_split).

    A rung is one generator: the result is split by ``split_rungs``, each run placed by (rung, episode), so the result
    of one ``evaluate`` (one rung) gives one block and a result joined over rungs gives one block per rung, each equal
    to the block of that rung's own result, even when the rungs share episode indices as the difficulty ladder's do
    (§7.4, Q88); input a run could be placed from only by guessing is refused (``split_rungs``). Every baseline in the
    result is listed under each regime of ``regimes`` it ran, with its RSS row (``rss_table``); baselines all of whose
    runs raised a stub's ``NotImplementedError`` are marked ``built`` False.

    Raises:
        ValueError: as ``split_rungs``.

    """
    flips = inference.B_FLIPS if B is None else B
    rungs = []
    for gid, sub in split_rungs(result):
        rows = sub.rows
        exclusions = {c: sum(r.excluded == c for r in rows) for c in EXCLUSION_CAUSES}
        table = [row for row in rss_table(dataclasses.replace(sub, exclusions=exclusions)) if row["regime"] in regimes]
        rungs.append(
            {
                "generator_id": gid,
                "episodes": len(rows),
                "exclusions": exclusions,
                "anchor_failed": sub.anchor_failed,
                "baselines": table,
                "pairs": [_pair(sub, a, b, reg, STRATUM_WEIGHTS, flips, entropy) for reg in regimes for a, b in pairs],
            }
        )
    note = fixture_note(result.setup.get("instance_kind"))
    return {"note": note, "B": flips, "entropy": entropy, "regimes": list(regimes), "rungs": rungs}


def _episode_of(line: str) -> int | None:
    """The episode index of a ``v5_failures`` line ("<policy> <regime> ep<n>: ..."), or None."""
    head = line.split(":", 1)[0].split()
    return int(head[2][2:]) if len(head) >= 3 and head[2].startswith("ep") and head[2][2:].isdigit() else None


# ----- M5: the ladder reports (stream "ladders") -----------------------------------------------------------------
def pair_test(
    result: EvalResult,
    better: str,
    worse: str,
    *,
    regime: str = ladders.RANKED_REGIME,
    size: str | None = None,
    weights: Sequence[float] = STRATUM_WEIGHTS,
    B: int | None = None,
    entropy: int,
) -> ladders.PairTest:
    """One F-size test at one size: (58) and both one-sided (61) p-values of ``better`` against ``worse``.

    The same pairing, exclusions and refusals as ``separation_report``'s pairs (no episode dropped selectively); both p
    use the same flips (``entropy``), "greater" for the declared direction and "less" for the reversal (M5-O5 (6)).
    ``size`` defaults to the result's ``setup["instance_kind"]``.

    Raises:
        ValueError: with the reason, when the pair is undefined (a missing, failed or V5-failing run, the anchor's V5
            failure, D-bar <= 0) or the size is unknown.

    """
    flips = inference.B_FLIPS if B is None else B
    kind = size if size is not None else result.setup.get("instance_kind")
    if kind not in ladders.SIZES:
        raise ValueError(f"the size of an F-size test must be one of {ladders.SIZES}, got {kind!r}")
    out = _pair(result, better, worse, regime, weights, flips, entropy)
    if out["reason"] is not None:
        raise ValueError(f"{better} vs {worse} under {regime} on {kind}: {out['reason']}")
    J_A, J_B, _D, labels, w = paired_cents(result, better, worse, regime, weights)
    d = [b - a for a, b in zip(J_A, J_B, strict=True)]
    p_less = inference.sign_flip(
        d, labels, weights=w, B=flips, entropy=entropy, alternative=ladders.REVERSAL_ALTERNATIVE
    )
    return ladders.PairTest(kind, better, worse, regime, out["delta_hat"], out["p"], p_less)


def paired_cents(
    result: EvalResult, better: str, worse: str, regime: str, weights: Sequence[float] = STRATUM_WEIGHTS
) -> tuple[list[int], list[int], list[int], list[int], tuple[float, ...]]:
    """(J^better, J^worse, D, stratum labels, weights) on the kept episodes, paired as ``separation_report``'s pairs.

    The input of (58), (59) and V15 for one pair (``pilot.v15``); no episode is dropped selectively.

    Raises:
        ValueError: with the reason, on the anchor's V5 failure, a policy not run under ``regime``, or a missing,
            failed or V5-failing run on a kept episode.

    """
    if result.anchor_failed:
        raise ValueError("the anchor failed V5 (a bug, §6.2)")
    by = _runs_by_policy(result.runs)
    if missing := [p for p in (better, worse) if (p, regime) not in by]:
        raise ValueError(f"{missing} not in this evaluation under {regime}")
    label_of, w, _stratified = _strata(result.rows, weights)
    kept = [r for r in result.rows if r.excluded is None]
    episodes = [r.episode for r in kept]
    if problems := [f"{p} {q}" for p in (better, worse) for q in _problems(by[(p, regime)], episodes)]:
        raise ValueError("pairing broken, no episode dropped selectively: " + "; ".join(problems))
    J_A = [by[(better, regime)][n].J_cents for n in episodes]
    J_B = [by[(worse, regime)][n].J_cents for n in episodes]
    return J_A, J_B, [r.D for r in kept], [label_of[n] for n in episodes], tuple(w)


def f_size_report(
    tests: Sequence[ladders.PairTest],
    *,
    sizes: Sequence[str] = ladders.F_SIZE_SIZES,
    pairs: Sequence[tuple[str, str]] = SEPARATION_PAIRS,
    alpha: float = ladders.FAMILY_ALPHA,
) -> dict:
    """Family F-size (§2.6, §7.3) over the tests of the gated ``sizes``; the other sizes' tests are reported only.

    The family needs one test per (gated size, pair) (M5-O2 default (b): `small` and `full`, n_fam 4); a missing one
    fails it with the reason. Every test is listed with its Holm-adjusted p (gated tests), whether it passed and
    whether its reversal is significant; `tiny`'s tests carry the fixture note.
    """
    tests = tuple(tests)
    gated = [t for t in tests if t.size in sizes]
    expected = {(s, a, b) for s in sizes for a, b in pairs}
    have = {(t.size, t.better, t.worse) for t in gated}
    missing = sorted(expected - have)
    rows = []
    fam = ladders.f_size_family(gated, alpha=alpha) if gated else None
    for t in tests:
        row = dataclasses.asdict(t) | {"gated": t.size in sizes, "note": fixture_note(t.size)}
        if fam is not None and t in gated:
            i = gated.index(t)
            row |= {"adjusted": fam.adjusted[i], "rejected": fam.rejected[i], "reversal": i in fam.reversals}
            row["adjusted_reversal"] = fam.adjusted_reversal[i]
        rows.append(row)
    reason = f"missing tests (size, better, worse): {missing}" if missing else None
    if fam is None and reason is None:
        reason = "no test of a gated size"
    return {
        "sizes": list(sizes),
        "pairs": [list(p) for p in pairs],
        "n_fam": len(gated),
        "alpha": alpha,
        "tests": rows,
        "passed": bool(fam is not None and fam.passed and not missing),
        "reason": reason,
    }


def ladder_report(
    result: "ladders.LadderResult",
    *,
    delta_min: Fraction = ladders.DELTA_MIN,
    B: int | None = None,
    entropy: int,
    alpha: float = ladders.FAMILY_ALPHA,
    measure: str = ladders.MEASURE,
) -> dict:
    """The difficulty ladder of one size (§2.6, §7.4): delta_r (64) per rung, the adjacent tests and family F-knob.

    Every rung is weighted by the anchor strata (the rows' ``stratum``). An episode excluded at a gated rung
    (``ladders.gated_exclusions``) is dropped at every rung; one excluded only at a reported rung is dropped from the
    reported rungs' rows and tests alone, so F-knob's sample never depends on a rung it does not test (M5 gate
    ACC-M5-06; ``excluded`` and ``excluded_reported`` list them, each test its ``episodes``). A rung whose D-bar_s is
    undefined (a stratum of positive weight emptied) reports delta None with the reason; the tests still run on the
    strata present. The knob is gated when it is in ``profiles.GATED_KNOBS`` (M5-O3 default (a): γ only), else
    reported. When the anchor failed V5 (a bug) no verdict is given. ``measure`` (``ladders.MEASURES``) is the tested
    statistic: "delta", (64), by default; "loss", the γ ladder's gated measure (Q114's addendum; the committed
    experiment files), tests loss_r (73) on J^oracle with the same pairing, delta_min, flips and Holm, and reports each
    rung's loss beside its delta, the ratio being loss's. Every adjacent pair of the played rungs is tested; F-knob's
    Holm runs over the pairs of ``spec.gated_rungs`` alone, and a reported rung's test (``spec.reported``: its upper
    rung reported) keeps its raw p and ratio, with no adjusted p and no rejection.
    """
    from sbfv.disruption.profiles import GATED_KNOBS

    measure = ladders.check_measure(measure)
    flips = inference.B_FLIPS if B is None else B
    spec, setup = result.spec, result.setup
    T, S = int(setup["T"]), float(setup["sink_demand"])
    excluded = set(ladders.gated_exclusions(result))
    excluded_reported = set(result.excluded) - excluded
    samples = {}  # gated or reported -> (the episodes kept, their anchor strata)
    for gated, out in ((True, excluded), (False, excluded | excluded_reported)):
        rows = [r for r in result.rows[spec.anchor] if r.episode not in out]
        samples[gated] = ([r.episode for r in rows], [r.stratum for r in rows])
    kept = samples[True][0]

    def values(rung, gated: bool) -> tuple[list[int], list[int]]:
        """``rung``'s D and the tested values (D, or J^oracle under "loss") on the gated or reported sample."""
        episodes, strata = samples[gated]
        by_ep = {r.episode: r for r in result.rows[rung]}
        if [by_ep[n].stratum for n in episodes] != strata:
            raise ValueError(f"{ladders.rung_label(rung)}: the rows do not carry the anchor strata (§7.4; Q88)")
        rows = [by_ep[n] for n in episodes]
        D = [r.D for r in rows]
        return D, D if measure == "delta" else ladders.measure_values(rows, measure)

    def level(fn, x, strata) -> tuple[float | None, str | None]:
        """delta_r or loss_r of ``x``, or None with the reason (a stratum of positive weight emptied)."""
        try:
            return fn(x, strata, T=T, sink_demand=S), None
        except ValueError as err:
            return None, str(err)

    tested = ladders.delta_r if measure == "delta" else ladders.loss_r
    per_rung = []
    for rung in spec.rungs:
        gated = rung not in spec.reported
        strata = samples[gated][1]
        D, X = values(rung, gated)
        entry = {"rung": ladders.rung_label(rung), "gated": gated, "delta": None, "reason": None}
        entry["N_s"] = [strata.count(s) for s in range(1, len(STRATUM_WEIGHTS) + 1)]
        entry["D_bar_s"] = [
            _float(Fraction(sum(v for v, s2 in zip(D, strata) if s2 == s), entry["N_s"][s - 1]))
            if entry["N_s"][s - 1]
            else None
            for s in range(1, len(STRATUM_WEIGHTS) + 1)
        ]
        entry["delta"], entry["reason"] = level(ladders.delta_r, D, strata)
        if measure == "loss":
            entry["loss"], why = level(ladders.loss_r, X, strata)
            entry["reason"] = entry["reason"] or why
        per_rung.append(entry)
    tests = []
    for lo, hi in zip(spec.rungs, spec.rungs[1:]):
        gated = hi not in spec.reported
        episodes, strata = samples[gated]
        x_lo, x_hi = values(lo, gated)[1], values(hi, gated)[1]
        p = (
            ladders.difficulty_test(x_lo, x_hi, strata, delta_min=delta_min, B=flips, entropy=entropy)
            if episodes
            else None
        )
        m_lo, m_hi = level(tested, x_lo, strata)[0], level(tested, x_hi, strata)[0]
        ratio = m_hi / m_lo if m_lo not in (None, 0.0) and m_hi is not None else None
        tests.append(
            {
                "lower": ladders.rung_label(lo),
                "upper": ladders.rung_label(hi),
                "gated": gated,
                "episodes": len(episodes),
                "p": p,
                "ratio": ratio,
            }
        )
    family = {i: k for k, i in enumerate(i for i, t in enumerate(tests) if t["gated"])}  # test index -> F-knob's
    fam = ladders.f_knob_family([tests[i]["p"] for i in family], alpha=alpha) if family and kept else None
    for i, t in enumerate(tests):
        k = None if fam is None else family.get(i)
        t["adjusted"] = None if k is None else fam.adjusted[k]
        t["rejected"] = None if k is None else fam.rejected[k]
    gated = spec.knob in GATED_KNOBS
    reason = None
    if result.anchor_failed:
        reason = "the anchor failed V5 on this ladder (a bug, §6.2): no verdict"
    elif fam is None:
        reason = "no gated rung difference to test" if len(spec.gated_rungs) < 2 else "no episode kept"
    return {
        "note": fixture_note(setup.get("instance_kind")),
        "knob": spec.knob,
        "gated": gated,
        "measure": measure,
        "delta_min": str(delta_min),
        "alpha": alpha,
        "B": flips,
        "entropy": entropy,
        "episodes": len(kept),
        "excluded": sorted(excluded),
        "excluded_reported": sorted(excluded_reported),
        "anchor_failed": result.anchor_failed,
        "reported_rungs": [ladders.rung_label(r) for r in spec.reported],
        "rungs": per_rung,
        "tests": tests,
        "passed": None if reason or not gated else fam.passed,
        "reason": reason if reason else (None if gated else f"knob {spec.knob!r} is reported, not gated (M5-O3)"),
    }


# why the size ladder carries no verdict (§2.6, §7.4): the owner's answer of 2026-09-29, Q114's superseding note
SIZE_LADDER_REPORTED = (
    "the size ladder is reported, not gated (the owner's answer of 2026-09-29, \"Report it, don't gate "
    "(Recommended)\"; Q114's superseding note): each measure's test at its raw p, no Holm, no family, no verdict"
)


def size_ladder_report(
    samples: Sequence["ladders.SizeSample"],
    *,
    delta_min: Fraction = ladders.DELTA_MIN,
    B: int = ladders.B_PERM,
    entropy: int,
    statistic: str = ladders.SIZE_STATISTIC,
    measures: Sequence[str] = ladders.SIZE_MEASURES,
) -> dict:
    """The size ladder (§2.6, §7.4), reported: loss (73) and delta (64) per size and the unpaired tests between sizes.

    ``samples`` in ladder order (each a size's anchor-rung J^oracle and D, ``ladders.size_sample``). Every adjacent
    pair is tested once per measure of ``measures`` (``ladders.SIZE_MEASURES``: loss, then delta) by
    ``ladders.size_ladder_test``, each test with its raw p and the ratio of the measure, upper over lower. Nothing is
    gated (the owner's answer of 2026-09-29, Q114's superseding note): no Holm, no family (F-knob's or F-size's), no
    verdict, so ``passed`` is None with ``SIZE_LADDER_REPORTED`` as the reason, whatever the p. The tests share
    ``entropy``; `tiny` carries the fixture note (Q82).

    Raises:
        ValueError: on no measure, an unknown one, or a sample without a measure's values (``SizeSample.values``).

    """
    measures = tuple(ladders.check_measure(m) for m in measures)
    if not measures:
        raise ValueError(f"the size ladder reports at least one measure of {ladders.MEASURES}")
    samples = tuple(samples)
    sizes = []
    for s in samples:
        entry = {"size": s.size, "episodes": len(s.D), "T": s.T, "sink_demand": s.sink_demand, "delta": None}
        entry |= {"loss": None, "note": fixture_note(s.size)}
        for name, values, fn in (("delta", s.D, ladders.delta_r), ("loss", s.J_oracle, ladders.loss_r)):
            if values is None:
                continue
            try:
                entry[name] = fn(values, s.strata, T=s.T, sink_demand=s.sink_demand, weights=s.weights)
            except ValueError as err:
                entry["reason"] = entry.get("reason") or str(err)
        sizes.append(entry)
    tests = []
    for i, (lo, hi) in enumerate(zip(samples, samples[1:])):
        for measure in measures:
            p = ladders.size_ladder_test(
                lo, hi, delta_min=delta_min, B=B, entropy=entropy, statistic=statistic, measure=measure
            )
            m_lo, m_hi = sizes[i][measure], sizes[i + 1][measure]
            ratio = m_hi / m_lo if m_lo not in (None, 0.0) and m_hi is not None else None
            tests.append({"lower": lo.size, "upper": hi.size, "measure": measure, "p": p, "ratio": ratio})
    return {
        "gated": False,
        "measures": list(measures),
        "statistic": statistic,
        "delta_min": str(delta_min),
        "B": B,
        "entropy": entropy,
        "sizes": sizes,
        "tests": tests,
        "passed": None,
        "reason": SIZE_LADDER_REPORTED,
    }


def per_rung_rss(result: "ladders.LadderResult", *, policies: Sequence[str] = ladders.PER_RUNG_POLICIES) -> dict:
    """The pooled RSS (56) of ``policies`` (and their variants) at every rung, on the anchor strata: reported only.

    §2.6: RSS can rise with difficulty when naive collapses faster, so it is never gated. A D-only ladder has no
    policy runs: the rows are empty with the reason.
    """
    rows = []
    for rung in result.spec.rungs:
        res = result.evals.get(rung)
        if res is None:
            continue
        for row in rss_table(res):
            if base_name(row["policy"]) in policies:
                rows.append(
                    {"rung": ladders.rung_label(rung)}
                    | {k: row[k] for k in ("policy", "regime", "rss_G", "rss_G_reason", "rss_s", "N_s")}
                )
    reason = None if result.evals else "a D-only ladder plays no policy (LadderSpec.d_only)"
    return {"gated": False, "policies": list(policies), "rows": rows, "reason": reason}


def transfer_report(
    source: Sequence[Mapping],
    target: Sequence[Mapping],
    *,
    policy: str = ladders.TRANSFER_POLICY,
    regime: str = ladders.RANKED_REGIME,
    sizes: tuple[str, str] = (ladders.TRANSFER_FROM, ladders.TRANSFER_TO),
) -> dict:
    """Transfer (§2.6): ``policy``'s variant tuned on the source size (best RSS_G there), scored on the target.

    ``source`` and ``target`` are ``rss_table`` rows of the two sizes. The gap is the target's best variant's RSS_G
    minus the tuned variant's there (>= 0), reported with no threshold (M5-O5 (6)); a tie in the tuning takes the
    first variant in ``policy_order``. With one scored variant on the source nothing is tuned, and with one on the
    target the gap is 0 by construction: ``reason`` says which beside the gap, so a gap of 0 never reads as a perfect
    transfer (the M5 pilot plays `mpc_det` at H = L only, Q110's third addendum; M5 re-gate ACC-M5R-03).
    """

    def variants(table):
        out = {}
        for row in table:
            if base_name(row["policy"]) == policy and row["regime"] == regime and row.get("rss_G") is not None:
                out[row["policy"]] = row["rss_G"]
        return out

    src, tgt = variants(source), variants(target)
    out = {"policy": policy, "regime": regime, "source": sizes[0], "target": sizes[1], "threshold": None}
    out |= {"tuned": None, "rss_source": None, "rss_target": None, "best_target": None, "rss_best_target": None}
    out |= {"gap": None, "reason": None}
    if not src or not tgt:
        out["reason"] = f"no scored {policy} variant under {regime} on the {'source' if not src else 'target'} size"
        return out
    tuned = max(sorted(src, key=policy_order), key=lambda k: src[k])
    best = max(sorted(tgt, key=policy_order), key=lambda k: tgt[k])
    out |= {"tuned": tuned, "rss_source": src[tuned], "best_target": best, "rss_best_target": tgt[best]}
    if tuned not in tgt:
        out["reason"] = f"the tuned variant {tuned} has no scored run on the target size"
        return out
    out |= {"rss_target": tgt[tuned], "gap": tgt[best] - tgt[tuned]}
    why = []
    if len(src) == 1:
        why.append(f"one scored {policy} variant under {regime} on the source size, so nothing is tuned")
    if len(tgt) == 1:
        why.append("one scored variant on the target size, so the gap is 0 by construction")
    out["reason"] = "; ".join(why) or None
    return out
