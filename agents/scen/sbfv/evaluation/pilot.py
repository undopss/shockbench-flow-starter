"""The 30-per-stratum pilot, V15 and the sizing (59) (milestone M5, stream "ladders"; design §7.3; Q14, Q63).

Readings the design leaves open are in docs/owner-queue.md (2026-09-28, M5); each is built at its recommended default,
kept in one named constant with the question id beside it. The builder-level readings are the design §12 rows under
"M5 stream ladders".

- **Pilot** (§7.3 "Sizing"): 30 scenarios per harm stratum on `small` and on `full`, running the budget-compliant
  baselines under the ranked regime (M5-O5 (3), ``PILOT_REGIMES``). The runner fills strata in index order
  (``runner.fill_strata``), so the pilot is the prefix of a 100-per-stratum dev split (M5-O5 (4)).
- **V15** (§10): sigma_res,s = SD_{n in s}(upsilon_n) of (58) per adjacent pair and stratum (the sample SD, ddof 1),
  its bootstrap SE and the ESS (sum D)^2 / sum D^2 per stratum; sigma enters (59) at the 80 % bootstrap upper bound.
  M5-O5 (2) default: the bootstrap is stratified, all policies together (one resample of scenario indices serves J^A,
  J^B and D), recomputing Delta-hat, D-bar and upsilon in each resample, B = 10,000 from
  ``disruption.gate.evaluation_generator``; the upper bound is the ceil(0.8 B)-th smallest resampled sigma (the
  package's one quantile rule, ``strata.inverse_cdf``) and the SE their sample SD. M5-O31, answered (c) (owner,
  2026-09-28): each resampled sigma*_s is first scaled by sqrt(N_s / (N_s - 1)) (``SMALL_SAMPLE_CORRECTION``), since
  a resample's SD runs low by about sqrt((N_s - 1) / N_s) and the percentile bound inherited it (coverage 0.74-0.79
  at 30 per stratum, docs/evidence/m5_ladder_size_8_ABC.txt part C); the SE and the upper bound are both read from the
  scaled values.
- **(59)**: N = ceil((z_{1-alpha/n_fam} + z_{0.8})^2 (sum_s p_s sigma_s)^2 / Delta_min^2), one-sided z; Neyman
  N_s = max(20, ceil(N p_s sigma_s / sum p sigma)). M5-O5 (1) default: sigma comes from the F-size pairs, and N is the
  maximum over the pairs at `full` (``SIZING_SIZE``); n_fam follows F-size's scope (M5-O2, ``N_FAM``); Delta_min stays
  open (Q14, M5-O4), so ``sample_size`` takes it as an argument and has no default (``DELTA_MIN_CANDIDATES`` are the
  values the pilot reports).
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from numbers import Integral, Real

import numpy as np

from sbfv.evaluation.ladders import F_SIZE_SIZES, RANKED_REGIME
from sbfv.evaluation.results import SEPARATION_PAIRS, base_name
from sbfv.evaluation.runner import STRATA, EpisodeSpec
from sbfv.policies.naive_fq import REPLICATIONS
from sbfv.policies.registry import BASELINES, GeneratorRef
from sbfv.scoring import inference
from sbfv.scoring.rss import STRATUM_WEIGHTS


STREAM = "ladders"
PER_STRATUM = 30  # pilot scenarios per harm stratum, SYNTHETIC protocol constant (§7.3; §11 row 82; Q63)
DEV_PER_STRATUM = 100  # private episodes per stratum until the pilot sizes N_s (§7.3; §11 rows 29, 82)
B_BOOT = 10_000  # bootstrap resamples (§7.3 (62); §11 row 82)
UPPER_LEVEL = 0.80  # sigma enters (59) at its 80 % bootstrap upper bound (§7.3; §11 row 82)
SMALL_SAMPLE_CORRECTION = True  # M5-O31 answer (c): sigma*_s scaled by sqrt(N_s / (N_s - 1)) before the quantile
FLOOR = 20  # the N_s floor of (59) (§11 row 82)
ALPHA = 0.05  # the F-size family level (§7.3)
POWER = 0.80  # z_{0.8} of (59)
# n_fam of (59): F-size's test count, the gated sizes (M5-O2, ``ladders.F_SIZE_SIZES``) times the §2.6 pairs; 4 under
# M5-O2's default (b), 6 as designed (§7.3)
N_FAM = len(F_SIZE_SIZES) * len(SEPARATION_PAIRS)
PILOT_SPLIT = "dev"  # M5-O5 (4) default: the pilot is the prefix of the dev split (index-order fill)
PILOT_REGIMES = (RANKED_REGIME,)  # M5-O5 (3) default: the pilot plays the ranked regime only
SIZING_SIZE = "full"  # M5-O5 (1) default: N is the maximum over the F-size pairs at `full`
DELTA_MIN_CANDIDATES = (0.10, 0.05)  # M5-O4 (Q14): the pilot reports (59) at both; 0.10 recommended (§11 row 30)


@dataclass(frozen=True)
class SigmaEstimate:
    """V15 for one (pair, stratum): sigma_res,s of (59), its bootstrap SE and upper bound, the stratum's ESS."""

    better: str
    worse: str
    stratum: int
    n: int
    sigma: float
    se: float
    upper: float  # the ``UPPER_LEVEL`` bootstrap quantile of sigma, the value (59) takes
    ess: float  # (sum D)^2 / sum D^2 over the stratum (§7.3 diagnostics)


@dataclass(frozen=True)
class Sizing:
    """(59)'s answer for one Delta_min: N, the Neyman N_s per stratum, and the pair and size that set N."""

    delta_min: float
    N: int
    n_per_stratum: tuple[int, ...]
    binding_pair: tuple[str, str]
    size: str


def pilot_spec(
    instance: str,
    generator: GeneratorRef,
    *,
    cut_draws: int,
    cut_entropy: int,
    per_stratum: int = PER_STRATUM,
    fq_replications: int = REPLICATIONS,
) -> EpisodeSpec:
    """The pilot's episodes: the dev split filled to ``per_stratum`` per harm stratum at the generator's rung (§7.3).

    Because strata fill in index order, these keys are the prefix of the ``DEV_PER_STRATUM`` split on the same cut
    points (``runner.fill_strata``).
    """
    return EpisodeSpec(
        instance=instance,
        kind="generated",
        split=PILOT_SPLIT,
        generator=generator,
        fq_replications=fq_replications,
        cut_draws=cut_draws,
        cut_entropy=cut_entropy,
        n_per_stratum=(per_stratum,) * STRATA,
    )


def _groups(labels: Sequence[int], n_strata: int) -> dict[int, list[int]]:
    """Episode positions per stratum label 1..n_strata, in the order given."""
    out: dict[int, list[int]] = {s: [] for s in range(1, n_strata + 1)}
    for i, s in enumerate(labels):
        out[s].append(i)
    return out


def sigma_res(
    J_A: Sequence[int], J_B: Sequence[int], D: Sequence[int], strata: Sequence[int], weights=STRATUM_WEIGHTS
) -> dict[int, float]:
    """sigma_res,s of (59) per stratum: the sample SD of upsilon_n of (58) (``scoring.inference.residuals``) in s.

    The SD has ddof 1; strata of weight 0 with no episode are left out. Keys are the stratum labels, in order.

    Raises:
        TypeError, ValueError: as ``inference.residuals``; a ValueError also for a stratum of positive weight with
            fewer than 2 episodes (its SD is undefined).

    """
    ups = inference.residuals(J_A, J_B, D, strata, weights)
    p = inference._weights(weights)
    labels = inference._labels(strata, len(ups), len(p))
    out = {}
    for s, idx in _groups(labels, len(p)).items():
        if p[s - 1] == 0 and not idx:
            continue
        if len(idx) < 2:
            raise ValueError(f"stratum {s} holds {len(idx)} episode(s): sigma_res,s of (59) needs at least 2")
        out[s] = float(np.std(np.array([ups[i] for i in idx]), ddof=1))
    return out


def v15(
    J_A: Sequence[int],
    J_B: Sequence[int],
    D: Sequence[int],
    strata: Sequence[int],
    *,
    better: str,
    worse: str,
    weights=STRATUM_WEIGHTS,
    B: int = B_BOOT,
    level: float = UPPER_LEVEL,
    entropy: int,
    small_sample: bool = SMALL_SAMPLE_CORRECTION,
) -> tuple[SigmaEstimate, ...]:
    """V15 for one pair: per stratum sigma, its stratified-bootstrap SE and ``level`` upper bound, and the ESS.

    The bootstrap (module docstring, M5-O5 (2)): for b = 1..B, each stratum's scenario indices are resampled with
    replacement to its own N_s (one ``integers(0, N_s, (B, N_s))`` matrix per stratum, strata in label order, from
    ``gate.evaluation_generator(entropy)``); in each resample Delta-hat* and D-bar* of (58) are recomputed from the
    resampled J^A, J^B and D, upsilon* from them, and sigma*_s is the sample SD (ddof 1) of upsilon* in stratum s. With
    ``small_sample`` (M5-O31 (c), the default) each sigma*_s is multiplied by sqrt(N_s / (N_s - 1)). SE is the sample
    SD of sigma*_s over b, ``upper`` its ceil(level B)-th smallest value; on the same draws the corrected ``upper`` is
    the uncorrected one times the factor exactly (an order statistic). Floats in the resamples (the point estimate is
    exact, ``sigma_res``).

    Raises:
        TypeError, ValueError: as ``sigma_res``; a ValueError also for B < 2, a level outside (0, 1), or a resample
            whose D-bar* is not positive ((58) undefined there); a TypeError for a ``small_sample`` that is not a bool.

    """
    from sbfv.disruption.gate import evaluation_generator
    from sbfv.disruption.strata import inverse_cdf

    sigma = sigma_res(J_A, J_B, D, strata, weights)
    if isinstance(B, bool) or not isinstance(B, Integral) or B < 2:
        raise ValueError(f"B of the V15 bootstrap must be an integer >= 2, got {B!r}")
    if isinstance(level, bool) or not isinstance(level, Real) or not 0 < level < 1:
        raise ValueError(f"level must lie in (0, 1), got {level!r}")
    if not isinstance(small_sample, bool):
        raise TypeError(f"small_sample (M5-O31) must be a bool, got {small_sample!r}")
    a, b, h = inference._cents(J_A, "J_A"), inference._cents(J_B, "J_B"), inference._cents(D, "D")
    p = inference._weights(weights)
    labels = inference._labels(strata, len(a), len(p))
    groups = {s: idx for s, idx in _groups(labels, len(p)).items() if idx}
    d_all = np.array([y - x for x, y in zip(a, b, strict=True)], dtype=np.float64)
    D_all = np.array(h, dtype=np.float64)
    rng = evaluation_generator(entropy)
    draws, t_star, dbar_star = {}, np.zeros(int(B)), np.zeros(int(B))
    for s, idx in groups.items():
        pos = np.array(idx)[rng.integers(0, len(idx), size=(int(B), len(idx)))]
        draws[s] = pos
        w = float(p[s - 1])
        t_star += w * d_all[pos].mean(axis=1)
        dbar_star += w * D_all[pos].mean(axis=1)
    if np.any(dbar_star <= 0):
        raise ValueError(f"{int(np.sum(dbar_star <= 0))} bootstrap resample(s) have D-bar* <= 0: (58) undefined")
    delta_star = t_star / dbar_star
    out = []
    for s in sigma:
        pos = draws[s]
        ups = (d_all[pos] - delta_star[:, None] * D_all[pos]) / dbar_star[:, None]
        sig = ups.std(axis=1, ddof=1)
        if small_sample:  # M5-O31 (c): a resample's SD runs low by about sqrt((N_s - 1) / N_s)
            n = len(groups[s])
            sig = sig * math.sqrt(n / (n - 1))
        sig = np.sort(sig, kind="stable")
        Ds = [h[i] for i in groups[s]]
        sq = sum(v * v for v in Ds)
        out.append(
            SigmaEstimate(
                better=better,
                worse=worse,
                stratum=s,
                n=len(groups[s]),
                sigma=sigma[s],
                se=float(np.std(sig, ddof=1)),
                upper=inverse_cdf(sig, level),
                ess=float(Fraction(sum(Ds) ** 2, sq)) if sq else math.nan,
            )
        )
    return tuple(out)


def _z_factor(alpha: float, n_fam: int, power: float) -> float:
    """(z_{1-alpha/n_fam} + z_power)^2 of (59), one-sided (Q88)."""
    from scipy.stats import norm

    return float((norm.ppf(1 - alpha / n_fam) + norm.ppf(power)) ** 2)


def sample_size(
    sigma_upper: Mapping[int, float],
    *,
    delta_min: float,
    weights=STRATUM_WEIGHTS,
    alpha: float = ALPHA,
    n_fam: int = N_FAM,
    power: float = POWER,
    floor: int = FLOOR,
) -> tuple[int, tuple[int, ...]]:
    """(59): N and the Neyman N_s per stratum from each stratum's sigma upper bound, one-sided z at 1 - alpha/n_fam.

    ``sigma_upper`` maps every stratum label 1..len(weights) to its sigma (V15's ``upper``).

    Raises:
        ValueError: on a missing or extra stratum, a sigma that is negative or not finite, sum_s p_s sigma_s = 0,
            Delta_min not a positive finite number, n_fam < 1, alpha or power outside (0, 1), or a floor < 0.

    """
    p = [float(w) for w in inference._weights(weights)]
    if set(sigma_upper) != set(range(1, len(p) + 1)):
        raise ValueError(f"(59) needs a sigma for each stratum 1..{len(p)}, got {sorted(sigma_upper)}")
    sig = [sigma_upper[s] for s in range(1, len(p) + 1)]
    for v in sig:
        if isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) or v < 0:
            raise ValueError(f"sigma_res,s of (59) must be a finite number >= 0, got {v!r}")
    for name, v in (("delta_min", delta_min), ("alpha", alpha), ("power", power)):
        if isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) or v <= 0:
            raise ValueError(f"{name} of (59) must be a positive finite number, got {v!r}")
    if not alpha < 1 or not power < 1:
        raise ValueError(f"alpha and power lie in (0, 1), got {alpha!r} and {power!r}")
    if isinstance(n_fam, bool) or not isinstance(n_fam, Integral) or n_fam < 1:
        raise ValueError(f"n_fam of (59) must be an integer >= 1, got {n_fam!r}")
    if isinstance(floor, bool) or not isinstance(floor, Integral) or floor < 0:
        raise ValueError(f"the N_s floor must be an integer >= 0, got {floor!r}")
    total = math.fsum(w * s for w, s in zip(p, sig, strict=True))
    if total <= 0:
        raise ValueError("sum_s p_s sigma_s = 0: (59) has no spread to size against")
    N = math.ceil(_z_factor(alpha, n_fam, power) * total**2 / delta_min**2)
    n_s = tuple(max(int(floor), math.ceil(N * w * s / total)) for w, s in zip(p, sig, strict=True))
    return N, n_s


def sizing(estimates: Sequence[SigmaEstimate], *, delta_min: float, size: str, n_fam: int = N_FAM) -> Sizing:
    """(59) over the F-size pairs of one size: N the maximum over pairs, N_s from the binding pair's sigmas.

    Pairs are taken in their first appearance in ``estimates``; a tie in N binds the first. Each pair's sigma is its
    ``upper`` per stratum (V15).

    Raises:
        ValueError: on no estimates, a (pair, stratum) given twice, or as ``sample_size`` (a pair missing a stratum).

    """
    if not estimates:
        raise ValueError("(59) needs V15's estimates for at least one pair")
    by_pair: dict[tuple[str, str], dict[int, float]] = {}
    for e in estimates:
        pair = by_pair.setdefault((e.better, e.worse), {})
        if e.stratum in pair:
            raise ValueError(f"pair {(e.better, e.worse)} has two estimates for stratum {e.stratum}")
        pair[e.stratum] = e.upper
    best = None
    for pair, sig in by_pair.items():
        N, n_s = sample_size(sig, delta_min=delta_min, n_fam=n_fam)
        if best is None or N > best[0]:
            best = (N, n_s, pair)
    N, n_s, pair = best
    return Sizing(float(delta_min), N, n_s, pair, size)


def rank_agreement(scores_a: Mapping[str, float], scores_b: Mapping[str, float]) -> dict:
    """Kendall's tau-b between two sizes' RSS_G rankings of the baselines both score (§4.5: the public board's value).

    A baseline is a run whose base name is in ``registry.BASELINES`` (its variants included); an entry both sizes score
    that is not one, such as the kit's agents (``registry.KIT_AGENTS``, not §8.2 baselines), is left out of tau and
    listed (M5 re-gate SPEC-M5R-03: the M5 pilots' 0.867 ranked the kit agents too). Returns ``{"tau": ..., "n": ...,
    "policies": [...], "not_baselines": [...]}``; tau is None with fewer than 2 common baselines or no variation
    (``scipy.stats.kendalltau``'s NaN), never 0-filled.
    """
    from scipy.stats import kendalltau

    scored = [k for k in scores_a if k in scores_b and scores_a[k] is not None and scores_b[k] is not None]
    common = [k for k in scored if base_name(k) in BASELINES]
    tau = None
    if len(common) >= 2:
        t = kendalltau([scores_a[k] for k in common], [scores_b[k] for k in common]).statistic
        tau = float(t) if math.isfinite(t) else None
    left_out = [k for k in scored if k not in common]
    return {"tau": tau, "n": len(common), "policies": common, "not_baselines": left_out}
