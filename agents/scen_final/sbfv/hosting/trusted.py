"""The trusted runner's scoring of one submission over one split (design §7.1, §9.3-9.5; Q102).

``score_submission`` plays every scenario of the split (``split.fill_strata``) through one policy process per episode
(``TransportSpec``: a ``DockerTransport`` container, or a ``LocalShimTransport`` child for local runs on the dev split
only, since a local child can read E_split from its parent: ``hosting.docker``, INT-M4R2-01) under M3's
runner (``information.runner.play_wire_episode``) with the D9 fallback (``NaiveFallback`` with the generator's F_Q,
§9.3); on the same omega it rolls out the anchor (end-aware naive with the same F_Q, prediction-free whatever the
regime, Q10) and solves the oracle LP; then, **after the policy process is gone**, it re-simulates the policy's
trajectory from the action log and its wire failures (``runner.replay``) and requires the same integer cents (§9.4
'Scoring'; no LP is re-solved there). RSS is (55) per stratum and (56) pooled by M4's one rule
(``evaluation.results.episode_rss``; M4 re-gate ORACLE-M4R-02, SIMP-M4R2-02): an episode whose oracle on omega, or on
its event-free twin omega^0 (solved here too, cold, as M4's runner does), is not optimal is excluded for its cause
(``results.exclusion_cause``) and counted, never zero-filled (§6.3); every other episode enters both sums whatever the
sign of its D_n (§7.1). The kit's ``eval_submission.py`` applies the same function, so a local score is this one.

**Checks** (§6.2, §9.4; design §12 "Trusted scorer's checks"). The scored trajectory and the anchor's each run replay
(53) in the episode's LP (51), row evaluation without a solve, and the oracle bound in USD when the oracle is optimal,
through M4's ``evaluation.results.replay_checks`` (V5: feasible, cost-equal, J_LP in cents equal, the bound). The rule
is M4's (``results.rss_reason``): the anchor failing V5 on any episode, or the policy failing V5 or its re-simulation
on a kept episode, leaves every RSS None with the reason, never a score over the episodes that passed; every failure
is listed in ``check_failures`` and ``checks_passed`` is then False (the entry point exits 1). An excluded episode's
trajectories are still replayed, without the bound.

Per episode it records the integer cents J^pi, J^naive and J^oracle, the policy trajectory's SHA-256 (the digest an
in-process run of the same agent must reproduce), the substitutions (week, code) of §9.3, the stale lines, the entries
dropped, the checks of the policy's trajectory and of the anchor's (``checks``, ``anchor_checks``: the fields of
``results.ReplayChecks``) and the re-simulation's verdict, each week's round trip (``TimedTransport``: from the Request
written to the first line read, the transport, the shim's conversions and the agent's ``act`` together) and, for a
container, the start-up seconds and whether the container is gone. The document names E_split by its commitment only
(``split.entropy_commitment``), and a hidden root below the minimum is refused (``split.check_root``; INT-M4R2-02).
``sign_scores`` adds an HMAC-SHA256 of the canonical JSON with a key only the scorer holds (§9.4 'Scoring');
``verify_scores`` checks it.

Each episode's policy seed is ``omega.seeds.policy_seed(E_split, split, n, submission SHA-256)`` (27), per submission
so it does not identify an episode across submissions (§9.5). Each episode draws its own random episode tag and nonce
(``wire.new_token``), unlinkable to n. Logs: on the dev split the policy's stderr can be kept, runner-side, capped per
episode (``CappedLog``); on the hidden split it goes to /dev/null and a log directory is refused (§9.5 'Logs').
Episodes run over ``parallel.ordered_map`` (``n_jobs``, one container each); no result depends on it.

**Baselines on the board** (``score_baselines``): the in-package baselines (``policies.registry``) are scored over the
same split, the same scenarios (``split.fill_strata``), the same anchor, oracle and D9 fallback (``_references``, the
code the submission's episodes use) and the same ``rss_table``, in process: one document per baseline with the fields of
a submission's, ``policy`` in place of ``submission`` and transport ``in_process``, so a baseline's ``rss.pooled`` is
directly comparable to a participant's (and the same checks: its trajectory and the shared anchor's). A baseline plays
each episode with the policy seed of M4's local runs,
``policy_seed(E_split, split, n, "local")`` (``BASELINE_SEED_ID``, ``evaluation.runner.SUBMISSION``), and the context
``evaluation.runner`` gives it (F_Q, the public generator, the replication count), so its J on an episode equals
``run_eval``'s for that baseline and episode (no baseline of the board draws from its seed: ``mpc_scen`` samples its
futures from public streams, and the seed reaches only the deterministic naive fallback inside the LP baselines, so
the equality holds whatever the seed; the seed itself is checked where the rollout receives it). Its trajectory is
re-simulated from its action log like a submission's. A baseline that raises on an episode (its construction, rollout,
re-simulation or replay (53)) gets no scores document; the others keep theirs, as ``run_eval`` records a failed run and
keeps the other rows. ``board_row`` reads any scores document (a submission's or a baseline's) into one board row.

**A fill from elsewhere** (``fill=``): both scorers take the split's scenarios as ``split.fill_strata`` returns them
from the caller (the trusted runner's disk cache, ``sbf_boundary.strata_fill_cached``) instead of drawing them again;
``split.check_fill`` refuses one that does not answer ``n_per_stratum``, each scenario's stratum must be its harm's on
the cut points, and each played episode then requires the harm of its own omega to equal the scenario's, bit for bit
(0.02 s beside the 0.65 s its omega takes), so a fill of another split, generator, code or cut points cannot be scored
silently.
"""

import functools
import hmac
import json
import os
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

import sbfv
from sbfv.disruption.harm import episode_harm
from sbfv.disruption.params import GeneratorParams, generator_id
from sbfv.disruption.sampler import sample_omega
from sbfv.disruption.strata import CutPoints, stratum
from sbfv.dynamics.env import Env, rollout, took_fallback
from sbfv.evaluation.results import (
    ReplayChecks,
    episode_rss,
    exclusion_cause,
    oracle_optimal,
    replay_checks,
    rss_reason,
    substitution_counts,
    v5_problem,
)
from sbfv.hosting.docker import ContainerLimits, DockerTransport, LocalShimTransport
from sbfv.hosting.split import Scenario, check_fill, check_root, entropy_commitment, fill_strata
from sbfv.hosting.submission import Submission
from sbfv.information.runner import play_wire_episode, replay
from sbfv.information.wire import WireLimits
from sbfv.instance import load_instance
from sbfv.instance.schema import Instance
from sbfv.marks import compute_marks
from sbfv.omega.injected import event_free
from sbfv.omega.seeds import policy_seed
from sbfv.oracle.lp import build_lp, solve_oracle
from sbfv.parallel import ordered_map
from sbfv.policies.naive import NaiveFallback, NaivePolicy
from sbfv.scoring.rss import STRATUM_WEIGHTS


# 2: the checks of replay (53) and the bound, and M4's rule on them (ORACLE-M4-01); 3: entropy_commitment in place of
# entropy_sha256 (INT-M4R2-02), and the omega^0 oracle's exclusion with each episode's cause (ORACLE-M4R-02)
SCHEMA = "sbf-scores/3"
ANCHOR_REGIME = "prediction_free"  # the anchor of (55) plays prediction-free whatever the policy plays (Q10)
RESIMULATION_DIFFERS = "the re-simulation from the action log differs from the played trajectory (§9.4 'Scoring')"
TRANSPORTS = ("docker", "subprocess")
IN_PROCESS = "in_process"  # the transport kind of a baseline's document (``score_baselines``)
BASELINE_SEED_ID = "local"  # a baseline's submission id in the policy seed (27): M4's local runs' (runner.SUBMISSION)
FAILURE_CHARS = 500  # characters of a failed baseline's error text kept (as evaluation.runner's; not a model value)
RUNNER_SLACK_S = 5.0  # per week, the runner's own work in the watchdog's bound (not a model value)
TRUNCATED = b"\n[log truncated]\n"


@dataclass(frozen=True)
class TransportSpec:
    """How each episode's policy process is started, and the wire's limits (the hosted ones: ``hosting.limits``)."""

    kind: str  # "docker" or "subprocess"
    deadline_s: float
    startup_s: float
    max_reply_bytes: int
    bank_seconds: float
    image: str | None = None  # docker: the image ID the runner pins
    limits: ContainerLimits = field(default_factory=ContainerLimits)
    docker: tuple[str, ...] = ("docker",)
    shim_module: str | None = None  # subprocess: the kit's shim, and the directories that hold it
    kit_path: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Refuse an unknown kind, or a kind without what it needs.

        Raises:
            ValueError: on a kind outside ``TRANSPORTS``, docker without an image, subprocess without a shim module.

        """
        if self.kind not in TRANSPORTS:
            raise ValueError(f"transport must be one of {TRANSPORTS}, got {self.kind!r}")
        if self.kind == "docker" and not self.image:
            raise ValueError("the docker transport needs the policy image")
        if self.kind == "subprocess" and not self.shim_module:
            raise ValueError("the subprocess transport needs the kit's shim module")


class CappedLog:
    """A write end for a policy's stderr whose bytes go to ``path`` up to ``cap``, then ``TRUNCATED``, then nowhere."""

    def __init__(self, path: str | Path, cap: int) -> None:
        self.path, self.cap = Path(path), int(cap)
        read, self.fd = os.pipe()
        self._thread = threading.Thread(target=self._pump, args=(read,), daemon=True)
        self._thread.start()

    def _pump(self, read: int) -> None:
        kept = 0
        with open(self.path, "wb") as out:
            while data := os.read(read, 1 << 16):
                if kept < self.cap:
                    out.write(data[: self.cap - kept])
                    kept += min(len(data), self.cap - kept)
                    if kept >= self.cap:
                        out.write(TRUNCATED)
        os.close(read)

    def close(self) -> None:
        """Close the runner's copy of the write end and wait for the pump (the child's copies close as it exits)."""
        os.close(self.fd)
        self._thread.join(timeout=30)


def _transport(spec: TransportSpec, submission_dir: Path, stderr: int | None, T: int):
    if spec.kind == "docker":
        return DockerTransport(
            spec.image,
            submission_dir,
            deadline_s=spec.deadline_s,
            startup_s=spec.startup_s,
            max_reply_bytes=spec.max_reply_bytes,
            limits=spec.limits,
            docker=spec.docker,
            stderr=subprocess.DEVNULL if stderr is None else stderr,
            episode_timeout_s=2 * spec.startup_s + T * (spec.deadline_s + RUNNER_SLACK_S),
            labels={"sbf.role": "policy"},
        )
    return LocalShimTransport(
        submission_dir,
        shim_module=spec.shim_module,
        kit_path=spec.kit_path,
        deadline_s=spec.deadline_s,
        startup_s=spec.startup_s,
        max_reply_bytes=spec.max_reply_bytes,
        stderr=subprocess.DEVNULL if stderr is None else stderr,
    )


@dataclass(frozen=True)
class _Task:
    instance_ref: str | Path
    instance_hash: str
    params: GeneratorParams
    entropy: int
    split: str
    regime: str
    submission_dir: Path
    submission_sha256: str
    quantiles: Mapping
    transport: TransportSpec
    log_dir: Path | None
    log_cap_bytes: int
    check_harm: bool = False  # the fill came from the caller: each episode re-derives its harm (module docstring)


class TimedTransport:
    """A transport whose weeks are timed: ``round_trip_s`` from each Request written to the first line read after it.

    The first line sent is the Reset, which gets no reply and is not timed; a week whose reply never came (a deadline
    or a closed channel) records nothing. Everything else is the wrapped transport's.
    """

    def __init__(self, inner) -> None:
        self.inner = inner
        self.round_trip_s: list[float] = []
        self._sent = 0
        self._t0: float | None = None

    def send(self, line: bytes) -> int:
        n = self.inner.send(line)
        self._sent += 1
        self._t0 = time.perf_counter() if self._sent > 1 else None
        return n

    def receive(self):
        r = self.inner.receive()
        if self._t0 is not None and r.kind == "line":
            self.round_trip_s.append(time.perf_counter() - self._t0)
            self._t0 = None
        return r

    def drain(self) -> int:
        return self.inner.drain()

    def kill(self) -> None:
        self.inner.kill()

    def close(self) -> None:
        self.inner.close()

    def summary(self) -> dict:
        """{weeks, median, max, sum} of the timed round trips in seconds (None values when no week was timed)."""
        rt = sorted(self.round_trip_s)
        if not rt:
            return {"weeks": 0, "median": None, "max": None, "sum": 0.0}
        mid = len(rt) // 2
        median = rt[mid] if len(rt) % 2 else (rt[mid - 1] + rt[mid]) / 2
        return {"weeks": len(rt), "median": median, "max": rt[-1], "sum": sum(rt)}


@dataclass(frozen=True)
class _References:
    """A scenario's omega, marks, LP, D9 fallback, anchor trajectory and checks, and oracles (``_references``)."""

    omega: object
    marks: object
    fallback: NaiveFallback
    anchor: object  # the anchor's Trajectory
    oracle: object  # the oracle's OracleResult
    optimal: bool
    model: object  # the LP (51) of omega's marks: the oracle's, and the rows replay (53) evaluates
    anchor_checks: ReplayChecks  # V5 of the anchor's trajectory (M4 checks its references too)
    oracle0: object  # the oracle's OracleResult on omega^0, the event-free twin (§6.3, (57))
    excluded: str | None  # results.exclusion_cause of the two solves: the episode's §6.3 exclusion, or None

    def record(self) -> dict:
        """The reference fields of an episode record: J^naive, the oracles' cents, statuses and solvers, the exclusion.

        A solver is the linprog method whose result is kept (``OracleResult.solver``): highs-ds where §6.3's fallback
        re-solved a status-4 highs-ipm, so an exclusion's cause is its status and solver.
        """
        return {
            "J_naive_cents": self.anchor.J_cents,
            "J_oracle_cents": self.oracle.J_cents if self.optimal else None,
            "oracle_status": self.oracle.status,
            "oracle_solver": self.oracle.solver,
            "J_oracle0_cents": self.oracle0.J_cents if oracle_optimal(self.oracle0) else None,
            "oracle0_status": self.oracle0.status,
            "oracle0_solver": self.oracle0.solver,
            "excluded": self.excluded,
        }


def _checks_record(checks: ReplayChecks) -> dict:
    """``ReplayChecks`` as scores.json records it (plain JSON)."""
    return {**asdict(checks), "worst_row": list(checks.worst_row)}


def _checked(ref: _References, traj, again) -> dict:
    """One scored trajectory's checks: its V5 (M4's ``replay_checks``), the anchor's V5, and the re-simulation.

    V5 is replay (53) in the episode's LP and the oracle bound; ``again`` is the trajectory re-simulated from the action
    log (§9.4 'Scoring'), which must equal ``traj``.

    Raises:
        ValueError: where replay (53) does (an unfinished trajectory, or one of another instance, omega or marks).

    """
    return {
        "checks": _checks_record(replay_checks(ref.model, traj, ref.oracle.J_usd, ref.optimal)),
        "anchor_checks": _checks_record(ref.anchor_checks),
        "rescored_equal": again.sha256() == traj.sha256() and again.J_cents == traj.J_cents,
    }


def _v5(record: Mapping) -> tuple[str, ...]:
    """The V5 failures of a recorded ``checks`` or ``anchor_checks`` (``ReplayChecks.failures``, M4's texts)."""
    return ReplayChecks(**record).failures


def check_failures(episodes: Sequence[Mapping]) -> list[str]:
    """Every failed check of the episodes: the anchor's first ("anchor ep<n>: ..."), then the policy's ("ep<n>: ...").

    A policy's lines are its V5 failures (replay (53), J_LP in cents, the oracle bound) and a re-simulation that
    differs; a bound not checked (the oracle not optimal) is not a failure.
    """
    anchor = [f"anchor ep{e['episode']}: {f}" for e in episodes for f in _v5(e["anchor_checks"])]
    policy = [
        f"ep{e['episode']}: {f}"
        for e in episodes
        for f in (*_v5(e["checks"]), *(() if e["rescored_equal"] else (RESIMULATION_DIFFERS,)))
    ]
    return anchor + policy


def _unscored(episodes: Sequence[Mapping], kept: Sequence[Mapping]) -> str | None:
    """Why the document has no RSS (M4's rule, ``results.rss_reason``), or None (module docstring, 'Checks')."""
    problems = []
    for e in kept:
        if v5 := _v5(e["checks"]):
            problems.append(v5_problem(e["episode"], v5))
        if not e["rescored_equal"]:
            problems.append(f"ep{e['episode']}: {RESIMULATION_DIFFERS}")
    return rss_reason(any(_v5(e["anchor_checks"]) for e in episodes), problems)


def _load(task) -> Instance:
    """The task's instance at its generator's rung (``Instance.at_rung``: that rung's warm start, §2.3; M5-O37 (b))."""
    inst = load_instance(task.instance_ref)
    if inst.hash != task.instance_hash:
        raise ValueError("the worker loaded another instance than the runner's")
    return inst.at_rung(task.params.hawkes.gamma)


def _references(inst: Instance, task, scenario: Scenario, pseed: int) -> _References:
    """Omega_n of the split, its marks and D9 fallback, the anchor (prediction-free, Q10), the oracle LP, anchor V5.

    The one code both a submission's episodes (``play_episode``) and the baselines' (``play_baselines``) are scored
    against: ``task`` carries the instance hash, generator parameters, E_split, split and F_Q quantiles. With
    ``task.check_harm`` (a fill from the caller) omega's harm (42) must equal the scenario's. The anchor's trajectory
    is replayed (53) in the oracle's own LP, with the bound when the oracle is optimal (M4's references). The oracle
    also solves omega^0 (``omega.injected.event_free``), cold, for the exclusion rule M4's runner applies.

    Raises:
        ValueError: on a harm that differs (the fill is not this split's, generator's or code's).

    """
    n = scenario.episode
    omega = sample_omega(inst, task.params, task.entropy, n, task.split)
    if task.check_harm and episode_harm(inst, omega, task.params.marks) != scenario.harm:
        raise ValueError(
            f"episode {n}: the harm of its omega differs from the given fill's; the fill is not of this split, "
            "generator or code (clear the strata-fill cache)"
        )
    marks = compute_marks(inst, omega)
    fallback = NaiveFallback(omega.generator_id, task.quantiles, instance_digest=inst.family_digest)
    anchor = rollout(
        inst, NaivePolicy(fq_quantile=task.quantiles), omega, ANCHOR_REGIME, pseed, marks=marks, fallback=fallback
    )
    model = build_lp(inst, marks)
    oracle = solve_oracle(model)
    optimal = oracle_optimal(oracle)
    checks = replay_checks(model, anchor, oracle.J_usd, optimal)
    oracle0 = solve_oracle(build_lp(inst, compute_marks(inst, event_free(omega, inst))))
    return _References(omega, marks, fallback, anchor, oracle, optimal, model, checks, oracle0,
                       exclusion_cause(oracle, oracle0))  # fmt: skip


def play_episode(task: _Task, scenario: Scenario) -> dict:
    """One scenario: the anchor, the oracle, the policy over its transport, the re-simulation and the checks.

    As the module docstring says ('Checks').
    """
    start = time.perf_counter()
    inst = _load(task)
    n = scenario.episode
    pseed = policy_seed(task.entropy, task.split, n, task.submission_sha256)
    ref = _references(inst, task, scenario, pseed)
    omega, marks, fallback = ref.omega, ref.marks, ref.fallback
    log = None
    if task.log_dir is not None:
        log = CappedLog(task.log_dir / f"ep{n}.stderr", task.log_cap_bytes)
    try:
        transport = _transport(task.transport, task.submission_dir, None if log is None else log.fd, inst.T)
    except BaseException:
        if log is not None:
            log.close()
        raise
    timed = TimedTransport(transport)
    try:
        limits = WireLimits(max_reply_bytes=task.transport.max_reply_bytes, bank_seconds=task.transport.bank_seconds)
        wired = play_wire_episode(
            Env(fallback=fallback),
            inst,
            timed,
            limits=limits,
            regime=task.regime,
            omega=omega,
            policy_seed=pseed,
            marks=marks,
            policy_name="submission",
        )
    finally:
        if log is not None:
            log.close()
    traj = wired.trajectory
    # §9.4 'Scoring': the policy process is gone; re-simulate from the action log and the wire failures, to the cent
    again = replay(Env(fallback=fallback), inst, traj, regime=task.regime, omega=omega, policy_seed=pseed, marks=marks)
    return {
        "episode": n,
        "stratum": scenario.stratum,
        "harm_usd": scenario.harm,
        "J_policy_cents": traj.J_cents,
        "trajectory_sha256": traj.sha256(),
        **ref.record(),
        "substitutions": [list(s) for s in wired.substitutions],
        "stale": [list(s) for s in wired.stale],
        "invalid_entries": substitution_counts(traj)[0],
        **_checked(ref, traj, again),  # §6.2: replay (53) and the bound on every scored trajectory, and the anchor's
        "round_trip_s": timed.summary(),
        "ready_s": getattr(transport, "ready_s", None),
        "container_gone": getattr(transport, "container_gone", None),
        "watchdog_fired": getattr(transport, "watchdog_fired", None),
        "wall_s": time.perf_counter() - start,
    }


def rss_table(episodes: Sequence[Mapping], weights: Sequence[float] = STRATUM_WEIGHTS) -> dict:
    """(55) per stratum and (56) pooled by M4's one rule (``results.episode_rss``); None with the reason otherwise.

    An episode ``excluded`` for its oracle on omega or omega^0 (``results.exclusion_cause``) is dropped; every other
    one is kept whatever the sign of its D_n. A failed check (module docstring, 'Checks': the anchor's V5 on any
    episode, the policy's V5 or re-simulation on a kept one) leaves every RSS None with M4's reason
    (``results.rss_reason``). Each episode must carry its ``excluded``, ``checks``, ``anchor_checks`` and
    ``rescored_equal`` (KeyError otherwise: an unchecked episode is never scored).
    """
    kept = [e for e in episodes if e["excluded"] is None]
    return episode_rss(episodes, weights, reason=_unscored(episodes, kept))


def score_submission(
    inst: Instance,
    params: GeneratorParams,
    *,
    submission_dir: str | Path,
    submission: Submission,
    split: str,
    entropy: int,
    regime: str,
    cuts: CutPoints,
    n_per_stratum: Sequence[int],
    quantiles: Mapping,
    replications: int,
    transport: TransportSpec,
    instance_ref: str | Path | None = None,
    max_candidates: int = 10_000,
    n_jobs: int = 1,
    harm_jobs: int = 1,
    harm_of: Callable | None = None,
    log_dir: str | Path | None = None,
    log_cap_bytes: int = 1 << 20,
    fill: tuple | None = None,
) -> dict:
    """The scores document of one submission over one split (module docstring); unsigned (``sign_scores``).

    ``quantiles`` are naive's F_Q quantiles of ``params`` from ``replications`` replications (the anchor's and the
    fallback's); ``instance_ref`` is what workers load (default ``inst.instance_id``'s packaged name, ``tiny``).
    ``fill``: the split's scenarios from the caller (module docstring, 'A fill from elsewhere'), else drawn here.

    Raises:
        ValueError: on a split other than dev with a transport other than ``docker`` (a local child can read E_split
            from its parent: ``hosting.docker``, 'The scorer's secrets and local runs'), on the hidden split with a
            ``log_dir`` (scored runs keep no policy output), on cut points of another generator, where
            ``split.fill_strata`` or ``split.check_fill`` raises, on a given fill whose harm differs from an
            episode's omega, or on a hidden root below the minimum (``split.check_root``).

    """
    if split != "dev" and transport.kind != "docker":
        raise ValueError(
            f"the {split} split is scored only in the policy container (transport docker, §9.4 'Policy isolation'): "
            f"a {transport.kind} child runs with this process's uid and can read E_split from its environment"
        )
    if split == "hidden" and log_dir is not None:
        raise ValueError("the hidden split keeps no policy output (§9.5 'Logs'): log_dir must be None")
    check_root(split, entropy)
    scenarios, drawn, unfilled = _fill(
        inst, params, entropy, split, cuts, n_per_stratum, fill, max_candidates=max_candidates, n_jobs=harm_jobs,
        harm_of=harm_of,
    )  # fmt: skip
    if log_dir is not None:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
    task = _Task(
        instance_ref=instance_ref or inst.kind,
        instance_hash=inst.hash,
        params=params,
        entropy=entropy,
        split=split,
        regime=regime,
        submission_dir=Path(submission_dir).resolve(),
        submission_sha256=submission.sha256,
        quantiles=dict(quantiles),
        transport=transport,
        log_dir=None if log_dir is None else Path(log_dir).resolve(),
        log_cap_bytes=int(log_cap_bytes),
        check_harm=fill is not None,
    )
    episodes = ordered_map(functools.partial(play_episode, task), scenarios, n_jobs)
    spec = asdict(transport)
    head = {
        "image": None if transport.kind != "docker" else transport.image,
        "transport": {k: spec[k] for k in ("kind", "deadline_s", "startup_s", "max_reply_bytes", "bank_seconds")}
        | ({"limits": spec["limits"]} if transport.kind == "docker" else {"shim_module": transport.shim_module}),
        "submission": {
            "sha256": submission.sha256,
            "zip_bytes": submission.zip_bytes,
            "unpacked_bytes": submission.total_bytes,
            "files": len(submission.files),
        },
    }
    filled = (n_per_stratum, drawn, unfilled)
    return _document(head, inst, params, split, entropy, regime, replications, cuts, filled, episodes)


def _fill(
    inst: Instance,
    params: GeneratorParams,
    entropy: int,
    split: str,
    cuts: CutPoints,
    n_per_stratum: Sequence[int],
    fill: tuple | None,
    **kw,
) -> tuple[tuple[Scenario, ...], int, tuple[int, ...]]:
    """The split's scenarios: ``fill`` checked (``split.check_fill``) when the caller gives one, else ``fill_strata``.

    A given fill's strata must also be its harms' on ``cuts`` (44), so a fill made on other cut points, whose harms the
    played episodes would confirm, is not scored in the wrong strata.

    Raises:
        ValueError: on cut points of another generator (either way), on a given scenario whose stratum is not its harm's
            on ``cuts``, and where ``check_fill`` or ``fill_strata`` does.

    """
    if fill is None:
        return fill_strata(inst, params, entropy, split, cuts, n_per_stratum, **kw)
    if cuts.generator_id != generator_id(params, inst):
        raise ValueError(f"cut points of generator {cuts.generator_id[:12]}... cannot stratify this generator (44)")
    checked = check_fill(fill, n_per_stratum)
    for s in checked[0]:
        if stratum(s.harm, cuts, generator_id=cuts.generator_id) != s.stratum:
            raise ValueError(f"episode {s.episode}: stratum {s.stratum} is not its harm's on these cut points (44)")
    return checked


def _document(
    head: Mapping,
    inst: Instance,
    params: GeneratorParams,
    split: str,
    entropy: int,
    regime: str,
    replications: int,
    cuts: CutPoints,
    fill: tuple,
    episodes: Sequence[Mapping],
) -> dict:
    """A scores document: ``head`` (who played, how), the split, the fill, the checks, the RSS table, the episodes."""
    n_per_stratum, drawn, unfilled = fill
    excluded = [
        {"episode": e["episode"], "cause": e["excluded"], "oracle_status": e["oracle_status"],
         "oracle_solver": e["oracle_solver"], "oracle0_status": e["oracle0_status"],
         "oracle0_solver": e["oracle0_solver"]}
        for e in episodes
        if e["excluded"] is not None
    ]  # fmt: skip
    failures = check_failures(episodes)
    return {
        "schema": SCHEMA,
        "package_version": sbfv.__version__,
        **head,
        "split": split,
        "entropy_commitment": entropy_commitment(split, entropy),  # never the root nor its plain hash (INT-M4R2-02)
        "instance": inst.instance_id,
        "instance_hash": inst.hash,
        "generator_id": generator_id(params, inst),
        "regime": regime,
        "anchor_regime": ANCHOR_REGIME,
        "fq_replications": replications,
        "cut_points": {"draws": cuts.draws, "quantiles": list(cuts.quantiles), "values_usd": list(cuts.values)},
        "n_per_stratum": list(n_per_stratum),
        "candidates_drawn": drawn,
        "unfilled_strata": list(unfilled),
        "scenario_count": len(episodes),
        "excluded": excluded,
        "substitutions_total": sum(len(e["substitutions"]) for e in episodes),
        "rescored_all_equal": all(e["rescored_equal"] for e in episodes),
        "checks_passed": not failures,  # every replay (53), bound and re-simulation, the anchor's included
        "anchor_failed": any(_v5(e["anchor_checks"]) for e in episodes),
        "check_failures": failures,
        "rss": rss_table(episodes),
        "episodes": list(episodes),
    }


# ----- the in-package baselines on the board (module docstring, 'Baselines on the board') ----------------------------
@dataclass(frozen=True)
class _BaselineTask:
    instance_ref: str | Path
    instance_hash: str
    params: GeneratorParams
    entropy: int
    split: str
    regime: str
    quantiles: Mapping
    replications: int
    generator: object  # policies.registry.GeneratorRef: the public profile and rung the scenario baselines read
    policies: tuple[tuple[str, object | None], ...]  # (registry name, its parameter dataclass or None)
    transient_paths: Mapping | None = None  # sz_state_base_stock's paths, computed once in the parent
    check_harm: bool = False  # the fill came from the caller: each episode re-derives its harm (module docstring)


def baseline_label(name: str, params: object | None = None) -> str:
    """A baseline's run name, as ``run_eval`` reports it (``mpc_det``, ``mpc_det[H=L+4]``); refuses unknown names.

    Raises:
        ValueError, TypeError: as ``policies.registry.make_policy``.

    """
    from sbfv.policies.registry import make_policy

    return getattr(make_policy(name, None, params), "name", name)


def play_baselines(task: _BaselineTask, scenario: Scenario) -> list[dict]:
    """One scenario's references, then each baseline in process with its re-simulation and checks: one record each.

    The records have a submission episode's fields (``play_episode``) where they apply, the checks included; a week
    the D9 fallback played is the substitution ``[week, "action"]``, the code the wire gives a null or invalid action.
    ``wall_s`` is the shared references' seconds plus the baseline's own (``policy_s``), so it compares with a
    submission's. A baseline that raises (built, played, re-simulated or replayed (53)) gets
    ``{"episode": n, "failed": "<type>: <message>"}`` instead, and the next baseline still plays.
    """
    from sbfv.policies.naive_fq import remember_quantiles
    from sbfv.policies.registry import PolicyContext, make_policy

    start = time.perf_counter()
    inst = _load(task)
    n = scenario.episode
    pseed = policy_seed(task.entropy, task.split, n, BASELINE_SEED_ID)
    ref = _references(inst, task, scenario, pseed)
    # the parent's F_Q (and sz's paths) enter this process's caches, never recomputed here (evaluation.runner)
    remember_quantiles(inst, task.params, task.replications, dict(task.quantiles))
    if task.transient_paths is not None:
        from sbfv.policies import sz_state_base_stock as sz

        sz.remember_paths(inst, task.params, task.replications, task.transient_paths)
    context = PolicyContext(fq_quantile=task.quantiles, generator=task.generator, fq_replications=task.replications)
    shared_s = time.perf_counter() - start
    out = []
    for name, params in task.policies:
        t0 = time.perf_counter()
        try:
            policy = make_policy(name, context, params)
            traj = rollout(inst, policy, ref.omega, task.regime, pseed, marks=ref.marks, fallback=ref.fallback)
            again = replay(
                Env(fallback=ref.fallback), inst, traj, regime=task.regime, omega=ref.omega, policy_seed=pseed,
                marks=ref.marks,
            )  # fmt: skip
            checked = _checked(ref, traj, again)
        except Exception as err:  # noqa: BLE001 - a baseline's failure: recorded, the other baselines play (run_eval's)
            text = f"{type(err).__name__}: {err}"
            out.append({"episode": n, "failed": text[:FAILURE_CHARS]})
            continue
        policy_s = time.perf_counter() - t0
        out.append(
            {
                "episode": n,
                "stratum": scenario.stratum,
                "harm_usd": scenario.harm,
                "J_policy_cents": traj.J_cents,
                "trajectory_sha256": traj.sha256(),
                **ref.record(),
                "substitutions": [[w, "action"] for w, r in enumerate(traj.records, start=1) if took_fallback(r)],
                "stale": [],
                "invalid_entries": substitution_counts(traj)[0],
                **checked,
                "policy_s": policy_s,
                "wall_s": shared_s + policy_s,
            }
        )
    return out


def score_baselines(
    inst: Instance,
    params: GeneratorParams,
    *,
    generator,
    policies: Sequence[tuple[str, object | None]],
    split: str,
    entropy: int,
    regime: str,
    cuts: CutPoints,
    n_per_stratum: Sequence[int],
    quantiles: Mapping,
    replications: int,
    instance_ref: str | Path | None = None,
    max_candidates: int = 10_000,
    n_jobs: int = 1,
    harm_jobs: int = 1,
    harm_of: Callable | None = None,
    fill: tuple | None = None,
) -> dict[str, dict]:
    """One scores document per baseline over one split, in process (module docstring), keyed by its run name.

    ``generator`` is the split's public ``policies.registry.GeneratorRef`` (its ``params(inst)`` must be ``params``);
    ``policies`` are (registry name, parameter dataclass or None) pairs. Every baseline plays the scenarios
    ``score_submission`` would play with the same arguments, against the same anchor, oracle and fallback, and each
    document's ``rss`` is ``rss_table`` of its episodes. The documents are unsigned (``sign_scores``). A baseline that
    raised on any episode has no document: its value is ``{"policy": {...}, "failed": [{"episode", "error"}, ...]}``
    (``failed_baseline``), and every other baseline's document is as if it had played alone. ``fill`` as
    ``score_submission``'s.

    Raises:
        ValueError: on no baselines or two with one run name, a ``generator`` whose parameters are not ``params``, and
            where ``split.fill_strata``, ``split.check_fill`` or ``policies.registry.make_policy`` raises (TypeError
            for parameters of the wrong class), or on a given fill whose harm differs from an episode's omega.

    """
    check_root(split, entropy)
    policies = tuple((name, p) for name, p in policies)
    labels = [baseline_label(name, p) for name, p in policies]
    if not labels or len(set(labels)) != len(labels):
        raise ValueError(f"at least one baseline, no run name twice: {labels}")
    if generator_id(generator.params(inst), inst) != generator_id(params, inst):
        raise ValueError("the baselines' public generator is not the split's (generator.params(inst) != params)")
    scenarios, drawn, unfilled = _fill(
        inst, params, entropy, split, cuts, n_per_stratum, fill, max_candidates=max_candidates, n_jobs=harm_jobs,
        harm_of=harm_of,
    )  # fmt: skip
    paths = None
    if any(name == "sz_state_base_stock" for name, _ in policies):
        from sbfv.policies import sz_state_base_stock as sz

        paths = sz.transient_paths(inst, params, replications, harm_jobs)
    task = _BaselineTask(
        instance_ref=instance_ref or inst.kind,
        instance_hash=inst.hash,
        params=params,
        entropy=entropy,
        split=split,
        regime=regime,
        quantiles=dict(quantiles),
        replications=replications,
        generator=generator,
        policies=policies,
        transient_paths=paths,
        check_harm=fill is not None,
    )
    per_episode = ordered_map(functools.partial(play_baselines, task), scenarios, n_jobs)
    filled = (n_per_stratum, drawn, unfilled)
    docs = {}
    for i, ((name, p), label) in enumerate(zip(policies, labels)):
        head = {
            "image": None,
            "transport": {"kind": IN_PROCESS},
            "policy": {
                "name": label,
                "registry_name": name,
                "params": None if p is None else asdict(p),
                "seed_id": BASELINE_SEED_ID,
            },
        }
        episodes = [records[i] for records in per_episode]
        failed = [{"episode": e["episode"], "error": e["failed"]} for e in episodes if "failed" in e]
        if failed:
            docs[label] = {"policy": head["policy"], "failed": failed}
            continue
        docs[label] = _document(head, inst, params, split, entropy, regime, replications, cuts, filled, episodes)
    return docs


def failed_baseline(doc: Mapping) -> bool:
    """Whether a value of ``score_baselines`` is a failed baseline's (``failed``), not a scores document."""
    return "failed" in doc


def board_row(doc: Mapping) -> dict:
    """One board row of a scores document, a submission's or a baseline's.

    RSS (56) pooled and (55) per stratum, the episodes whose J^pi is below, equal to and above J^naive (every episode
    played, excluded ones included), the D9 weeks (``substitutions_total``), the policy's name (a baseline's) or the
    submission's SHA-256, whether every re-simulation matched and whether every check passed (``checks_passed``: None
    for a document of schema ``sbf-scores/1``, which predates the checks and is read for analysis only).
    """
    eps = doc["episodes"]
    who = doc["policy"]["name"] if "policy" in doc else doc["submission"]["sha256"]
    return {
        "who": who,
        "transport": doc["transport"]["kind"],
        "rss_pooled": doc["rss"]["pooled"],
        "rss_strata": {s: v["rss"] for s, v in doc["rss"]["strata"].items()},
        "n_strata": {s: v["n"] for s, v in doc["rss"]["strata"].items()},
        "won": sum(e["J_policy_cents"] < e["J_naive_cents"] for e in eps),
        "tied": sum(e["J_policy_cents"] == e["J_naive_cents"] for e in eps),
        "lost": sum(e["J_policy_cents"] > e["J_naive_cents"] for e in eps),
        "episodes": len(eps),
        "d9_weeks": doc["substitutions_total"],
        "excluded": len(doc["excluded"]),
        "rescored_all_equal": doc["rescored_all_equal"],
        "checks_passed": doc["checks_passed"] if doc.get("schema") != "sbf-scores/1" else None,
    }


def _canonical(doc: Mapping) -> bytes:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sign_scores(doc: Mapping, key: bytes) -> dict:
    """``doc`` with ``signature`` = HMAC-SHA256 over the canonical JSON of everything else (§9.4 'Scoring')."""
    body = {k: v for k, v in doc.items() if k != "signature"}
    return {**body, "signature": {"alg": "hmac-sha256", "value": hmac.new(key, _canonical(body), "sha256").hexdigest()}}


def verify_scores(doc: Mapping, key: bytes) -> bool:
    """Whether ``doc``'s signature is the HMAC of its body under ``key``."""
    sig = doc.get("signature") or {}
    body = {k: v for k, v in doc.items() if k != "signature"}
    want = hmac.new(key, _canonical(body), "sha256").hexdigest()
    return sig.get("alg") == "hmac-sha256" and hmac.compare_digest(str(sig.get("value", "")), want)
