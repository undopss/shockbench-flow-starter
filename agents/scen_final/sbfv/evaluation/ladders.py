"""The ladder checks of design §2.6 and §7.4 (milestone M5, stream "ladders"): (64), (73), F-knob and F-size.

Readings the design leaves open are in docs/owner-queue.md (2026-09-28, M5); each is built at its recommended default,
kept in one named constant below with the question id beside it, so an answer is a one-line change. The builder-level
readings that follow from the design are the design §12 rows under "M5 stream ladders".

- **(64)**: delta_r = sum_s p_s D-bar_{s,r} / (T sum_{i in V^snk, k} d-bar_ik), the oracle's saving per unit of sink
  demand and week at rung r (D_n = J^anchor_n - J^oracle_n of (57), integer cents), exact in fractions, one float.
- **(73)**: loss_r = sum_s p_s J-bar^oracle_{s,r} / (T sum d-bar_ik), the loss even the oracle cannot avoid, by
  (64)'s arithmetic on J^oracle: the γ ladder's gated measure (M5-O3's second branch, taken by Q114's addendum after
  the re-measure on V3; design §7.4, §12 row "Gated γ ladder (Q114 addendum)"), which the committed experiment files
  select (``experiment.measure: loss``). A ladder that names no measure gates ``MEASURE`` ("delta", (64)); under
  "loss" the pairing on the anchor keys and strata, delta_min, the sign flip (61) and Holm are the same, on J^oracle
  in place of D, and delta_r is reported beside loss_r.
- **Reported rungs** (Q114's addendum): ``LadderSpec.reported``, the tail of the rung list, is played on the same keys
  and reported (each rung's row and its test against the rung below, raw p), never in F-knob: γ 0.97 on the committed
  γ ladders.
- **Difficulty ladder** (§7.4, Q88; family F-knob): one set of spawn keys per size, stratified once on the anchor
  rung's harm quantiles (γ 0.62) and filled to N_s per stratum; every rung is played on those keys through the
  monotone coupling of §2.6 and weighted by the anchor strata's p_s / N_s; the one-sided sign flip (61) on
  D_{n,r+1} - (1 + delta_min) D_{n,r}, flipped within the anchor strata, Holm over each knob's gated rungs - 1
  tests. With delta_min = num / den exact, the paired difference is the integer den D_{n,r+1} - (den + num) D_{n,r},
  a positive multiple of the design's, so (61)'s exact integer arithmetic (``scoring.inference.sign_flip``, exact at
  any magnitude) carries over. A rung passes only if H0 is rejected. It needs D alone (the oracle and the anchor on
  omega), never omega^0: the D-only path of ``evaluation.runner`` (``evaluate_d``). Adjacent rungs are consecutive in
  ``LadderSpec.rungs`` (anchor first, in increasing difficulty: γ's in ``params.RUNGS`` order,
  ``check_rung_order``; M5 re-gate SPEC-M5R-04). A gated ladder (``is_gated``: `small` or `full`, a gated rung above
  the anchor) plays adjacent rungs of ``RUNGS`` only, refused before any draw on a gap (``check_no_gap``; §7.4 "Gated
  ladders", the owner's answer of 2026-09-29, "Refuse on gated"). An episode whose oracle is not optimal at a gated
  rung leaves every rung; one not optimal only at a reported rung leaves that rung's row and test only
  (``gated_exclusions``; M5 gate ACC-M5-06).
- **Size ladder** (§2.6, §7.4): reported, not gated (the owner's answer of 2026-09-29, "Report it, don't gate
  (Recommended)", Q114's superseding note; it supersedes "Unavoidable loss, like γ" for the size ladder only). Sizes
  share no omega, so each measure of ``SIZE_MEASURES`` (loss of (73) and delta of (64)) is compared unpaired by a
  one-sided stratified two-sample permutation test, relabelling scenarios within each harm stratum (cut per size, same
  p_s), B = 20,000, each test reported at its raw p with no Holm, no family and no verdict. M5-O5 (5) default: the
  shifted null m_upper <= (1 + delta_min) m_lower scales the lower size's
  normalised values by 1 + delta_min, and the statistic is studentised, sum_s p_s (x-bar_s - y-bar_s) over
  sqrt(sum_s p_s^2 (s_x,s^2 / n_x,s + s_y,s^2 / n_y,s)), which stays valid when the sizes' spreads and counts differ
  (Janssen 1997; Chung and Romano 2013), where the plain difference does not.
- **Family F-size** (§2.6, §7.3; Q15, Q33, Q62): adjacent baseline pairs (``results.SEPARATION_PAIRS``) at each gated
  size (M5-O2 default (b): ``F_SIZE_SIZES``), one-sided (61) with Holm at 0.05 on the declared direction; a pair passes
  when rejected. M5-O5 (6) default: a reversal is judged by each test's "less" p, Holm-adjusted over the same family's
  tests at the same level, and a significant reversal fails the family.
- **Re-parameterisation** (§2.6; Q64): a failing size or rung is re-parameterised, not explained; each attempt is
  logged (``ReparamAttempt``, numbered from 1 per target, one size or one rung, with the committed command that
  measured the failure; the γ ladder's one log is ``configs/experiment/ladder_gamma.yaml``'s ``attempts``) and the final
  pass or fail is re-run once on a holdout spawn key no tuning touched (``holdout_spec``: another split name, and the
  caller's other E_split; ``check_holdout`` refuses a re-run that shares a split name or an E_split, or plays another
  instance, other gated rungs or another ``HOLDOUT_SAME`` field (profile, cut points, F_Q); a shared scenario is a
  shared E_split, since omega's hash covers the split's label and so never repeats under two names (M5 re-gate
  ACC-M5R-05);
  ``run_ladder``'s holdout mode calls it on the tuned ladder's summary, before anything is drawn on a
  ``planned_ladder`` and again on the played one, and refuses another tested measure or delta_min).
- **Cut draws** (§11 row 28; M5-O17, answered): M5 cuts the anchor's strata at M = ``CUT_DRAWS`` (100), the seal at
  ``SEAL_CUT_DRAWS`` (10^5); ``check_sealable_cuts`` is the seal's refusal of cut points on fewer draws.
"""

import dataclasses
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from numbers import Integral, Real

import numpy as np

from sbfv.disruption.params import RUNGS
from sbfv.disruption.profiles import ANCHOR_RUNG, GATED_KNOBS, KNOBS, Rung
from sbfv.disruption.strata import CutPoints
from sbfv.oracle.lp import ORACLE_METHOD
from sbfv.policies.naive_fq import REPLICATIONS
from sbfv.scoring import inference
from sbfv.scoring.inference import B_FLIPS
from sbfv.scoring.rss import STRATUM_WEIGHTS


STREAM = "ladders"
DELTA_MIN = Fraction(1, 10)  # delta_min of (64), 10 % relative, SYNTHETIC (§7.4; §11 row 73; Q64)
B_PERM = 20_000  # B of the size-ladder permutation test (§7.4), SYNTHETIC protocol constant (§11 row 82)
FAMILY_ALPHA = 0.05  # Holm level of F-size and F-knob (§7.3 "Families")
SIZES = ("tiny", "small", "full")  # the size ladder, in order (§2.6)
# M5-O2 default (b): F-size gates `small` and `full` (2 x 2 = 4 tests) and reports `tiny`, a correctness fixture (Q82);
# answer (a), as designed (3 x 2 = 6 tests, §2.6, §7.3), is ``F_SIZE_SIZES = SIZES``; ``pilot.N_FAM`` follows it
F_SIZE_SIZES = ("small", "full")
# the sizes whose difficulty ladders are gated when they have a gated rung above the anchor (``is_gated``; §7.4 "Gated
# ladders", the owner's answers of 2026-09-29 to SPEC-M5R-04 and SPEC-M5R-05): `tiny` is a correctness fixture (Q82)
GATED_LADDER_SIZES = ("small", "full")
SIZE_STATISTICS = ("difference", "studentised")  # the size-ladder test's statistic (module docstring)
SIZE_STATISTIC = "studentised"  # M5-O5 (5) default: valid under unequal spreads (Janssen 1997; Chung and Romano 2013)
# the split name of a ladder's spawn keys: a label in omega's meta only, since omega is a function of (E_split, n,
# params) (§4.1), so the ladder's keys are its own only on its own E_split (128 bits per split and phase, §4.1); on the
# pilot's or the dev split's root it replays their scenarios (the M5 acceptance runs; docs/results.md, M5, "The shared
# root"). ``check_own_root`` refuses a ladder on a root it is told of (``run_ladder``'s ``experiment.distinct_from``,
# which names the same size's pilot on every gated ladder: §7.4 "Gated ladders")
LADDER_SPLIT = "ladder"
HOLDOUT_SPLIT = "ladder-holdout"  # the holdout re-run's split name (§2.6; Q64), played on another E_split
# M5-O17, answered (owner, 2026-09-28: "we can do 100 ... we will do larger sample as a split is sealed"): M of (44) on
# the anchor rung at M5 is 100, SYNTHETIC protocol constant (the 0.95 cut rests on the top 5 draws); the M5 entry points
# read it through ``sbf_boundary`` (LadderExperimentConfig.spec, run_pilot) when experiment.cut_draws is null
CUT_DRAWS = 100
# §11 row 28: M of a sealed split's cut points (all rungs at M6); the seal reads it through ``check_sealable_cuts``
SEAL_CUT_DRAWS = 100_000
RANKED_REGIME = "standard"  # M5-O5 (3) default: the pilot, F-size and the per-rung report play the ranked regime only
REVERSAL_ALTERNATIVE = "less"  # M5-O5 (6) default: a reversal is the "less" p, Holm-adjusted in the same family
PER_RUNG_POLICIES = ("greedy_lp", "mpc_det")  # M5-O1 (d) default: the per-rung pooled-RSS report (reported, not gated)
TRANSFER_POLICY = "mpc_det"  # M5-O5 (6) default: its horizon H is tuned on TRANSFER_FROM and scored on TRANSFER_TO
TRANSFER_FROM, TRANSFER_TO = "small", "full"  # the transfer check of §2.6, reported with no threshold
# the difficulty ladder's measure: "delta", (64), or "loss", the unavoidable loss loss_r (73). Q114's addendum (the
# owner's "Re-measure, then decide (Recommended)", after the re-measure on V3, docs/099-m5-sanction-rules.md): the γ
# ladder gates "loss", which the committed experiment files select (experiment.measure); MEASURE is the default of a
# ladder that names no measure
MEASURES = ("delta", "loss")
MEASURE = "delta"
# the size ladder's measures, each tested and reported, none gated: the owner's answer of 2026-09-29 ("Report it,
# don't gate (Recommended)"; Q114's superseding note), which supersedes the size ladder's gate on loss (73) (the answer
# to the M5 gate's ACC-M5-03, "Unavoidable loss, like γ") and M5-O30 (a)'s gated `small` -> `full`; the γ ladder keeps
# loss gated. Loss first: the size ladder's finding is stated on it, delta (64) beside it
SIZE_MEASURES = ("loss", "delta")
_PERM_CHUNK = 1_024  # permutations drawn per ``Generator.permuted`` call (bounds memory; fixed, so p is reproducible)


def rung_label(rung: Rung) -> str:
    """A rung's text label, ``<knob>=<value>`` with the value's ``repr`` (``gamma=0.62``): report and JSON keys."""
    return f"{rung.knob}={rung.value!r}"


def sink_demand(inst) -> float:
    """sum_{i in V^snk, k} d-bar_ik of (22), units per week: the denominator of (64) (``inst.demands`` are sinks')."""
    return math.fsum(d.dbar for d in inst.demands)


def _check_scale(T: int, sink_demand: float) -> None:
    if isinstance(T, bool) or not isinstance(T, Integral) or T < 1:
        raise ValueError(f"T of (64) is the horizon in weeks, an integer >= 1, got {T!r}")
    if isinstance(sink_demand, bool) or not isinstance(sink_demand, Real) or not math.isfinite(sink_demand):
        raise ValueError(f"the sink demand of (64) must be a finite number, got {sink_demand!r}")
    if sink_demand <= 0:
        raise ValueError(f"the sink demand of (64) must be positive, got {sink_demand!r}")


def _delta_min(delta_min) -> Fraction:
    """delta_min as an exact fraction >= 0; a float is refused, since its binary value would decide exact ties."""
    if isinstance(delta_min, bool) or not isinstance(delta_min, (Fraction, Integral)):
        raise TypeError(f"delta_min must be exact (a Fraction or an integer), got {delta_min!r}")
    d = Fraction(delta_min)
    if d < 0:
        raise ValueError(f"delta_min of (64) must be >= 0, got {d}")
    return d


def _check_B(B: int, what: str) -> int:
    if isinstance(B, bool) or not isinstance(B, Integral) or B < 1:
        raise ValueError(f"B of {what} must be an integer >= 1, got {B!r}")
    return int(B)


def _check_alpha(alpha: float) -> float:
    if isinstance(alpha, bool) or not isinstance(alpha, Real) or not 0 < alpha < 1:
        raise ValueError(f"the family level alpha must lie in (0, 1), got {alpha!r}")
    return float(alpha)


def check_sealable_cuts(cuts: CutPoints) -> None:
    """Refuse cut points of (44) drawn from fewer than ``SEAL_CUT_DRAWS`` draws: the seal's M (§11 row 28; M5-O17).

    M5 cuts the anchor at ``CUT_DRAWS`` (100) to keep the runs fast, and the runner records M with the cut points
    (``EvalResult.setup["cut_points"]["draws"]``); the seal (M6) calls this on the cut points it publishes with each
    split, so no strata cut at M5's M can be sealed.

    Raises:
        TypeError: if ``cuts`` is not a ``strata.CutPoints`` or its M is not an integer.
        ValueError: if M < ``SEAL_CUT_DRAWS``.

    """
    if not isinstance(cuts, CutPoints):
        raise TypeError(f"the seal checks strata.CutPoints, got {type(cuts).__name__}")
    if isinstance(cuts.draws, bool) or not isinstance(cuts.draws, Integral):
        raise TypeError(f"M of the cut points must be an integer, got {cuts.draws!r}")
    if cuts.draws < SEAL_CUT_DRAWS:
        raise ValueError(
            f"a sealed split's cut points rest on M = {SEAL_CUT_DRAWS} draws (§11 row 28; M5-O17), these on "
            f"{cuts.draws}"
        )


@dataclass(frozen=True)
class SizeSample:
    """One size's episodes for the size ladder: (73) on their J^oracle and (64) on their D, both reported (§7.4).

    Attributes:
        size: the instance kind (one of ``SIZES``).
        D: D_n = J^anchor_n - J^oracle_n of (57) per episode, integer cents.
        strata: harm stratum 1..4 of each episode, cut on this size's anchor rung (§7.4: strata cut per size).
        T: the horizon in weeks.
        sink_demand: sum over sinks i and commodities k of d-bar_ik (22), units per week (the denominator of (64)).
        weights: p_s of (44).
        J_oracle: J^oracle_n per episode, integer cents, in the order of ``D`` (the values of (73)); None on a sample
            that carries D alone (``values`` then refuses the loss measure).

    Raises:
        ValueError: on a size outside ``SIZES``, unequal lengths, a stratum label outside 1..len(weights), a negative
            weight, T < 1 or a sink demand that is not a positive finite number.
        TypeError: on a D or J^oracle that is not integer cents (floats and bools refused).

    """

    size: str
    D: tuple[int, ...]
    strata: tuple[int, ...]
    T: int
    sink_demand: float
    weights: tuple[float, ...] = STRATUM_WEIGHTS
    J_oracle: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        if self.size not in SIZES:
            raise ValueError(f"size must be one of {SIZES}, got {self.size!r}")
        D = inference._cents(self.D, "D")
        p = inference._weights(self.weights)
        labels = inference._labels(self.strata, len(D), len(p))
        _check_scale(self.T, self.sink_demand)
        if self.J_oracle is not None:
            J = inference._cents(self.J_oracle, "J_oracle")
            if len(J) != len(D):
                raise ValueError(f"lengths differ: D {len(D)}, J_oracle {len(J)}")
            object.__setattr__(self, "J_oracle", tuple(J))
        object.__setattr__(self, "D", tuple(D))
        object.__setattr__(self, "strata", tuple(labels))
        object.__setattr__(self, "weights", tuple(self.weights))

    def values(self, measure: str) -> tuple[int, ...]:
        """The episodes' values under ``measure`` (``MEASURES``): D for "delta" (64), J^oracle for "loss" (73).

        Raises:
            ValueError: on an unknown measure, or "loss" on a sample without J^oracle.

        """
        if check_measure(measure) == "delta":
            return self.D
        if self.J_oracle is None:
            raise ValueError(f"the {self.size!r} size sample carries no J^oracle: the loss measure (73) is undefined")
        return self.J_oracle


@dataclass(frozen=True)
class PairTest:
    """One adjacent-pair test of family F-size at one size (``better`` declared better than ``worse``)."""

    size: str
    better: str
    worse: str
    regime: str
    delta_hat: float  # (58), J^worse - J^better over D-bar
    p_greater: float  # one-sided (61), H1: ``better`` better
    p_less: float  # one-sided (61), H1: ``worse`` better (the reversal)


@dataclass(frozen=True)
class FamilyResult:
    """A Holm family's outcome: the tests in input order, their Holm-adjusted p, and the verdict.

    ``reversals`` lists the tests whose reversal is significant at the family level (F-size fails on any), judged on
    ``adjusted_reversal``, the Holm-adjusted "less" p (M5-O5 (6)); F-knob has no reversal and leaves both empty.
    """

    tests: tuple
    adjusted: tuple[float, ...]
    rejected: tuple[bool, ...]
    reversals: tuple[int, ...]
    passed: bool
    adjusted_reversal: tuple[float, ...] = ()


@dataclass(frozen=True)
class ReparamAttempt:
    """One logged re-parameterisation of a failing size or rung (§2.6; Q64): its attempt number and what changed.

    ``target`` is the failing size or rung (``key``), ``knob`` the parameter the attempt changes, ``command`` the
    committed command that measured the failure it answers; the final pass or fail is the holdout re-run.

    Raises:
        ValueError: on an attempt number < 1, a target that is not one size or one rung (``key``), or an empty knob,
            change, reason or command.

    """

    attempt: int
    target: str  # "size:<kind>" or "rung:<knob>=<value>"
    knob: str
    change: str
    reason: str
    command: str

    def __post_init__(self) -> None:
        a = self.attempt
        if isinstance(a, bool) or not isinstance(a, Integral) or a < 1:
            raise ValueError(f"attempts number from 1 (§2.6), got {a!r}")
        self.key()
        for name in ("knob", "change", "reason", "command"):
            v = getattr(self, name)
            if not isinstance(v, str) or not v.strip():
                raise ValueError(f"a logged attempt names its {name} (§2.6), got {v!r}")

    def key(self) -> tuple[str, str | Rung]:
        """The target as one size, ``("size", kind)``, or one rung, ``("rung", Rung(knob, value))`` (§12 row "Holdout").

        ``size:<kind>`` names a kind of ``SIZES``; ``rung:<knob>=<value>`` a knob of ``profiles.KNOBS`` at a finite
        number, a γ number being one of ``params.RUNGS`` (``profiles.Rung``). Two spellings of one rung
        (``rung:gamma=0.95``, ``rung:gamma=0.950``) are one target, numbered together by ``check_attempts``.

        Raises:
            ValueError: on any other target (free text, a missing or non-numeric value, an unknown knob or kind).

        """
        kind, sep, rest = str(self.target).partition(":")
        if kind == "size" and sep and rest in SIZES:
            return ("size", rest)
        knob, eq, value = rest.partition("=")
        if kind == "rung" and sep and eq and knob in KNOBS:
            try:
                return ("rung", Rung(knob, float(value)))
            except ValueError:
                pass
        raise ValueError(
            f"target must be 'size:<{'|'.join(SIZES)}>' or 'rung:<knob>=<number>' (a knob of {KNOBS}, a gamma number "
            f"one of the RUNGS), got {self.target!r}"
        )


def check_attempts(attempts: Sequence[ReparamAttempt]) -> tuple[ReparamAttempt, ...]:
    """The re-parameterisation log, checked: each target's attempts number 1, 2, ... in log order (§2.6; Q64).

    A target is its ``ReparamAttempt.key``, so two spellings of one rung share one numbering.

    Raises:
        TypeError: on an entry that is not a ``ReparamAttempt``.
        ValueError: on a target whose attempt numbers skip, repeat or do not start at 1.

    """
    seen: dict[tuple, int] = {}
    out = tuple(attempts)
    for a in out:
        if not isinstance(a, ReparamAttempt):
            raise TypeError(f"the log holds ReparamAttempt entries, got {a!r}")
        expected = seen.get(a.key(), 0) + 1
        if a.attempt != expected:
            raise ValueError(f"{a.target}: attempt {a.attempt} logged where attempt {expected} comes next (§2.6)")
        seen[a.key()] = a.attempt
    return out


def check_rung_order(rungs: Sequence[Rung], *, adjacent: bool = False) -> None:
    """Refuse γ rungs out of difficulty order: the anchor first, then ``params.RUNGS``' order (§2.6, §7.4).

    (64) and (73) test adjacent rungs in increasing difficulty, and F-knob and a reported rung's test pair consecutive
    entries of a ladder's rungs, so a reversed list tests a pair the design never states (M5 re-gate SPEC-M5R-04:
    0.97 -> 0.79 reported as "the rung below it"; ``experiment.values=[0.95, 0.79]`` put 0.95 -> 0.79 into F-knob).
    γ's difficulty table is ``RUNGS``, anchor first (§2.6; Q39). Without ``adjacent`` a ladder may leave a rung out, as
    the smoke run's 0.62 / 0.79 / 0.97 on `tiny` does, and its tests are then between the rungs it plays. With
    ``adjacent`` (a gated ladder, ``check_no_gap``; §7.4 "Gated ladders") a rung left out between the lowest and the
    highest γ played is refused too. Another knob's table is phase 4's (its rungs are refused before any draw, Q114's
    addendum on the other knobs), so only the anchor is checked for it.

    Raises:
        ValueError: if the γ values of ``rungs`` do not rise strictly in ``RUNGS``' order, or with ``adjacent`` if they
            leave a rung of ``RUNGS`` out between their lowest and highest.

    """
    order = [RUNGS.index(r.value) for r in rungs if r.knob == "gamma"]
    played = tuple(RUNGS[i] for i in order)
    if any(b <= a for a, b in zip(order, order[1:])):
        raise ValueError(
            "a ladder climbs γ in increasing difficulty, anchor first, each rung above the one before it "
            f"(params.RUNGS {RUNGS}; §2.6, §7.4), got {played}"
        )
    if adjacent and (missing := [RUNGS[i] for a, b in zip(order, order[1:]) for i in range(a + 1, b)]):
        raise ValueError(
            f"a gated ladder plays adjacent rungs of params.RUNGS {RUNGS} from its lowest to its highest, so each test "
            "of (64) and (73) is between adjacent rungs (§7.4, gated ladders; the owner's answer of 2026-09-29 to "
            f"SPEC-M5R-04): {played} leaves out {', '.join(map(repr, missing))}"
        )


@dataclass(frozen=True)
class LadderSpec:
    """A difficulty ladder of one size: the anchor rung's keys and strata, played at every rung (§7.4; Q88).

    Attributes:
        instance: a packaged instance name or a path.
        profile: the public generator profile (``policies.registry.PROFILES``).
        rungs: the rungs played, anchor first (``profiles.ANCHOR_RUNG``), then in increasing difficulty; all of one
            knob except the anchor. Adjacent rungs (the tests of (64)) are consecutive entries, so γ's are in
            ``params.RUNGS`` order (``check_rung_order``); a gated ladder's leave none of ``RUNGS`` out between them
            (``check_no_gap``, which needs the instance's size, so it is not checked here).
        n_per_stratum: N_s per anchor harm stratum (§11 row 29).
        cut_draws: M of (44) behind the anchor's cut points (§11 row 28: 10^5 at the seal, ``SEAL_CUT_DRAWS``; M5
            states a smaller M, ``CUT_DRAWS``, M5-O17).
        cut_entropy: the cut points' own root (§9.5), never an E_split.
        split: the spawn keys' split name; a holdout re-run uses another name and E_split (§2.6, ``holdout_spec``).
        fq_replications: naive's F_Q replications per (chokepoint, pool, rung) (§11 row 38).
        d_only: play only the oracle and the anchor on omega (D of (57)), no omega^0 and no baseline.
        policies: (baseline, parameters) pairs played on every rung when not ``d_only`` (the pooled-RSS report).
        regimes: the regimes those policies play (the ranked regime by default, M5-O5 (3)).
        max_candidates: candidates drawn at most while filling the anchor strata (None: ``runner.EpisodeSpec``'s).
        reported: the rungs of ``rungs`` played and reported but never gated (Q114's addendum: γ 0.97), the tail of
            ``rungs`` in the same order, so the gated rungs (``gated_rungs``, anchor first) are consecutive and F-knob
            tests their adjacent pairs; each reported rung's test against the rung below it is reported beside them.

    Raises:
        ValueError: on no rungs, a first rung that is not ``anchor``, a rung repeated, rungs of two knobs after the
            anchor, γ rungs out of difficulty order, N_s not four integers >= 0, ``cut_draws`` < 1, an empty split
            name, policies on a D-only ladder or none on a ladder that is not, no regime, or reported rungs that are
            not the tail of ``rungs`` after the anchor.

    """

    instance: str
    profile: str
    rungs: tuple[Rung, ...]
    n_per_stratum: tuple[int, ...]
    cut_draws: int
    cut_entropy: int
    split: str = LADDER_SPLIT
    fq_replications: int = REPLICATIONS
    d_only: bool = True
    policies: tuple[tuple[str, object | None], ...] = ()
    anchor: Rung = field(default=ANCHOR_RUNG)
    regimes: tuple[str, ...] = (RANKED_REGIME,)
    max_candidates: int | None = None
    reported: tuple[Rung, ...] = ()

    def __post_init__(self) -> None:
        rungs = tuple(self.rungs)
        if not rungs or rungs[0] != self.anchor:
            raise ValueError(f"a ladder plays its anchor {self.anchor} first (§7.4; Q88), got {rungs!r}")
        if len(set(rungs)) != len(rungs):
            raise ValueError(f"a rung is played once, got {rungs!r}")
        if len({r.knob for r in rungs[1:]}) > 1:
            raise ValueError(f"each rung changes one knob, the same along a ladder (§2.6), got {rungs!r}")
        check_rung_order(rungs)
        reported = tuple(self.reported)
        if reported and (len(reported) >= len(rungs) or reported != rungs[len(rungs) - len(reported) :]):
            raise ValueError(
                f"the reported rungs are the tail of the rung list after the gated ones, the anchor gated (Q114), got "
                f"reported {reported!r} of {rungs!r}"
            )
        n_s = tuple(self.n_per_stratum)
        if len(n_s) != len(STRATUM_WEIGHTS) or any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in n_s):
            raise ValueError(f"n_per_stratum needs one integer N_s >= 0 per harm stratum of (44), got {n_s!r}")
        c = self.cut_draws
        if isinstance(c, bool) or not isinstance(c, int) or c < 1:
            raise ValueError(f"cut_draws (M of (44)) must be an integer >= 1, got {c!r}")
        if not isinstance(self.split, str) or not self.split.strip():
            raise ValueError(f"the ladder's split name must be a non-empty string, got {self.split!r}")
        policies = tuple((name, params) for name, params in self.policies)
        if self.d_only and policies:
            raise ValueError("a D-only ladder plays the oracle and the anchor only: policies would be read by nothing")
        if not self.d_only and not policies:
            raise ValueError("a ladder that is not D-only plays policies on every rung: give at least one")
        if not self.regimes:
            raise ValueError("at least one regime")
        object.__setattr__(self, "rungs", rungs)
        object.__setattr__(self, "n_per_stratum", n_s)
        object.__setattr__(self, "policies", policies)
        object.__setattr__(self, "regimes", tuple(self.regimes))
        object.__setattr__(self, "reported", reported)

    @property
    def knob(self) -> str:
        """The knob this ladder climbs (the anchor's when it plays the anchor alone)."""
        return self.rungs[-1].knob

    @property
    def gated_rungs(self) -> tuple[Rung, ...]:
        """The rungs F-knob tests, anchor first: ``rungs`` without the reported tail."""
        return self.rungs[: len(self.rungs) - len(self.reported)]


def is_gated(spec: LadderSpec, kind: str) -> bool:
    """Whether ``spec`` on an instance of ``kind`` is a gated ladder (§7.4 "Gated ladders").

    Gated: a size of ``GATED_LADDER_SIZES`` (`small`, `full`) and a gated rung above the anchor, so F-knob tests at
    least one pair (the gate's γ ladders and holdouts, and any leaderboard ladder). A `tiny` ladder, a correctness
    fixture (Q82), and a reported-only one (its rungs above the anchor all reported) are not gated.
    """
    return kind in GATED_LADDER_SIZES and len(spec.gated_rungs) > 1


def check_no_gap(spec: LadderSpec, kind: str) -> None:
    """Refuse a gated ladder that leaves out a rung of ``RUNGS`` (§7.4 "Gated ladders"; M5 re-gate SPEC-M5R-04).

    The owner's answer of 2026-09-29 ("Refuse on gated"): a gated ladder (``is_gated``) plays every γ rung from the
    anchor to its highest played rung, the reported ones included, so each test of (64) and (73) and each reported
    rung's test is between rungs adjacent in ``RUNGS`` (``check_rung_order`` with ``adjacent``). A `tiny` ladder and
    a reported-only one may still leave a rung out. ``LadderSpec`` checks the order alone, since it does not know the
    instance's size; ``evaluate_ladder`` and ``run_ladder`` call this before anything is drawn.

    Raises:
        ValueError: on a gated ladder whose γ rungs leave a rung of ``RUNGS`` out.

    """
    if is_gated(spec, kind):
        check_rung_order(spec.rungs, adjacent=True)


@dataclass(frozen=True)
class RungRow:
    """One episode at one rung: its anchor key and stratum, the two sealed values behind D, the oracle's time, status.

    ``oracle_seconds`` is the oracle's solve time on this omega (§2.6 "Budgets": oracle times measured per size, Q13),
    outside equality as it is outside every hash (V1 compares rows across worker counts); None on a hand-built row.
    ``oracle_status`` is linprog's status of that solve (0 optimal, 1 iteration limit, 2 infeasible, 3 unbounded, 4
    numerical difficulties), the recorded cause of an exclusion (§6.3 "Status, solver and time are logged"; M5
    re-gate ORACLE-M5R2-04); None on a hand-built row and on a row read from a summary written before the fix.
    ``oracle_solver`` is the linprog method whose result the row keeps: highs-ds where §6.3's fallback re-solved a
    status-4 highs-ipm (an exclusion then means highs-ds failed too, at ``oracle_status``); None likewise.
    """

    episode: int
    stratum: int
    rung: Rung
    omega_hash: str
    J_oracle: int | None  # None when the oracle is not optimal (excluded as ``gated_exclusions`` says)
    J_anchor: int
    oracle_seconds: float | None = field(default=None, compare=False)
    oracle_status: int | None = None
    oracle_solver: str | None = None

    @property
    def D(self) -> int:
        """D_n = J^anchor_n - J^oracle_n (57) at this rung; raises when the oracle is not optimal (never 0-filled)."""
        if self.J_oracle is None:
            raise ValueError(
                f"episode {self.episode} at {rung_label(self.rung)}: the oracle is not optimal, D undefined"
            )
        return self.J_anchor - self.J_oracle


@dataclass(frozen=True)
class LadderResult:
    """A played ladder: rows by rung in the anchor keys' index order, exclusions, the command and E_split's SHA-256.

    ``excluded``: the episodes whose oracle is not optimal at some rung; those of a gated rung (``gated_exclusions``)
    leave every rung, the rest a reported rung's row and test only (pairing kept, §6.3; M5 gate ACC-M5-06).
    ``v5_failures``: the anchor's V5 failures, ``<rung>: <policy> <regime> ep<n>: <failure>`` (a bug when any is the
    anchor's: ``anchor_failed``); on a ladder that is not D-only also the policies'. ``evals``: each rung's
    ``EvalResult`` when the ladder is not D-only (the per-rung pooled-RSS report), else empty.
    """

    spec: LadderSpec
    rows: Mapping[Rung, tuple[RungRow, ...]]
    excluded: tuple[int, ...]
    setup: Mapping[str, object]
    v5_failures: tuple[str, ...] = ()
    anchor_failed: bool = False
    evals: Mapping[Rung, object] = field(default_factory=dict)


# ----- (64) and the difficulty test ----------------------------------------------------------------------------------
def delta_r(D: Sequence[int], strata: Sequence[int], *, T: int, sink_demand: float, weights=STRATUM_WEIGHTS) -> float:
    """delta_r of (64): sum_s p_s D-bar_s / (T sum_{i,k} d-bar_ik), from integer cents.

    Exact in fractions (p_s read as decimals, the sink demand's binary value), rounded once to a float. A stratum of
    weight 0 may be empty.

    Raises:
        TypeError: on a D that is not integer cents (floats and bools refused).
        ValueError: on unequal lengths, a label outside 1..len(weights), a stratum of positive weight with no episode,
            T < 1 or a sink demand that is not a positive finite number.

    """
    return _per_demand_week(D, strata, T, sink_demand, weights, "D", "D-bar_s of (64)")


def loss_r(
    J_oracle: Sequence[int], strata: Sequence[int], *, T: int, sink_demand: float, weights=STRATUM_WEIGHTS
) -> float:
    """loss_r of (73): sum_s p_s J-bar^oracle_s / (T sum_{i,k} d-bar_ik), from integer cents.

    The unavoidable loss per unit of sink demand and week at a rung, the γ ladder's gated measure (M5-O3's second
    branch, Q114's addendum; module docstring): ``delta_r``'s arithmetic on J^oracle (exact in fractions, rounded once
    to a float; a stratum of weight 0 may be empty).

    Raises:
        TypeError: on a J^oracle that is not integer cents (floats and bools refused).
        ValueError: as ``delta_r``.

    """
    return _per_demand_week(J_oracle, strata, T, sink_demand, weights, "J_oracle", "J-bar^oracle_s of loss_r")


def _per_demand_week(values, strata, T: int, sink_demand: float, weights, name: str, what: str) -> float:
    """sum_s p_s x-bar_s / (T sink_demand) of integer cents x, exact in fractions, one float (delta_r, loss_r)."""
    h = inference._cents(values, name)
    p = inference._weights(weights)
    labels = inference._labels(strata, len(h), len(p))
    _check_scale(T, sink_demand)
    sums, counts = [0] * len(p), [0] * len(p)
    for v, s in zip(h, labels, strict=True):
        sums[s - 1] += v
        counts[s - 1] += 1
    num = Fraction(0)
    for i, w in enumerate(p):
        if w == 0:
            continue
        if counts[i] == 0:
            raise ValueError(f"stratum {i + 1} has weight {w} and no episode: {what} undefined")
        num += w * Fraction(sums[i], counts[i])
    return float(num / (T * Fraction(sink_demand)))


def check_measure(measure: str) -> str:
    """``measure`` if it is one of ``MEASURES`` (the difficulty ladder's statistic).

    Raises:
        ValueError: on any other value.

    """
    if measure not in MEASURES:
        raise ValueError(f"the ladder measure must be one of {MEASURES}, got {measure!r}")
    return measure


def measure_values(rows: Sequence["RungRow"], measure: str) -> list[int]:
    """Each row's value under ``measure``: D (57) for "delta", J^oracle for "loss", integer cents.

    Raises:
        ValueError: on an unknown measure, or a row whose oracle is not optimal (D and J^oracle undefined).

    """
    check_measure(measure)
    if measure == "delta":
        return [r.D for r in rows]
    if bad := [r.episode for r in rows if r.J_oracle is None]:
        raise ValueError(f"episodes {bad}: the oracle is not optimal, J^oracle undefined")
    return [r.J_oracle for r in rows]


def difficulty_differences(
    D_lo: Sequence[int], D_hi: Sequence[int], delta_min: Fraction = DELTA_MIN
) -> tuple[int, ...]:
    """The paired statistic of the difficulty test in exact integers: den D_{n,r+1} - (den + num) D_{n,r}.

    ``delta_min`` = num / den; the result is den times D_{n,r+1} - (1 + delta_min) D_{n,r} of §7.4, so its sign and
    (61)'s p-value are the design's.

    Raises:
        TypeError: on a D that is not integer cents, or a delta_min that is not a Fraction or an integer.
        ValueError: on unequal lengths or a negative delta_min.

    """
    lo, hi = inference._cents(D_lo, "D_lo"), inference._cents(D_hi, "D_hi")
    if len(lo) != len(hi):
        raise ValueError(f"lengths differ: D_lo {len(lo)}, D_hi {len(hi)} (paired on the anchor keys)")
    d = _delta_min(delta_min)
    num, den = d.numerator, d.denominator
    return tuple(den * b - (den + num) * a for a, b in zip(lo, hi, strict=True))


def difficulty_test(
    D_lo: Sequence[int],
    D_hi: Sequence[int],
    strata: Sequence[int],
    *,
    delta_min: Fraction = DELTA_MIN,
    weights=STRATUM_WEIGHTS,
    B: int = B_FLIPS,
    entropy: int,
) -> float:
    """One-sided p of H0: delta_{r+1} <= (1 + delta_min) delta_r (64), paired on the anchor keys (§7.4).

    ``sign_flip(difficulty_differences(...), strata, alternative="greater")`` with the anchor strata's weights: the
    per-stratum means are over the anchor strata's N_s, so each episode weighs p_s / N_s, and T sum d-bar is common to
    both rungs of one size. Under the loss measure (``MEASURES``, the γ ladder's, Q114's addendum) the same test runs
    on J^oracle in place of D: H0 loss_{r+1} <= (1 + delta_min) loss_r of (73). ``sign_flip`` is exact at any
    magnitude, so the loss measure's d on `full`, whose N max |d| passed 2^62 at 100 per stratum on the M5 gate's runs
    (design §12 row "M5 gate fixes: ladders"), is tested, never refused (SPEC-M5-01).

    Raises:
        TypeError, ValueError: as ``difficulty_differences`` and ``scoring.inference.sign_flip``.

    """
    d = difficulty_differences(D_lo, D_hi, delta_min)
    return inference.sign_flip(d, strata, weights=weights, B=B, entropy=entropy, alternative="greater")


# ----- the size ladder ------------------------------------------------------------------------------------------------
def _studentise(diff, var):
    """The studentised statistic diff / sqrt(var): +-inf where var is 0 and diff is not, 0 where both are 0 (no NaN)."""
    diff = np.asarray(diff, dtype=np.float64)
    var = np.asarray(var, dtype=np.float64)
    safe = np.where(var > 0, var, 1.0)
    t = np.where(var > 0, diff / np.sqrt(safe), np.copysign(np.inf, diff))
    return np.where((var <= 0) & (diff == 0), 0.0, t)


def size_ladder_test(
    lower: SizeSample,
    upper: SizeSample,
    *,
    delta_min: Fraction = DELTA_MIN,
    B: int = B_PERM,
    entropy: int,
    statistic: str = SIZE_STATISTIC,
    measure: str = MEASURE,
) -> float:
    """One-sided p of H0: m_upper <= (1 + delta_min) m_lower, m delta of (64) or loss of (73), unpaired (§7.4).

    ``measure`` (``MEASURES``) names the values v: D ("delta", this function's default) or J^oracle ("loss");
    ``results.size_ladder_report`` runs it once per measure of ``SIZE_MEASURES`` and reports each p, gating none. A
    stratified two-sample permutation test relabelling scenarios within each harm stratum, the permutations from
    ``disruption.gate.evaluation_generator(entropy)``; ``statistic`` one of ``SIZE_STATISTICS``. The values are
    x_n = v_n / (T sum d-bar) on ``upper`` and y_n = (1 + delta_min) v_n / (T sum d-bar) on ``lower`` (the shifted
    null, M5-O5 (5)); the statistic is sum_s p_s (x-bar_s - y-bar_s), divided by
    sqrt(sum_s p_s^2 (s_x,s^2 / n_x,s + s_y,s^2 / n_y,s)) when studentised (sample variances, ddof 1). Within stratum
    s the pooled values are centred on their mean (a shift every relabelling shares), and each permutation is a row of
    ``Generator.permuted`` over the pooled indices, the first n_x,s going to ``upper``; strata are drawn in label
    order, ``_PERM_CHUNK`` rows per call. p = (1 + #{b: t^(b) >= t}) / (B + 1).

    Raises:
        TypeError: on a delta_min that is not exact.
        ValueError: on an unknown statistic or measure, B < 1, sizes not in ladder order (``lower`` before ``upper``
            in ``SIZES``), different weights, a sample without the measure's values (``SizeSample.values``), or a
            stratum of positive weight with fewer than 2 episodes (1 for the plain difference) in either size.

    """
    from sbfv.disruption.gate import evaluation_generator

    if statistic not in SIZE_STATISTICS:
        raise ValueError(f"statistic must be one of {SIZE_STATISTICS}, got {statistic!r}")
    B = _check_B(B, "the size-ladder permutation test")
    shift = 1 + _delta_min(delta_min)
    if SIZES.index(lower.size) >= SIZES.index(upper.size):
        raise ValueError(f"the size ladder runs {' -> '.join(SIZES)}: {lower.size!r} is not below {upper.size!r}")
    p = inference._weights(lower.weights)
    if p != inference._weights(upper.weights):
        raise ValueError("the sizes' strata carry the same p_s (§7.4): the weights differ")
    x = np.array(upper.values(measure), dtype=np.float64) / (upper.T * upper.sink_demand)
    y = np.array(lower.values(measure), dtype=np.float64) * (float(shift) / (lower.T * lower.sink_demand))
    lab_x, lab_y = np.array(upper.strata), np.array(lower.strata)
    need = 2 if statistic == "studentised" else 1
    rng = evaluation_generator(entropy)
    diff_obs, var_obs = 0.0, 0.0
    diff_b, var_b = np.zeros(B), np.zeros(B)
    for s, w in enumerate(p, start=1):
        if w == 0:
            continue
        xs, ys = x[lab_x == s], y[lab_y == s]
        if len(xs) < need or len(ys) < need:
            raise ValueError(
                f"stratum {s}: {len(xs)} episodes of {upper.size!r} and {len(ys)} of {lower.size!r}; the {statistic} "
                f"statistic needs at least {need} of each"
            )
        wf = float(w)
        pooled = np.concatenate([xs, ys])
        pooled = pooled - pooled.mean()
        m, nx = len(pooled), len(xs)
        diff_obs += wf * (pooled[:nx].mean() - pooled[nx:].mean())
        if need == 2:
            var_obs += wf * wf * (pooled[:nx].var(ddof=1) / nx + pooled[nx:].var(ddof=1) / (m - nx))
        for lo in range(0, B, _PERM_CHUNK):
            rows = min(_PERM_CHUNK, B - lo)
            g = pooled[rng.permuted(np.tile(np.arange(m), (rows, 1)), axis=1)]
            a, b = g[:, :nx], g[:, nx:]
            diff_b[lo : lo + rows] += wf * (a.mean(axis=1) - b.mean(axis=1))
            if need == 2:
                var_b[lo : lo + rows] += wf * wf * (a.var(axis=1, ddof=1) / nx + b.var(axis=1, ddof=1) / (m - nx))
    if need == 2:
        t_obs, t_b = float(_studentise(diff_obs, var_obs)), _studentise(diff_b, var_b)
    else:
        t_obs, t_b = diff_obs, diff_b
    return (1 + int(np.count_nonzero(t_b >= t_obs))) / (B + 1)


# ----- the Holm families ---------------------------------------------------------------------------------------------
def _pvalues(ps: Sequence[float], what: str) -> list[float]:
    out = []
    for v in ps:
        if isinstance(v, bool) or not isinstance(v, Real) or not 0 <= v <= 1:
            raise ValueError(f"{what}: a p-value lies in [0, 1], got {v!r}")
        out.append(float(v))
    return out


def f_size_family(tests: Sequence[PairTest], *, alpha: float = FAMILY_ALPHA) -> FamilyResult:
    """Family F-size (§2.6, §7.3): Holm at ``alpha`` over the tests' ``p_greater``; a significant reversal fails it.

    A pair passes when its Holm-adjusted ``p_greater`` is at most ``alpha``; a reversal is a test whose ``p_less``,
    Holm-adjusted over the family's tests, is at most ``alpha`` (M5-O5 (6)). The family passes when every pair passes
    and no reversal is significant.

    Raises:
        TypeError: on an entry that is not a ``PairTest``.
        ValueError: on no test, a (size, better, worse, regime) listed twice, a p outside [0, 1] or an alpha outside
            (0, 1).

    """
    from sbfv.disruption.gate import holm

    tests = tuple(tests)
    alpha = _check_alpha(alpha)
    if not tests:
        raise ValueError("F-size needs at least one test (an empty family would pass without evidence)")
    if any(not isinstance(t, PairTest) for t in tests):
        raise TypeError("F-size's entries are PairTest")
    ids = [(t.size, t.better, t.worse, t.regime) for t in tests]
    if len(set(ids)) != len(ids):
        raise ValueError(f"a test is listed twice in F-size: {ids}")
    adj = holm(_pvalues([t.p_greater for t in tests], "p_greater"))
    rev = holm(_pvalues([t.p_less for t in tests], "p_less"))
    rejected = tuple(bool(a <= alpha) for a in adj)
    reversals = tuple(i for i, a in enumerate(rev) if a <= alpha)
    return FamilyResult(
        tests=tests,
        adjusted=tuple(float(a) for a in adj),
        rejected=rejected,
        reversals=reversals,
        passed=all(rejected) and not reversals,
        adjusted_reversal=tuple(float(a) for a in rev),
    )


def f_knob_family(pvalues: Sequence[float], *, alpha: float = FAMILY_ALPHA) -> FamilyResult:
    """Family F-knob (§7.3): Holm over one knob's gated rungs - 1 difficulty tests; a rung passes only if rejected.

    The knob passes when every gated rung's H0 of (64), or of (73) under the loss measure, is rejected (burden of proof
    on passing, Q64); a reported rung's test is not in the family (``LadderSpec.reported``).

    Raises:
        ValueError: on no p-value, a p outside [0, 1] or alpha outside (0, 1).

    """
    from sbfv.disruption.gate import holm

    alpha = _check_alpha(alpha)
    ps = _pvalues(pvalues, "F-knob")
    if not ps:
        raise ValueError("F-knob needs at least one rung difference (an empty family would pass without evidence)")
    adj = holm(ps)
    rejected = tuple(bool(a <= alpha) for a in adj)
    return FamilyResult(tuple(ps), tuple(float(a) for a in adj), rejected, (), all(rejected))


# ----- playing a ladder ----------------------------------------------------------------------------------------------
def _generator_ref(spec: LadderSpec, rung: Rung):
    """The public generator of ``rung`` (``registry.GeneratorRef``): only γ rungs are played (M5-O3 (a)).

    The other knobs' rungs, the reported ones of §2.6 included, are deferred to phase 4 (the owner's answer of
    2026-09-29 to the M5 gate, Q114's addendum on the other knobs).

    Raises:
        NotImplementedError: for a knob other than γ (no rung rule: ``profiles.apply_rung``; ``GATED_KNOBS``).

    """
    from sbfv.policies.registry import GeneratorRef

    if rung.knob != "gamma":
        raise NotImplementedError(
            f"the ladder runner plays γ rungs only (M5-O3 (a), gated knobs {GATED_KNOBS}): knob {rung.knob!r} has no "
            "rung rule or public generator reference, its rungs deferred to phase 4 (Q114's addendum on the other "
            "knobs)"
        )
    return GeneratorRef(spec.profile, rung.value)


def episode_spec(spec: LadderSpec, rung: Rung, episodes: Sequence[int] | None = None):
    """The runner's ``EpisodeSpec`` of ``rung``: the anchor's stratified fill, or the given episodes (plain range).

    Every rung shares the ladder's split, instance and replication count; only the generator's rung differs.
    """
    from sbfv.evaluation.runner import EpisodeSpec

    common = {
        "instance": spec.instance,
        "kind": "generated",
        "split": spec.split,
        "generator": _generator_ref(spec, rung),
        "fq_replications": spec.fq_replications,
    }
    if episodes is not None:
        return EpisodeSpec(**common, episodes=tuple(episodes))
    extra = {} if spec.max_candidates is None else {"max_candidates": spec.max_candidates}
    return EpisodeSpec(
        **common, cut_draws=spec.cut_draws, cut_entropy=spec.cut_entropy, n_per_stratum=spec.n_per_stratum, **extra
    )


def evaluate_ladder(
    spec: LadderSpec, *, entropy: int, n_jobs: int = 1, oracle_method: str = ORACLE_METHOD, command: str = ""
) -> LadderResult:
    """Play ``spec``: the anchor rung's keys and strata (``runner.episode_keys``), then every rung on those keys.

    Workers go through ``parallel.ordered_map``; naive's F_Q is computed once per rung in the parent (as
    ``runner.evaluate`` does); E_split never leaves this call (``setup`` records its SHA-256). D-only: each rung's
    rows come from ``runner.evaluate_d`` (the oracle and the anchor on omega; at the anchor rung each omega is checked
    against its key). Otherwise each rung is a full ``runner.evaluate_keys`` of ``spec.policies`` on the anchor keys
    re-drawn at the rung (``runner.rung_keys``), kept in ``LadderResult.evals``. No result depends on ``n_jobs`` (V1).

    Raises:
        NotImplementedError: for a rung of a knob other than γ (before anything is drawn).
        ValueError: on a gated ladder that leaves a rung out (``check_no_gap``, before anything is drawn), and as
            ``runner.episode_keys`` (an unfilled stratum included) and ``runner.check_request``.

    """
    from sbfv.disruption.params import generator_id
    from sbfv.evaluation import runner
    from sbfv.instance import load_instance

    refs = {rung: _generator_ref(spec, rung) for rung in spec.rungs}  # refuses a knob before any draw
    if not spec.d_only:
        runner.check_request(spec.policies, spec.regimes)
    inst = load_instance(spec.instance)
    check_no_gap(spec, inst.kind)  # a gated ladder's gap, before any draw (§7.4 "Gated ladders")
    gids = {rung_label(r): generator_id(ref.params(inst), inst) for r, ref in refs.items()}
    keys, anchor_setup = runner.episode_keys(episode_spec(spec, spec.anchor), entropy=entropy, n_jobs=n_jobs)
    episodes = tuple(k.episode for k in keys)
    rows: dict[Rung, tuple[RungRow, ...]] = {}
    evals: dict[Rung, object] = {}
    failures: list[str] = []
    anchor_failed = False
    for rung in spec.rungs:
        rspec = episode_spec(spec, rung, episodes)
        label = rung_label(rung)
        if spec.d_only:
            drows = runner.evaluate_d(
                rspec, keys, entropy=entropy, check_hash=rung == spec.anchor, n_jobs=n_jobs, oracle_method=oracle_method
            )
            rows[rung] = tuple(
                RungRow(
                    r.episode,
                    r.stratum,
                    rung,
                    r.omega_hash,
                    r.J_oracle_cents,
                    r.J_anchor_cents,
                    r.oracle_seconds,
                    r.oracle_status,
                    r.oracle_solver,
                )
                for r in drows
            )
            lines = [f for r in drows for f in r.v5_failures]
            anchor_failed |= bool(lines)
        else:
            rkeys = keys if rung == spec.anchor else runner.rung_keys(rspec, keys, entropy=entropy, n_jobs=n_jobs)
            res = runner.evaluate_keys(
                rspec,
                rkeys,
                anchor_setup,
                spec.policies,
                spec.regimes,
                entropy=entropy,
                n_jobs=n_jobs,
                command=command,
                oracle_method=oracle_method,
            )
            evals[rung] = res
            rows[rung] = tuple(
                RungRow(
                    r.episode,
                    r.stratum,
                    rung,
                    r.omega_hash,
                    r.J_oracle_cents,
                    r.J_naive_cents,
                    r.oracle_seconds,
                    r.oracle_status,
                    r.oracle_solver,
                )
                for r in res.rows
            )
            lines = list(res.v5_failures)
            anchor_failed |= res.anchor_failed
        failures += [f"{label}: {line}" for line in lines]
    excluded = tuple(sorted({r.episode for rr in rows.values() for r in rr if r.J_oracle is None}))
    setup = dict(anchor_setup) | {
        "instance_name": spec.instance,
        "profile": spec.profile,
        "rungs": [rung_label(r) for r in spec.rungs],
        "reported": [rung_label(r) for r in spec.reported],
        "generators": {rung_label(r): dataclasses.asdict(g) for r, g in refs.items()},
        "generator_ids": gids,
        "d_only": spec.d_only,
        "regimes": list(spec.regimes) if not spec.d_only else [],
        "policies": [name for name, _ in spec.policies],
        "oracle_method": oracle_method,
        "T": inst.T,
        "sink_demand": sink_demand(inst),
        "instance_kind": inst.kind,
        "command": command,
    }
    if evals and (provenance := evals[spec.anchor].setup.get("policy_provenance")):
        setup["policy_provenance"] = provenance  # a kit agent's seed_id and files, as evaluate_keys records (DET-M5R-2)
    return LadderResult(spec, rows, excluded, setup, tuple(failures), anchor_failed, evals)


# ----- exclusions, the size ladder's sample, the holdout --------------------------------------------------------------
def gated_exclusions(result: LadderResult) -> tuple[int, ...]:
    """The episodes whose oracle is not optimal at a gated rung (``LadderSpec.gated_rungs``), in index order.

    They leave every rung's report, F-knob's tests and the size sample (pairing kept, §6.3). An episode not optimal
    only at a reported rung (γ 0.97, outside F-knob, Q114's addendum) stays in them and leaves that rung's row and its
    test against the rung below only, so a rung the family does not test cannot move the family's sample (M5 gate
    ACC-M5-06).
    """
    return tuple(sorted({r.episode for g in result.spec.gated_rungs for r in result.rows[g] if r.J_oracle is None}))


def size_sample(result: LadderResult) -> SizeSample:
    """The anchor rung's J^oracle and D of a played ladder as the size ladder's sample (strata cut per size, §7.4).

    Episodes excluded at a gated rung are dropped, as F-knob's tests drop them (``gated_exclusions``).

    Raises:
        ValueError: if the anchor failed V5 (D is then undefined: a bug, §6.2) or the instance kind is not a size.

    """
    if result.anchor_failed:
        raise ValueError("the anchor failed V5 on this ladder (a bug, §6.2): D is undefined")
    excluded = set(gated_exclusions(result))
    kept = [r for r in result.rows[result.spec.anchor] if r.episode not in excluded]
    return SizeSample(
        size=str(result.setup["instance_kind"]),
        D=tuple(r.D for r in kept),
        strata=tuple(r.stratum for r in kept),
        T=int(result.setup["T"]),
        sink_demand=float(result.setup["sink_demand"]),
        J_oracle=tuple(r.J_oracle for r in kept),
    )


def holdout_spec(spec: LadderSpec, split: str = HOLDOUT_SPLIT) -> LadderSpec:
    """The holdout re-run of ``spec`` (§2.6; Q64): the same ladder on another split name, played on another E_split.

    Raises:
        ValueError: if ``split`` is the tuned ladder's own split name.

    """
    if split == spec.split:
        raise ValueError(f"a holdout re-run takes another split name than the tuned ladder's {spec.split!r}")
    return dataclasses.replace(spec, split=split)


def planned_ladder(spec: LadderSpec, *, entropy: int) -> LadderResult:
    """``spec`` on E_split ``entropy`` before anything is drawn, as ``check_holdout`` reads a holdout it refuses early.

    No row; the setup holds the instance's hash and E_split's SHA-256 (``runner.entropy_sha256``), never E_split.
    """
    from sbfv.evaluation.runner import entropy_sha256
    from sbfv.instance import load_instance

    setup = {"instance_hash": load_instance(spec.instance).hash, "entropy_sha256": entropy_sha256(entropy)}
    return LadderResult(spec, {}, (), setup)


# what a holdout shares with the tuned ladder beyond its instance and gated rungs (``check_holdout``; the M5 gate's
# skeptic of SIMP-M5-02): the ``LadderSpec`` field and its name in a refusal
HOLDOUT_SAME = {
    "profile": "generator profile",
    "cut_draws": "cut draws M",
    "cut_entropy": "cut entropy",
    "fq_replications": "F_Q replications",
}


def check_holdout(tuned: LadderResult, holdout: LadderResult) -> None:
    """Refuse a holdout re-run that shares the tuned ladder's split name or its E_split (§2.6; Q64).

    E_split is compared by its SHA-256 (``setup["entropy_sha256"]``), the only form a result holds. It is the whole
    guard on the keys: omega is a function of (E_split, n, params), the split name a label in its meta (§4.1), so the
    tuned scenarios under the holdout's name are the tuned E_split, and omega hashes, which cover the label, never
    repeat under two split names; a clause comparing them could not fire and is gone (M5 re-gate ACC-M5R-05). The
    two must be ladders of one instance and one list of gated rungs, the family the holdout decides; the reported
    rungs may differ, since they are outside F-knob and, by ``gated_exclusions``, outside its sample (the gate plan's
    holdout drops γ 0.97). They must also share what defines the ladder's values and strata
    (``HOLDOUT_SAME``): the generator profile, the cut points' M and root (§9.5: the strata are the cut points', never
    an E_split's) and naive's F_Q replications (the anchor, so D); N_s, D-only and the flips may differ. ``holdout``
    may be a ``planned_ladder``, with no row yet: the check reads no row, so it is the same before anything is drawn
    and once played (``run_ladder``'s holdout mode, which also refuses another tested measure or delta_min).

    Raises:
        ValueError: on a shared split name or E_split, or another instance, list of gated rungs, profile, cut points or
            F_Q replications.

    """
    a, b = tuned.setup, holdout.setup
    if a["instance_hash"] != b["instance_hash"] or tuned.spec.gated_rungs != holdout.spec.gated_rungs:
        raise ValueError("a holdout re-runs the same ladder: the instance or the gated rungs differ")
    if differ := [name for f, name in HOLDOUT_SAME.items() if getattr(tuned.spec, f) != getattr(holdout.spec, f)]:
        raise ValueError(f"a holdout re-runs the same ladder, and these differ from the tuned one: {', '.join(differ)}")
    if tuned.spec.split == holdout.spec.split:
        raise ValueError(f"the holdout reuses the tuned split name {tuned.spec.split!r}")
    if a["entropy_sha256"] == b["entropy_sha256"]:
        raise ValueError("the holdout reuses the tuned E_split (same SHA-256): no tuning may have touched its keys")


def check_own_root(ladder: LadderResult, others: Mapping[str, str]) -> None:
    """Refuse a ladder on the E_split of another split's run (§4.1: 128 bits per split and phase).

    ``others`` maps a run's name (its summary's path) to its E_split's SHA-256. omega ignores the split name (§4.1),
    so a ladder on the pilot's or the dev split's root plays their scenarios at the anchor: one sample, not two (the M5
    acceptance runs; M5 re-gate SPEC-M5R-05). ``ladder`` may be a ``planned_ladder``, so the refusal comes before
    anything is drawn. E_split lives only in the environment (§4.1), so a ladder knows another run's root only
    through that run's summary: a gated ladder (``is_gated``) must name its size's pilot among them, which
    ``run_ladder`` refuses it without (§7.4 "Gated ladders"; the owner's answer of 2026-09-29, "Name the pilot").

    Raises:
        ValueError: when ``ladder``'s E_split SHA-256 is one of ``others``'.

    """
    own = ladder.setup["entropy_sha256"]
    if shared := [name for name, sha in others.items() if sha == own]:
        raise ValueError(
            f"the ladder (split {ladder.spec.split!r}) is on the E_split of {', '.join(shared)} (same SHA-256): omega "
            "ignores the split name, so it would replay that run's scenarios; give each split its own root (§4.1)"
        )
