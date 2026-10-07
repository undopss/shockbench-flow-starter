"""The episode runner (milestone M4, stream "runner").

Strata, the sealed LPs, every baseline with its replay (53) and bound, over joblib workers (design §6.3, §7.1-7.2,
§9.5, §10 V1, V5, V30; Q62, Q82, Q95).

Readings (design §12 M4 row "Runner", and the rows under the bold head row "M4 stream runner"):

- **Strata** are filled in index order from the full omega, so the fill is policy-independent: candidates
  n = 0, 1, ... are drawn, each harm taken from the full omega (``harm.episode_harm``), its stratum by
  ``strata.stratum`` on the rung's cut points, and the first N_s of each stratum kept; a stratum still unfilled after
  ``max_candidates`` is reported, never padded. `tiny` is a correctness fixture (Q82): its report cuts at a small M of
  cut draws, stated in the command and the output name, not the design's 10^5. Candidates are drawn in batches over
  ``parallel.ordered_map`` (twice the keys still missing, at least four per worker, at most ``_BATCH``); the keys kept
  are the first N_s in index order whatever the batch or worker count.
- **One episode** (``run_episode_task``, a pure worker): omega and omega^0 (``omega.injected.event_free``), their marks
  and LPs; the oracle on both (``linprog`` highs-ipm, cold, never a warm solve: Q95); the anchor (end-aware naive with
  the generator's F_Q, prediction_free, Q10) on both, and ``nd`` on omega^0 ((57)); then each (policy, regime) with its
  own D9 fallback, replay (53), cents equality and the oracle bound in USD. A policy is built fresh per episode
  (``registry.make_policy``). The worker never computes naive's F_Q or ``sz_state_base_stock``'s transient paths:
  the parent computes them once per rung and passes them in the task (``naive_fq.remember_quantiles``,
  ``sz_state_base_stock.remember_paths``), and never calls ``naive_fq.anchor_policy`` or ``fallback_spec``, which
  would recompute F_Q in a fresh process: the anchor is ``NaivePolicy`` and the fallback ``NaiveFallback`` built from
  the task's quantiles.
- **Exclusions**: a non-optimal sealed LP excludes the episode for every policy, counted by cause
  (``results.EXCLUSION_CAUSES``); an anchor V5 failure is recorded and makes the entry point exit 1. The policies still
  run on an excluded episode (their replay (53) is checked; the bound is not, the oracle having no point).
- **Failed runs**: a policy that raises (a stub's ``NotImplementedError("M4 stream <name>")`` included) is a failed run
  with "<ExceptionType>: <message>", never substituted; the reports label a baseline whose every run raised a stub's
  error "not built" (``results.NOT_BUILT``). The environment refusing a regime on an episode's omega is the request's
  error, never a policy's: ``check_request`` refuses the known case (an injected list under a regime that shows a
  warning, messages or a blackout spell) before anything is drawn, and a worker whose ``Env.reset`` refuses a regime
  raises.
- **Parallelism** only through ``parallel.ordered_map`` (§12 "joblib inside the package": joblib is imported only when
  n_jobs != 1); every draw is keyed (27), so no result depends on n_jobs or the episode order (V1): ``evaluate`` sorts
  the episodes by index before mapping. Timings come from a separate serial pass (``timing_pass``, ``timings``), each
  cold reset in a fresh interpreter left as a fresh policy container finds it (omega drawn by the parent, numba's
  cache an empty directory).
- The policy seed of each episode is ``omega.seeds.policy_seed(E_split, split, n, "local")``; E_split never leaves
  ``evaluate`` (the result records its SHA-256 only, in ``EvalResult.setup``). A policy that declares a ``seed_id``
  (a kit agent of ``policies.kit_agents``: its submission zip's SHA-256) plays with that salt in place of "local", the
  seed the trusted runner gives that zip (``episode_policy_seed``; the M5 pilot's participant-like entries).
- **Ladders** (M5, stream "ladders"; design §7.4, Q88; §12 rows under "M5 stream ladders"): ``rung_keys`` re-draws the
  anchor rung's keys at another rung of the same size (same split, indices and anchor strata; the rung's omega hash
  and harm), ``evaluate_keys`` plays given keys (``evaluate`` is ``episode_keys`` then ``evaluate_keys``), and the
  D-only path (``evaluate_d``, ``run_d_task``) plays the oracle and the anchor on omega alone, the two values behind D
  of (57), never omega^0, ``nd`` or a baseline. naive's F_Q is computed once per rung in the parent, as here.
"""

import copy
import dataclasses
import functools
import hashlib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sbfv.evaluation.results import (
    ANCHOR,
    ANCHOR0,
    ANCHOR_LABELS,
    ANCHOR_REGIME,
    EXCLUSION_CAUSES,
    ND0,
    EvalResult,
    PolicyRun,
    ReferenceRow,
    exclusion_cause,
    oracle_optimal,
    replay_checks,
    run_failures,
    substitution_counts,
)
from sbfv.evaluation.timings import StepTimings, fresh_numba_cache, machine_record, timed_rollout
from sbfv.information.theta import REGIME_NAMES
from sbfv.oracle.lp import ORACLE_METHOD
from sbfv.parallel import ordered_map
from sbfv.policies import registry
from sbfv.policies.lp_common import OPTIMAL
from sbfv.policies.naive_fq import REPLICATIONS, check_replications
from sbfv.policies.registry import GeneratorRef


EPISODE_KINDS = ("generated", "injected")
SUBMISSION = "local"  # the submission id of local runs in the policy seed (27)
STRATA = 4  # harm strata of (44): one N_s per p_s
FAILURE_CHARS = 500  # a failed run keeps the first characters of its exception text (the type always)
_BATCH = 64  # candidates per ``ordered_map`` call while filling the strata (no result depends on it)


@dataclass(frozen=True)
class EpisodeSpec:
    """Which episodes an evaluation plays: a generated split filled to N_s per stratum, or a plain index range.

    Raises:
        ValueError: on a kind outside ``EPISODE_KINDS``, a generated spec without ``generator``, both or neither of
            ``n_per_stratum`` and ``episodes`` on the generated kind, a stratum count that is not 4 (p_s of (44)),
            ``cut_draws`` or ``max_candidates`` < 1, or ``fq_replications`` refused by ``naive_fq.check_replications``.
            Also: stratified filling without ``cut_draws`` and ``cut_entropy``; on the injected kind a generator,
            ``n_per_stratum`` or cut settings (an injected list has no generator and no strata) or no ``episodes``;
            events or demand noise off on the generated kind; cut settings on a plain range; a negative or repeated
            episode index; an N_s < 0.

    """

    instance: str  # a packaged instance name or a path (``instance.load_instance``)
    kind: str  # "generated" or "injected"
    split: str = "dev"
    generator: GeneratorRef | None = None  # the split's public profile and rung (generated kind)
    fq_replications: int = REPLICATIONS  # naive's F_Q and sz's paths; other counts are smoke runs, named so
    cut_draws: int | None = None  # M of (44): harm draws behind the cut points (a small, stated M on `tiny`)
    cut_entropy: int | None = None  # the cut points' own root (§9.5), never an E_split
    n_per_stratum: tuple[int, ...] | None = None  # N_s per harm stratum
    episodes: tuple[int, ...] | None = None  # plain range mode: these indices, unstratified
    max_candidates: int = 10_000  # candidates drawn at most while filling the strata
    events: tuple = ()  # the injected kind's event list (``omega.injected.InjectedEvent``)
    demand_noise: bool = True  # the injected kind's (21) noise (off in the fixture's lists, §2.4); generated: always on

    def __post_init__(self) -> None:
        if self.kind not in EPISODE_KINDS:
            raise ValueError(f"kind must be one of {EPISODE_KINDS}, got {self.kind!r}")
        check_replications(self.fq_replications)
        for name in ("cut_draws", "max_candidates"):
            v = getattr(self, name)
            if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 1):
                raise ValueError(f"{name} must be an integer >= 1, got {v!r}")
        if self.episodes is not None:
            eps = tuple(self.episodes)
            if any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in eps) or len(set(eps)) != len(eps):
                raise ValueError(f"episodes must be distinct integer indices >= 0, got {self.episodes!r}")
            object.__setattr__(self, "episodes", eps)
        if self.kind == "injected":
            if self.generator is not None or self.n_per_stratum is not None:
                raise ValueError(
                    "an injected list has no generator and no harm strata (§8.1): generator and "
                    "n_per_stratum are read by the generated kind only"
                )
            if self.cut_draws is not None or self.cut_entropy is not None:
                raise ValueError("cut_draws and cut_entropy are read by the generated kind only")
            if self.episodes is None:
                raise ValueError("the injected kind plays a plain range: give episodes")
            if not isinstance(self.demand_noise, bool):
                raise ValueError(f"demand_noise must be a bool, got {self.demand_noise!r}")
            object.__setattr__(self, "events", tuple(self.events))
            return
        if self.generator is None:
            raise ValueError("the generated kind needs its public generator (registry.GeneratorRef)")
        if self.events:
            raise ValueError("the generated kind draws its events (§4); an injected list is refused")
        if self.demand_noise is not True:
            raise ValueError("the generated kind always draws the demand noise of (21)")
        if (self.n_per_stratum is None) == (self.episodes is None):
            raise ValueError("the generated kind takes exactly one of n_per_stratum (strata) and episodes (range)")
        if self.episodes is not None and (self.cut_draws is not None or self.cut_entropy is not None):
            raise ValueError("a plain range reads no cut points: cut_draws and cut_entropy serve the strata only")
        if self.n_per_stratum is not None:
            n_s = tuple(self.n_per_stratum)
            if len(n_s) != STRATA:
                raise ValueError(f"n_per_stratum needs one N_s per harm stratum of (44) ({STRATA}), got {n_s!r}")
            if any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in n_s):
                raise ValueError(f"every N_s must be an integer >= 0, got {n_s!r}")
            if self.cut_draws is None or self.cut_entropy is None:
                raise ValueError("filling the strata needs cut_draws and cut_entropy (the cut points' own root)")
            object.__setattr__(self, "n_per_stratum", n_s)

    @property
    def stratified(self) -> bool:
        """Whether the episodes are filled into harm strata (else a plain index range)."""
        return self.n_per_stratum is not None


@dataclass(frozen=True)
class EpisodeKey:
    """One episode of the split: its index, harm and stratum, and omega's identity (never E_split)."""

    split: str
    episode: int
    harm: float | None
    stratum: int | None
    omega_hash: str
    generator_id: str


@dataclass(frozen=True)
class EpisodeTask:
    """Everything a worker needs for one episode (plain, picklable data; the quantiles and paths precomputed)."""

    spec: EpisodeSpec
    key: EpisodeKey
    entropy: int  # E_split of the split: trusted side only, never written out
    policies: tuple[tuple[str, object | None], ...]  # (baseline name, its parameter dataclass or None)
    regimes: tuple[str, ...]  # registry names (``information.theta.REGIME_NAMES``)
    fq_quantile: Mapping[tuple, float] | None  # naive's generator quantiles; None on an injected list
    transient_paths: Mapping[tuple[int, str], object] | None  # sz's o^tr paths per (c, pool); None on injected
    oracle_method: str = "highs-ipm"
    store_actions: bool = False  # also return each run's V24 record (``conformance.conformance_record``)


@dataclass(frozen=True)
class EpisodeResult:
    """A worker's answer: the reference row, the runs, and (when asked) each run's conformance record.

    ``references`` are the anchor on omega and omega^0 and ``nd`` on omega^0 as runs (``results.ANCHOR``, ``ANCHOR0``,
    ``ND0``), each replayed (53) in its own LP.
    """

    row: ReferenceRow
    runs: tuple[PolicyRun, ...]
    records: tuple = ()  # (policy, regime, ConformanceRecord) when ``EpisodeTask.store_actions``
    references: tuple[PolicyRun, ...] = ()


# ----- strata --------------------------------------------------------------------------------------------------------
def _candidate(inst, params, entropy: int, split: str, episode: int) -> tuple[float, str]:
    """(H of (42) of the full omega, omega's hash) for candidate ``episode`` (module docstring)."""
    from sbfv.disruption.harm import episode_harm
    from sbfv.disruption.sampler import sample_omega

    omega = sample_omega(inst, params, entropy, episode, split)
    return float(episode_harm(inst, omega)), omega.hash


def fill_strata(
    inst, params, entropy: int, split: str, cuts, n_per_stratum: Sequence[int], *, max_candidates: int, n_jobs: int = 1
) -> tuple[EpisodeKey, ...]:
    """The first N_s episodes of each harm stratum, in index order, harms from the full omega (module docstring).

    Raises:
        ValueError: if the cut points belong to another generator (``strata.stratum`` refuses them), or a stratum is
            still unfilled after ``max_candidates`` candidates (the message names it and its count).

    """
    from sbfv.disruption.params import generator_id
    from sbfv.disruption.strata import stratum

    gid = generator_id(params, inst)
    stratum(0.0, cuts, generator_id=gid)  # refuses cut points of another (size, rung) before any draw
    need = tuple(n_per_stratum)
    if len(need) != len(cuts.values) + 1:
        raise ValueError(f"one N_s per stratum of the cut points ({len(cuts.values) + 1}), got {need!r}")
    kept: dict[int, list[EpisodeKey]] = {s: [] for s in range(1, len(need) + 1)}
    n = 0
    draw = functools.partial(_candidate, inst, params, entropy, split)
    width = 1 if n_jobs == 1 else _workers(n_jobs)
    while n < max_candidates and any(len(kept[s]) < need[s - 1] for s in kept):
        missing = sum(need[s - 1] - len(kept[s]) for s in kept)
        batch = range(n, min(n + min(_BATCH, max(2 * missing, 4 * width)), max_candidates))
        for ep, (h, omega_hash) in zip(batch, ordered_map(draw, batch, n_jobs), strict=True):
            s = stratum(h, cuts, generator_id=gid)
            if len(kept[s]) < need[s - 1]:
                kept[s].append(EpisodeKey(split, ep, h, s, omega_hash, gid))
        n = batch.stop
    short = {s: f"{len(v)} of {need[s - 1]}" for s, v in kept.items() if len(v) < need[s - 1]}
    if short:
        raise ValueError(f"strata still unfilled after {max_candidates} candidates: {short} (never padded)")
    return tuple(sorted((k for v in kept.values() for k in v), key=lambda k: k.episode))


def _workers(n_jobs: int) -> int:
    """The worker count joblib gives ``n_jobs`` (joblib imported only here, never on a serial run)."""
    from joblib import effective_n_jobs

    return effective_n_jobs(n_jobs)


def _plain_key(spec: EpisodeSpec, inst, params, entropy: int, episode: int) -> EpisodeKey:
    """The key of a plain-range episode: omega's hash, and on the generated kind its harm (no stratum)."""
    if spec.kind == "generated":
        harm, omega_hash = _candidate(inst, params, entropy, spec.split, episode)
        return EpisodeKey(spec.split, episode, harm, None, omega_hash, _generator_id(params, inst))
    omega = _omega(spec, inst, params, entropy, spec.split, episode)
    return EpisodeKey(spec.split, episode, None, None, omega.hash, str(omega["meta_generator_id"]))


def _generator_id(params, inst) -> str:
    from sbfv.disruption.params import generator_id

    return generator_id(params, inst)


# ----- one episode ---------------------------------------------------------------------------------------------------
def _resolve(spec: EpisodeSpec):
    """The episode's instance and its generator's ``GeneratorParams`` on the generated kind (None on an injected list).

    On the generated kind the instance is the spec's at the generator's rung (``Instance.at_rung``: that rung's warm
    start, §2.3; owner queue M5-O37 (b)), so omega is drawn on it and every policy and the oracle start from its block;
    an injected list plays the file's own (the anchor rung's) block.
    """
    from sbfv.instance import load_instance

    inst = load_instance(spec.instance)
    if spec.kind != "generated":
        return inst, None
    params = spec.generator.params(inst)
    return inst.at_rung(params.hawkes.gamma), params


def _omega(spec: EpisodeSpec, inst, params, entropy: int, split: str, episode: int):
    """The omega of one episode: the generator's draw, or the injected list built on (E_split, n) (§4.1)."""
    if spec.kind == "generated":
        from sbfv.disruption.sampler import sample_omega

        return sample_omega(inst, params, entropy, episode, split)
    from sbfv.omega.injected import build_omega

    return build_omega(inst, spec.events, entropy=entropy, episode=episode, split=split, demand_noise=spec.demand_noise)


def _failure_text(err: BaseException) -> str:
    text = f"{type(err).__name__}: {err}"
    return text if len(text) <= FAILURE_CHARS else text[:FAILURE_CHARS] + "..."


def _telemetry(policy) -> dict:
    """Sums of the policy's ``StepTelemetry`` (``policies.base``): fallback weeks, failed scenarios, rungs that ended.

    ``ladder_rungs`` counts, per rung, the attempts whose HiGHS model status is ``lp_common.OPTIMAL``: a solve's climb
    of the status ladder ends on the first optimal rung, so each solve that succeeded counts once, on its rung.
    """
    tel = getattr(policy, "telemetry", None) or []
    rungs = Counter(rung for t in tel for rung, status in t.trail if status == OPTIMAL)
    return {
        "internal_fallback_weeks": sum(bool(t.fallback) for t in tel),
        "scenarios_failed": sum(int(t.scenarios_failed) for t in tel),
        "ladder_rungs": dict(sorted(rungs.items())),
    }


@dataclass(frozen=True)
class _World:
    """omega or omega^0 of one episode, with its marks, its LP (51) and what the oracle bound of (53) needs."""

    omega: object
    marks: object
    model: object
    J_oracle_usd: float | None
    optimal: bool


def _run(
    label: str, regime: str, episode: int, rung: str, policy, world: _World, play
) -> tuple[PolicyRun, object | None]:
    """One policy's episode as a ``PolicyRun`` and its trajectory (None when it raised: a failed run).

    ``play(policy, world, regime)`` rolls the episode out; the trajectory is replayed (53) in ``world.model`` with the
    oracle bound when ``world.optimal``. The run carries the episode's index and ``rung``, the row's ``generator_id``
    (on omega^0 too, whose own generator id is the event-free twin's), so a result joined over rungs places it by
    (rung, episode) (``results.split_rungs``).
    """
    try:
        traj = play(policy, world, regime)
    except Exception as err:  # a policy or simulator failure: recorded, never substituted (module docstring)
        run = PolicyRun(label, regime, episode, None, None, None, None, 0, 0, _failure_text(err), (), None)
        return dataclasses.replace(run, generator_id=rung), None
    from sbfv.oracle.replay import trajectory_usd

    invalid, d9 = substitution_counts(traj)
    run = PolicyRun(
        policy=label,
        regime=regime,
        episode=episode,
        J_cents=traj.J_cents,
        J_usd=trajectory_usd(traj),
        trajectory_sha256=traj.sha256(),
        checks=replay_checks(world.model, traj, world.J_oracle_usd, world.optimal),
        invalid_entries=invalid,
        d9_substitutions=d9,
        failed=None,
        cents_per_week=tuple(r.cost_cents for r in traj.records),
        salvage_cents=traj.salvage_cents,
        generator_id=rung,
        **_telemetry(policy),
    )
    return run, traj


def _fallback(inst, params, fq):
    """The episode's D9 fallback (§9.3, Q98): ``NaiveFallback`` from the task's quantiles, or "naive" when injected."""
    if params is None:
        return "naive"
    from sbfv.policies.naive import NaiveFallback

    return NaiveFallback(_generator_id(params, inst), fq, instance_digest=inst.family_digest, end_aware=True)


def _seed_caches(spec: EpisodeSpec, inst, params, fq, paths) -> None:
    """Put the parent's F_Q quantiles and sz's paths in this process's caches (trusted seams, never recomputed)."""
    from sbfv.policies.naive_fq import remember_quantiles

    remember_quantiles(inst, params, spec.fq_replications, dict(fq))
    if paths is not None:
        from sbfv.policies import sz_state_base_stock as sz

        sz.remember_paths(inst, params, spec.fq_replications, paths)


def episode_policy_seed(policy, entropy: int, split: str, episode: int) -> int:
    """The policy seed (27) ``policy`` plays episode ``episode`` of ``split`` with (module docstring).

    Salted by ``SUBMISSION`` ("local", M4's local runs and the board's baselines), or by the policy's own ``seed_id``
    when it declares one: a kit agent's submission SHA-256 (``policies.kit_agents``), the salt the trusted runner gives
    that zip (``hosting.trusted``), so the agent plays the episode as the runner and ``shockbench_flow_agent.evaluate``
    would. E_split stays inside the worker, as for every seed.
    """
    from sbfv.omega.seeds import policy_seed

    salt = getattr(policy, "seed_id", None)
    return policy_seed(entropy, split, episode, SUBMISSION if salt is None else salt)


def _episode_inputs(spec: EpisodeSpec, key: EpisodeKey, entropy: int, fq, paths, omega=None) -> tuple:
    """What a worker plays one episode with: (instance, F_Q, omega, D9 fallback, policy seed, ``PolicyContext``).

    On the generated kind the parent's quantiles and paths seed this process's caches first; on an injected list F_Q
    is None. Every value is a pure function of the arguments (keyed draws only). ``omega``, when given, is the
    episode's omega drawn elsewhere (the timing pass's parent): it is checked against the key and not drawn again.

    Raises:
        ValueError: if a given omega is not the key's.

    """
    from sbfv.omega.seeds import policy_seed

    inst, params = _resolve(spec)
    if params is None:
        fq = None
    else:
        _seed_caches(spec, inst, params, fq, paths)
    if omega is None:
        omega = _omega(spec, inst, params, entropy, key.split, key.episode)
    elif omega.hash != key.omega_hash:
        raise ValueError(f"episode {key.episode}: the omega given is not the key's")
    fallback = _fallback(inst, params, fq)
    pseed = policy_seed(entropy, key.split, key.episode, SUBMISSION)
    context = registry.PolicyContext(fq_quantile=fq, generator=spec.generator, fq_replications=spec.fq_replications)
    return inst, fq, omega, fallback, pseed, context


def run_episode_task(task: EpisodeTask) -> EpisodeResult:
    """One episode (module docstring): the reference row and every (policy, regime) run, as plain data.

    A policy that raises is recorded as a failed run (``PolicyRun.failed``), never substituted. With
    ``task.store_actions`` the worker makes each finished run's V24 record itself,
    ``conformance.conformance_record(inst, traj, policy_seed=..., fallback=...)``, since only it holds the policy seed
    and the episode's ``NaiveFallback`` (E_split never leaves ``evaluate``; a ``Trajectory`` carries neither), and
    returns them as ``EpisodeResult.records``; ``evaluate`` gathers them into ``EvalResult.records``, which ``run_eval``
    writes as ``conformance.save_entry`` entries under ``actions/``.

    Raises:
        ValueError: if omega's hash is not the key's (the parent and the worker drew different omegas), or the
            environment refuses one of the regimes on this omega (``Env.reset``, probed once per regime before any
            policy runs: the request's error, never a policy's failed run; ``check_request`` refuses the known cases
            before anything is drawn).
        Exception: whatever the oracle, the anchor or a conformance record raises (a bug: never recorded as a run).

    """
    from sbfv.dynamics.env import Env, rollout
    from sbfv.marks import compute_marks
    from sbfv.omega.injected import event_free
    from sbfv.oracle.lp import build_lp, solve_oracle
    from sbfv.policies.naive import NaivePolicy

    key = task.key
    inst, fq, omega, fallback, pseed, context = _episode_inputs(
        task.spec, key, task.entropy, task.fq_quantile, task.transient_paths
    )
    if omega.hash != key.omega_hash:
        raise ValueError(f"episode {key.episode}: omega {omega.hash[:12]}... is not the key's {key.omega_hash[:12]}...")
    omega0 = event_free(omega, inst)
    marks, marks0 = compute_marks(inst, omega), compute_marks(inst, omega0)
    for regime in task.regimes:  # the environment's refusal (no fallback: no naive plan) raises here, never in a run
        try:
            Env(fallback=None).reset(inst, regime, omega, pseed, marks=marks)
        except ValueError as err:
            raise ValueError(
                f"episode {key.episode}: the environment refuses regime {regime!r} on this omega ({err}); a request "
                "error, never a policy's failed run"
            ) from err
    model, model0 = build_lp(inst, marks), build_lp(inst, marks0)
    oracle, oracle0 = solve_oracle(model, task.oracle_method), solve_oracle(model0, task.oracle_method)
    optimal, optimal0 = oracle_optimal(oracle), oracle_optimal(oracle0)
    world = _World(omega, marks, model, oracle.J_usd, optimal)
    world0 = _World(omega0, marks0, model0, oracle0.J_usd, optimal0)

    def seed(policy) -> int:  # pseed ("local") unless the policy declares its own salt
        return episode_policy_seed(policy, task.entropy, key.split, key.episode)

    def play(policy, w: _World, regime: str):
        return rollout(inst, policy, w.omega, regime, seed(policy), marks=w.marks, fallback=fallback)

    # the anchor of (55) on omega and omega^0 (prediction-free, Q10) and nd on omega^0 (57): the references
    n, rung = key.episode, str(omega["meta_generator_id"])  # every run of the episode carries the row's rung
    anchor, _ = _run(ANCHOR, ANCHOR_REGIME, n, rung, NaivePolicy(fq_quantile=fq), world, play)
    anchor0, _ = _run(ANCHOR0, ANCHOR_REGIME, n, rung, NaivePolicy(fq_quantile=fq), world0, play)
    for ref in (anchor, anchor0):
        if ref.failed is not None:  # the anchor is the scorer's reference: its crash is a bug, never a failed run
            raise RuntimeError(f"episode {key.episode}: the anchor raised: {ref.failed}")
    nd0, _ = _run(ND0, ANCHOR_REGIME, n, rung, registry.make_policy("nd", context), world0, play)
    excluded = exclusion_cause(oracle, oracle0)  # the one rule (results, 'one RSS rule')
    row = ReferenceRow(
        episode=key.episode,
        stratum=key.stratum,
        harm=key.harm,
        omega_hash=omega.hash,
        generator_id=rung,
        oracle_status=oracle.status,
        oracle_method=oracle.method,
        oracle_solver=oracle.solver,
        oracle_seconds=oracle.seconds,
        J_oracle_cents=oracle.J_cents if optimal else None,
        J_oracle_usd=oracle.J_usd if optimal else None,
        J_naive_cents=anchor.J_cents,
        naive_sha256=anchor.trajectory_sha256,
        naive_invalid=anchor.invalid_entries,
        naive_d9=anchor.d9_substitutions,
        oracle0_status=oracle0.status,
        oracle0_solver=oracle0.solver,
        J_oracle0_cents=oracle0.J_cents if optimal0 else None,
        J_naive0_cents=anchor0.J_cents,
        J_nd0_cents=nd0.J_cents,
        excluded=excluded,
    )
    runs, records = [], []
    for name, params_obj in task.policies:
        for regime in task.regimes:
            policy = registry.make_policy(name, context, params_obj)
            label = getattr(policy, "name", name)
            run, traj = _run(label, regime, n, rung, policy, world, play)
            runs.append(run)
            if task.store_actions and traj is not None:
                from sbfv.evaluation import conformance

                record = conformance.conformance_record(inst, traj, policy_seed=seed(policy), fallback=fallback)
                records.append((label, regime, record))
    return EpisodeResult(row, tuple(runs), tuple(records), (anchor, anchor0, nd0))


# ----- the whole evaluation ------------------------------------------------------------------------------------------
def entropy_sha256(value: int) -> str:
    """The SHA-256 hex digest of E_split's decimal text (as ``sbf_boundary.entropy_sha256``): the root by name only."""
    return hashlib.sha256(str(value).encode()).hexdigest()


def needs_generated_omega(regime: str) -> bool:
    """Whether ``regime`` shows a warning, messages or a blackout spell, which only a generated omega carries.

    The information view's own rule (design §12 "Resets without what a regime needs"): a warning (45) or messages (49)
    need ``meta_information_params`` and the latent paths, a blackout rung a spell of its kind; an injected omega has
    none of them, so ``Env.reset`` refuses such a regime on it.
    """
    from sbfv.information.theta import phi_by_channel, resolve_regime

    theta = resolve_regime(regime)
    return theta.L is not None or bool(phi_by_channel(theta)) or theta.blackout is not None


def check_request(
    policies: Sequence[tuple[str, object | None]], regimes: Sequence[str], kind: str | None = None
) -> list[str]:
    """Refuse unknown names, parameters of the wrong class and unknown regimes before anything is drawn.

    Returns the run names (``policy.name``: a variant's parameters are in its name, e.g. ``mpc_det[H=L+4]`` or
    ``naive[closed_threshold=0.3]``, ``policies.base.run_name``); two entries with one run name are refused, since
    their runs could not be told apart (two entries of one parameterisation). With ``kind`` (an
    ``EPISODE_KINDS`` entry) a regime the episodes' omega cannot serve is refused too (``needs_generated_omega`` on the
    injected kind): the environment would refuse it at every reset, which is the request's error, never a policy's
    failed run.
    """
    labels = []
    for name, params in policies:  # make_policy raises ValueError or TypeError; a constructor builds nothing heavy
        labels.append(getattr(registry.make_policy(name, None, params), "name", name))
    if len(set(labels)) != len(labels):
        raise ValueError(f"two policies share a run name: {labels}")
    bad = [r for r in regimes if r not in REGIME_NAMES]
    if bad:
        raise ValueError(f"regimes {bad} are not registry names ({REGIME_NAMES})")
    if not regimes or len(set(regimes)) != len(regimes):
        raise ValueError(f"at least one regime, none twice: {list(regimes)}")
    if kind == "injected" and (bad := [r for r in regimes if needs_generated_omega(r)]):
        raise ValueError(
            f"regimes {bad} show a warning, messages or a blackout spell, which an injected omega lacks (design §12 "
            "'Resets without what a regime needs'): an injected list plays prediction_free and the coverage rungs"
        )
    return labels


def policy_provenance(policies: Sequence[tuple[str, object | None]]) -> dict[str, dict]:
    """Run name -> ``provenance`` of each policy that declares a ``seed_id`` (a kit agent, ``policies.kit_agents``).

    Its source, ``seed_id`` and the SHA-256 of each file of its zip: the seed, and so every trajectory of an agent that
    draws, follows from those bytes, so ``evaluate_keys`` records them in ``EvalResult.setup["policy_provenance"]``
    and a summary names the bytes its kit rows were played with (M5 re-gate DET-M5R-2). Empty when no policy declares a
    ``seed_id``.
    """
    out: dict[str, dict] = {}
    for name, params in policies:
        policy = registry.make_policy(name, None, params)
        if getattr(policy, "seed_id", None) is not None:
            record = getattr(policy, "provenance", None) or {"seed_id": policy.seed_id}
            out[getattr(policy, "name", name)] = copy.deepcopy(dict(record))
    return out


def episode_keys(spec: EpisodeSpec, *, entropy: int, n_jobs: int = 1) -> tuple[tuple[EpisodeKey, ...], dict]:
    """The episodes of ``spec`` in index order, and the setup that produced them (cut points included, no E_split)."""
    from sbfv.disruption.strata import cut_points

    inst, params = _resolve(spec)
    setup: dict = {"instance": inst.instance_id, "instance_hash": inst.hash, "kind": spec.kind, "split": spec.split}
    setup["instance_kind"] = inst.kind  # the reports' fixture note is `tiny`'s only (``results.fixture_note``, Q82)
    setup["entropy_sha256"] = entropy_sha256(entropy)
    if params is not None:
        setup |= {"generator": dataclasses.asdict(spec.generator), "generator_id": _generator_id(params, inst)}
        setup["fq_replications"] = spec.fq_replications
    if spec.stratified:
        cuts = cut_points(inst, params, spec.cut_draws, spec.cut_entropy, n_jobs)
        setup["cut_points"] = {"quantiles": list(cuts.quantiles), "values": list(cuts.values), "draws": cuts.draws}
        setup |= {"cut_entropy": spec.cut_entropy, "n_per_stratum": list(spec.n_per_stratum)}
        keys = fill_strata(
            inst,
            params,
            entropy,
            spec.split,
            cuts,
            spec.n_per_stratum,
            max_candidates=spec.max_candidates,
            n_jobs=n_jobs,
        )
    else:
        episodes = sorted(spec.episodes)
        keys = tuple(ordered_map(functools.partial(_plain_key, spec, inst, params, entropy), episodes, n_jobs))
        setup["episodes"] = episodes
    return tuple(sorted(keys, key=lambda k: k.episode)), setup


def _parent_inputs(spec: EpisodeSpec, policies, n_jobs: int):
    """Naive's F_Q quantiles and (when sz runs) its transient paths, computed once here (never in a worker).

    When ``sz_state_base_stock`` runs, its paths are the same stream-22 replications as F_Q, so they are drawn once:
    the quantiles come from them (``sz.fq_quantiles_from_paths``, equal to ``generator_quantiles`` bit for bit) and
    seed ``naive_fq.remember_quantiles``, which halves the parent's reset-time cost.
    """
    if spec.kind != "generated":
        return None, None
    from sbfv.policies.naive_fq import generator_quantiles, remember_quantiles

    inst, params = _resolve(spec)
    paths = None
    if any(name == "sz_state_base_stock" for name, _ in policies):
        from sbfv.policies import sz_state_base_stock as sz

        paths = sz.transient_paths(inst, params, spec.fq_replications, n_jobs)
        remember_quantiles(inst, params, spec.fq_replications, sz.fq_quantiles_from_paths(inst, paths))
    fq = generator_quantiles(inst, params, spec.fq_replications, n_jobs)  # a cache hit after remember_quantiles
    return fq, paths


def evaluate(
    spec: EpisodeSpec,
    policies: Sequence[tuple[str, object | None]],
    regimes: Sequence[str],
    *,
    entropy: int,
    n_jobs: int = 1,
    command: str = "",
    store_actions: bool = False,
    oracle_method: str = ORACLE_METHOD,
) -> EvalResult:
    """The whole evaluation over ``parallel.ordered_map``: keys, quantiles and paths in the parent, episodes in workers.

    The result is the same for any ``n_jobs`` and episode order, timings aside (V1): episodes are played in index
    order. ``EvalResult.setup`` names the split, generator, cut points, the oracle's ``oracle_method`` (§6.3; the
    entry points' ``eval.oracle_method``, M5 gate SIMP-M5-01) and E_split's SHA-256, never E_split.
    """
    policies = tuple((name, params) for name, params in policies)
    regimes = tuple(regimes)
    check_request(policies, regimes, spec.kind)
    keys, setup = episode_keys(spec, entropy=entropy, n_jobs=n_jobs)
    return evaluate_keys(
        spec,
        keys,
        setup,
        policies,
        regimes,
        entropy=entropy,
        n_jobs=n_jobs,
        command=command,
        store_actions=store_actions,
        oracle_method=oracle_method,
    )


def evaluate_keys(
    spec: EpisodeSpec,
    keys: Sequence[EpisodeKey],
    setup: Mapping[str, object],
    policies: Sequence[tuple[str, object | None]],
    regimes: Sequence[str],
    *,
    entropy: int,
    n_jobs: int = 1,
    command: str = "",
    store_actions: bool = False,
    oracle_method: str = "highs-ipm",
) -> EvalResult:
    """``evaluate`` on given keys: the quantiles and paths of ``spec`` in the parent, the episodes in workers.

    ``keys`` must be draws of ``spec`` (each worker checks omega's hash against its key); ``setup`` is the record of
    where they came from (``episode_keys``'s, or a ladder's anchor setup), extended here with the policies, regimes,
    the oracle's method and the count of episodes played. Episodes are played in index order whatever the order of
    ``keys`` (V1).
    """
    policies = tuple((name, params) for name, params in policies)
    regimes = tuple(regimes)
    labels = check_request(policies, regimes, spec.kind)
    keys = tuple(sorted(keys, key=lambda k: k.episode))
    setup = dict(setup)
    fq, paths = _parent_inputs(spec, policies, n_jobs)
    tasks = [
        EpisodeTask(spec, key, entropy, policies, regimes, fq, paths, oracle_method, store_actions) for key in keys
    ]
    results = ordered_map(run_episode_task, tasks, n_jobs)
    rows = tuple(r.row for r in results)
    runs = tuple(run for r in results for run in r.runs)
    references = tuple(ref for r in results for ref in r.references)
    failures = [f for ref in references for f in run_failures(ref)] + [f for run in runs for f in run_failures(run)]
    anchor_first = sorted(failures, key=lambda f: f.split(" ", 1)[0] not in ANCHOR_LABELS)  # stable
    exclusions = {cause: sum(r.excluded == cause for r in rows) for cause in EXCLUSION_CAUSES}
    records = tuple((p, g, r.row.episode, rec) for r in results for p, g, rec in r.records)
    setup |= {
        "policies": labels,
        "regimes": list(regimes),
        "oracle_method": oracle_method,
        "episodes_played": len(rows),
    }
    if provenance := policy_provenance(policies):
        setup["policy_provenance"] = provenance  # a kit agent's seed_id and files (DET-M5R-2)
    return EvalResult(
        rows=rows,
        runs=runs,
        exclusions=exclusions,
        v5_failures=tuple(anchor_first),
        machine=machine_record(),
        command=command,
        records=records,
        references=references,
        setup=setup,
    )


# ----- ladders: the anchor keys at other rungs, and the D-only path (M5, stream "ladders") -------------------------
def rung_keys(spec: EpisodeSpec, anchor_keys: Sequence[EpisodeKey], *, entropy: int, n_jobs: int = 1):
    """The anchor rung's keys at the rung of ``spec``: same split, indices and anchor strata (§7.4; Q88).

    Each omega is drawn at the rung (the same spawn key: the monotone coupling of §2.6 lies in the genealogical keys of
    §4.1), so each key carries the rung's omega hash, generator id and harm, and the anchor's stratum: every rung is
    weighted by the anchor strata's p_s / N_s. ``spec`` is the rung's generated spec on the keys' split.

    Raises:
        ValueError: if ``spec`` is not of the generated kind or its split is not the keys'.

    """
    if spec.kind != "generated":
        raise ValueError("a ladder rung is a generator's: rung keys need the generated kind")
    if any(k.split != spec.split for k in anchor_keys):
        raise ValueError(f"the anchor keys' split is not the rung spec's {spec.split!r}")
    inst, params = _resolve(spec)
    gid = _generator_id(params, inst)
    draw = functools.partial(_candidate, inst, params, entropy, spec.split)
    keys = sorted(anchor_keys, key=lambda k: k.episode)
    drawn = ordered_map(draw, [k.episode for k in keys], n_jobs)
    return tuple(
        EpisodeKey(k.split, k.episode, h, k.stratum, omega_hash, gid) for k, (h, omega_hash) in zip(keys, drawn)
    )


@dataclass(frozen=True)
class DTask:
    """One D-only episode for a worker: the rung's spec, the anchor key, E_split and the rung's F_Q (plain data).

    ``check_hash``: the key's omega hash is this rung's (the anchor rung: the fill drew it), so the worker checks it;
    at another rung the worker's own draw defines the hash it records.
    """

    spec: EpisodeSpec
    key: EpisodeKey
    entropy: int  # E_split of the split: trusted side only, never written out
    fq_quantile: Mapping[tuple, float]
    check_hash: bool
    oracle_method: str = "highs-ipm"


@dataclass(frozen=True)
class DRow:
    """A D-only episode: the oracle's and the anchor's J on omega (integer cents) and the anchor's V5 failures.

    ``J_oracle_cents`` is None when the oracle is not optimal (the episode is excluded, §6.3); ``oracle_solver`` is the
    method whose result is kept (highs-ds where §6.3's fallback re-solved a status-4 highs-ipm); ``v5_failures`` are the
    anchor's replay (53) and bound failures, formatted as ``EvalResult.v5_failures`` lines (a bug when not empty).
    """

    episode: int
    stratum: int | None
    omega_hash: str
    generator_id: str
    oracle_status: int
    oracle_solver: str
    oracle_seconds: float  # outside every hash
    J_oracle_cents: int | None
    J_anchor_cents: int
    anchor_sha256: str
    v5_failures: tuple[str, ...] = ()


def run_d_task(task: DTask) -> DRow:
    """One D-only episode: omega at the rung, its marks and LP (51), the oracle, and the anchor with replay (53).

    The anchor is ``run_episode_task``'s (end-aware naive with the rung's F_Q, prediction_free, the D9 fallback built
    from the task's quantiles), so on the same key its J equals ``evaluate``'s ``J_naive_cents`` bit for bit.

    Raises:
        ValueError: if ``check_hash`` and omega's hash is not the key's.
        RuntimeError: if the anchor raises (the scorer's reference: a bug, never a failed run).

    """
    from sbfv.dynamics.env import rollout
    from sbfv.marks import compute_marks
    from sbfv.oracle.lp import build_lp, solve_oracle
    from sbfv.policies.naive import NaivePolicy

    key = task.key
    inst, fq, omega, fallback, pseed, _context = _episode_inputs(task.spec, key, task.entropy, task.fq_quantile, None)
    if task.check_hash and omega.hash != key.omega_hash:
        raise ValueError(f"episode {key.episode}: omega {omega.hash[:12]}... is not the key's {key.omega_hash[:12]}...")
    marks = compute_marks(inst, omega)
    model = build_lp(inst, marks)
    oracle = solve_oracle(model, task.oracle_method)
    optimal = oracle.status == 0 and oracle.J_cents is not None
    world = _World(omega, marks, model, oracle.J_usd, optimal)

    def play(policy, w: _World, regime: str):
        return rollout(inst, policy, w.omega, regime, pseed, marks=w.marks, fallback=fallback)

    rung = str(omega["meta_generator_id"])  # the row's rung, as ``run_episode_task`` keys its runs
    anchor, _ = _run(ANCHOR, ANCHOR_REGIME, key.episode, rung, NaivePolicy(fq_quantile=fq), world, play)
    if anchor.failed is not None:
        raise RuntimeError(f"episode {key.episode}: the anchor raised: {anchor.failed}")
    return DRow(
        episode=key.episode,
        stratum=key.stratum,
        omega_hash=omega.hash,
        generator_id=str(omega["meta_generator_id"]),
        oracle_status=oracle.status,
        oracle_solver=oracle.solver,
        oracle_seconds=oracle.seconds,
        J_oracle_cents=oracle.J_cents if optimal else None,
        J_anchor_cents=anchor.J_cents,
        anchor_sha256=anchor.trajectory_sha256,
        v5_failures=run_failures(anchor),
    )


def evaluate_d(
    spec: EpisodeSpec,
    keys: Sequence[EpisodeKey],
    *,
    entropy: int,
    check_hash: bool,
    n_jobs: int = 1,
    oracle_method: str = "highs-ipm",
) -> tuple[DRow, ...]:
    """The D-only rows of ``keys`` at the rung of ``spec``, in index order: F_Q once here, episodes in workers.

    No result depends on ``n_jobs`` or the order of ``keys`` (V1).

    Raises:
        ValueError: if ``spec`` is not of the generated kind.

    """
    if spec.kind != "generated":
        raise ValueError("a ladder rung is a generator's: the D-only path needs the generated kind")
    fq, _paths = _parent_inputs(spec, (), n_jobs)
    ordered = sorted(keys, key=lambda k: k.episode)
    tasks = [DTask(spec, key, entropy, fq, check_hash, oracle_method) for key in ordered]
    return tuple(ordered_map(run_d_task, tasks, n_jobs))


# ----- the timing pass (Q13 inputs) ----------------------------------------------------------------------------------
def _timing_task(args: tuple) -> tuple[str, list[tuple[StepTimings, str]]]:
    """One (policy, regime, episode) timed in this process: a cold reset first, then ``warm`` more on the same episode.

    The process is left as a fresh policy container finds it (design §9.4; §12 row "Timings (M4 runner)"): omega comes
    in the job, drawn by the parent (a hosted episode's omega is drawn in the runner's process, never in the policy's),
    so no generator draw runs here before the timed reset; with ``cache_dir`` (the fresh pass: an empty directory made
    for this job) numba's cache is that directory (``timings.fresh_numba_cache``), as in a container whose ``/tmp`` is a
    fresh tmpfs, so a policy whose reset draws from the generator (the scenario libraries of ``mpc_scen`` and
    ``hindsight_consensus``) pays the kernels' compile inside its cold reset.

    Returns the policy's name and (timings, trajectory SHA-256) per timed episode, in order.
    """
    spec, key, entropy, name, params_obj, regime, fq, paths, warm, omega, cache_dir = args
    if cache_dir is not None:
        fresh_numba_cache(cache_dir)
    inst, _fq, omega, fallback, _pseed, context = _episode_inputs(spec, key, entropy, fq, paths, omega)
    out, label = [], name
    for _ in range(1 + warm):
        policy = registry.make_policy(name, context, params_obj)  # imports the module before the timed reset
        label = getattr(policy, "name", name)
        seed = episode_policy_seed(policy, entropy, key.split, key.episode)  # pseed unless it declares a seed_id
        traj, t = timed_rollout(inst, policy, omega, regime, seed, fallback=fallback)
        out.append((t, traj.sha256()))
    return label, out


def timing_pass(
    spec: EpisodeSpec,
    policies: Sequence[tuple[str, object | None]],
    regime: str,
    *,
    entropy: int,
    keys: Sequence[EpisodeKey],
    warm: int = 1,
    fresh: bool = True,
) -> tuple[list[tuple[str, str, StepTimings]], list[dict]]:
    """Per-step timings of each policy on ``keys``: a serial pass, cold resets apart (design §12 row "Timings").

    Each (policy, episode) runs in a fresh interpreter (``multiprocessing`` spawn, one task per process, one process at
    a time) when ``fresh``, so its first reset is cold, as a fresh policy container's (``_timing_task``): the parent
    draws each episode's omega and hands it over, and each task's numba cache is a new empty directory, removed after
    it; ``warm`` more episodes follow in the same process. Without ``fresh`` the tasks run in this process and "cold" is
    only the first timed reset of the process. A policy that raises is listed in the second value with its reason,
    never timed. The rung label is ``g<gamma>`` (or ``injected``) and the regime, e.g. ``g0.62/standard``.

    Returns:
        (policy, rung label, StepTimings) triples for ``timings.timing_table``, and the failures as dicts.

    Raises:
        ValueError: as ``check_request`` on the policies, the regime and the episode kind, before anything is drawn.

    """
    import contextlib
    import tempfile

    check_request(policies, (regime,), spec.kind)
    fq, paths = _parent_inputs(spec, policies, 1)
    inst, params = _resolve(spec)
    omegas = {key.episode: _omega(spec, inst, params, entropy, key.split, key.episode) for key in keys}
    rung = ("injected" if spec.kind == "injected" else f"g{spec.generator.gamma!r}") + f"/{regime}"
    triples, failures = [], []
    pool = None
    if fresh:
        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor

        pool = ProcessPoolExecutor(1, mp_context=multiprocessing.get_context("spawn"), max_tasks_per_child=1)
    try:
        for name, p in policies:
            for key in keys:
                with contextlib.ExitStack() as stack:
                    cache = stack.enter_context(tempfile.TemporaryDirectory(prefix="sbf-numba-")) if pool else None
                    job = (spec, key, entropy, name, p, regime, fq, paths, warm, omegas[key.episode], cache)
                    try:
                        label, timed = pool.submit(_timing_task, job).result() if pool else _timing_task(job)
                    except Exception as err:  # a stub or a crash: listed, not timed
                        failures.append({"policy": name, "episode": key.episode, "failed": _failure_text(err)})
                        continue
                triples += [(label, rung, t) for t, _sha in timed]
    finally:
        if pool is not None:
            pool.shutdown()
    return triples, failures
