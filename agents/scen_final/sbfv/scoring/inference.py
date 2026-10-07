"""Paired inference between two policies: (58) and the stratified sign-flip test (61) (M4, stream "runner").

Design §7.3; Q62, Q14; with the §7.3 diagnostics; pulled forward from M6, a plan-order deviation recorded in
docs/results.md.

- (58): Delta-hat_AB = sum_s p_s (1/N_s) sum_{n in s} (J^B_n - J^A_n) / D-bar, D-bar = sum_s p_s D-bar_s, and the
  residuals upsilon_n = ((J^B_n - J^A_n) - Delta-hat D_n) / D-bar;
- (61): T_AB = sum_s p_s (1/N_s) sum_{n in s} d_n with d_n = J^B_n - J^A_n, and B sign flips epsilon^(b)_n i.i.d.
  Rademacher, T^(b) the flipped statistic. Two-sided p = (1 + #{b: |T^(b)| >= |T_AB|}) / (B + 1) as (61) writes; the
  one-sided form of the families with a declared direction (§7.3 "Test") is written in design §12 M4 row "One-sided
  (61)": "greater" (H1: A better than B, T_AB > 0) p = (1 + #{b: T^(b) >= T_AB}) / (B + 1), "less" the mirror;
- the flips come from one keyed evaluation stream: ``disruption.gate.evaluation_generator(entropy)`` (PCG64DXSM on a
  fixed evaluation entropy, never an E_split; §4.1 rule table), one (B, N) Rademacher matrix over the episodes in the
  order given (the runner's episode-index order);
- the denominator of (58) is flip-invariant, so (61) tests (58) (§7.3);
- diagnostics beside every interval (§7.3): per stratum ESS (sum D)^2 / sum D^2, the share of sum |upsilon| in the top
  5 episodes, and the sample skewness of upsilon; the skew threshold stays SYNTHETIC (§11) and M4 only reports.

(62), (63), the Holm families and V31 stay in M6. Inputs are integer cents (24); floats and bools are refused as in
``scoring.rss``.
"""

import math
from collections.abc import Sequence
from fractions import Fraction
from numbers import Integral
from typing import Literal

import numpy as np

from sbfv.scoring.rss import STRATUM_WEIGHTS


STREAM = "runner"
B_FLIPS = 20_000  # B of (61), SYNTHETIC protocol constant (§7.3, §11 row 82)
TOP_EPISODES = 5  # the top-5 share of sum |upsilon| (§7.3 diagnostics)
Alternative = Literal["greater", "less", "two-sided"]
ALTERNATIVES = ("greater", "less", "two-sided")
_INT64_EXACT = 1 << 63  # a stratum's sum of |d| below it keeps (61)'s flipped int64 sums exact (``_flipped_sums``)


def _cents(xs: Sequence[int], name: str) -> list[int]:
    """Integer cents (24) as Python ints; floats, booleans and anything else non-integral raise TypeError."""
    out = []
    for x in xs:
        if isinstance(x, bool) or not isinstance(x, Integral):
            raise TypeError(f"{name}: costs must be integer cents (24), got {x!r} of type {type(x).__name__}")
        out.append(int(x))
    return out


def _weights(weights: Sequence[float]) -> list[Fraction]:
    """p_s read as decimals (``Fraction(str(w))``, as ``scoring.rss`` reads them): 0.30 is exactly 3/10."""
    p = [Fraction(str(w)) for w in weights]
    if not p or any(w < 0 for w in p):
        raise ValueError(f"weights must be a non-empty sequence of non-negative numbers, got {tuple(weights)!r}")
    return p


def _labels(strata: Sequence[int], n: int, n_strata: int) -> list[int]:
    """Stratum labels 1..n_strata as Python ints, one per episode."""
    labels = list(strata)
    if len(labels) != n:
        raise ValueError(f"lengths differ: {n} episodes, {len(labels)} stratum labels")
    for s in labels:
        if isinstance(s, bool) or not isinstance(s, Integral) or not 1 <= s <= n_strata:
            raise ValueError(f"stratum label {s!r} is not an integer in 1..{n_strata}")
    return [int(s) for s in labels]


def _stratum_means(values: Sequence[int], labels: Sequence[int], p: Sequence[Fraction]) -> Fraction:
    """sum_s p_s (1/N_s) sum_{n in s} values_n, exactly; a stratum of positive weight must hold an episode."""
    sums, counts = [0] * len(p), [0] * len(p)
    for v, s in zip(values, labels, strict=True):
        sums[s - 1] += v
        counts[s - 1] += 1
    total = Fraction(0)
    for i, w in enumerate(p):
        if w == 0:
            continue
        if counts[i] == 0:
            raise ValueError(f"stratum {i + 1} has weight {w} and no episode (N_s >= 1 required by (58))")
        total += w * Fraction(sums[i], counts[i])
    return total


def _delta(J_A, J_B, D, strata, weights) -> tuple[Fraction, Fraction, list[int], list[int]]:
    """Delta-hat and D-bar of (58) as exact fractions, with the paired differences d_n = J^B_n - J^A_n and D_n."""
    a, b, h = _cents(J_A, "J_A"), _cents(J_B, "J_B"), _cents(D, "D")
    if not len(a) == len(b) == len(h):
        raise ValueError(f"lengths differ: J_A {len(a)}, J_B {len(b)}, D {len(h)}")
    p = _weights(weights)
    labels = _labels(strata, len(a), len(p))
    d = [y - x for x, y in zip(a, b, strict=True)]
    d_bar = _stratum_means(h, labels, p)
    if d_bar <= 0:
        raise ValueError(f"(58) D-bar = sum_s p_s D-bar_s = {float(d_bar)} cents is not positive")
    return _stratum_means(d, labels, p) / d_bar, d_bar, d, h


def delta_hat(
    J_A: Sequence[int], J_B: Sequence[int], D: Sequence[int], strata: Sequence[int], weights=STRATUM_WEIGHTS
) -> float:
    """Delta-hat_AB of (58): the p_s-weighted mean paired saving of A over B, over D-bar.

    Exact in fractions from the integer cents, rounded once to the nearest float.

    Raises:
        TypeError: on a non-integer cent value (bools included).
        ValueError: on unequal lengths, a stratum label outside 1..len(weights), an empty stratum of positive
            weight, or D-bar <= 0.

    """
    return float(_delta(J_A, J_B, D, strata, weights)[0])


def residuals(
    J_A: Sequence[int], J_B: Sequence[int], D: Sequence[int], strata: Sequence[int], weights=STRATUM_WEIGHTS
) -> tuple[float, ...]:
    """upsilon_n of (58), in the order given (as ``delta_hat`` raises): exact, each rounded once to a float."""
    delta, d_bar, d, h = _delta(J_A, J_B, D, strata, weights)
    return tuple(float((dn - delta * Dn) / d_bar) for dn, Dn in zip(d, h, strict=True))


def _flipped_sums(eps: np.ndarray, d: list[int]) -> list[int]:
    """sum_n eps[b, n] d_n for every row b, exact: int64 when sum |d_n| < 2^63, Python integers otherwise.

    Every partial sum of signed terms is bounded by sum |d_n|, so below 2^63 no int64 accumulation can overflow, in any
    order; above it (the loss measure's d on `full` at a large N_s, or any |d_n| past int64) the products and sums are
    Python integers (NumPy object arrays).
    """
    if sum(abs(x) for x in d) < _INT64_EXACT:
        return [int(v) for v in eps.astype(np.int64) @ np.array(d, dtype=np.int64)]
    return [int(v) for v in eps.astype(object) @ np.array(d, dtype=object)]


def sign_flip(
    d: Sequence[int],
    strata: Sequence[int],
    *,
    weights=STRATUM_WEIGHTS,
    B: int = B_FLIPS,
    entropy: int,
    alternative: Alternative = "two-sided",
) -> float:
    """The p-value of the stratified sign-flip test (61), exactly reproducible from ``entropy``.

    Two-sided by default, as (61) writes; one-sided only for a family with a declared direction (§7.3 "Test"): the
    separation report passes "greater" for its §2.6 adjacent pairs.

    The flips are one (B, N) Rademacher matrix epsilon = 2 u - 1, u = ``integers(0, 2, (B, N), int8)`` of
    ``gate.evaluation_generator(entropy)`` (PCG64DXSM on a fixed evaluation entropy, never an E_split), row b the flip
    of T^(b), column n the n-th episode in the order given. The comparison is exact at any magnitude: the per-stratum
    sums S^(b)_s = sum_{n in s} epsilon^(b)_n d_n are exact integers (``_flipped_sums``: int64 when the stratum's
    sum of |d_n| is below 2^63, Python integers otherwise), and T^(b) = sum_s (p_s / N_s) S^(b)_s is compared with T_AB
    as the integer sum_s a_s S^(b)_s, a_s = (p_s / N_s) L with L the least common denominator (Python ints), so the
    identity flip ties T_AB exactly and no float rounding decides a count. A stratum without episodes adds nothing to
    T_AB or T^(b) (design §12 M4 row "(61) arithmetic").

    p lies in [1/(B+1), 1]; d == 0 gives 1 for every alternative.

    Raises:
        TypeError: on a non-integer cent value.
        ValueError: on unequal lengths, B < 1, an unknown alternative, or a stratum label outside 1..len(weights).

    """
    from sbfv.disruption.gate import evaluation_generator

    diffs = _cents(d, "d")
    if isinstance(B, bool) or not isinstance(B, Integral) or B < 1:
        raise ValueError(f"B of (61) must be an integer >= 1, got {B!r}")
    if alternative not in ALTERNATIVES:
        raise ValueError(f"alternative must be one of {ALTERNATIVES}, got {alternative!r}")
    p = _weights(weights)
    labels = _labels(strata, len(diffs), len(p))
    counts = [labels.count(s) for s in range(1, len(p) + 1)]
    coef = [w / n if n else Fraction(0) for w, n in zip(p, counts, strict=True)]
    lcd = math.lcm(*(c.denominator for c in coef))
    a = [int(c * lcd) for c in coef]  # exact integers: T = (sum_s a_s S_s) / lcd
    eps = 2 * evaluation_generator(entropy).integers(0, 2, size=(int(B), len(diffs)), dtype=np.int8) - 1
    lab = np.array(labels, dtype=np.int64)
    t_obs = sum(ai * sum(x for x, s2 in zip(diffs, labels, strict=True) if s2 == s) for s, ai in enumerate(a, start=1))
    t_flip = [0] * int(B)
    for s, ai in enumerate(a, start=1):
        if ai == 0:
            continue
        sums = _flipped_sums(eps[:, lab == s], [x for x, s2 in zip(diffs, labels, strict=True) if s2 == s])
        t_flip = [t + ai * v for t, v in zip(t_flip, sums, strict=True)]
    if alternative == "greater":
        hits = sum(t >= t_obs for t in t_flip)
    elif alternative == "less":
        hits = sum(t <= t_obs for t in t_flip)
    else:
        hits = sum(abs(t) >= abs(t_obs) for t in t_flip)
    return (1 + hits) / (int(B) + 1)


def skew_diagnostics(D: Sequence[int], upsilon: Sequence[float], strata: Sequence[int]) -> dict[int, dict[str, float]]:
    """Per stratum: {"ess": (sum D)^2 / sum D^2, "top5_share": ..., "skewness": ...} of §7.3 (reported, not gated).

    ``top5_share`` is the share of sum |upsilon| in the ``TOP_EPISODES`` largest |upsilon| of the stratum (1 with at
    most five episodes); ``skewness`` the Fisher-Pearson sample skewness g1 = m3 / m2^(3/2) with the biased central
    moments (``scipy.stats.skew``'s default). A quantity whose denominator is 0 (one episode, no spread, sum D^2 = 0)
    is NaN, never a crash. Strata are the labels present, in increasing order.

    Raises:
        ValueError: on unequal lengths.

    """
    if not len(D) == len(upsilon) == len(strata):
        raise ValueError(f"lengths differ: D {len(D)}, upsilon {len(upsilon)}, strata {len(strata)}")
    out: dict[int, dict[str, float]] = {}
    for s in sorted(set(int(x) for x in strata)):
        idx = [i for i, x in enumerate(strata) if int(x) == s]
        h = [int(D[i]) for i in idx]
        u = np.array([float(upsilon[i]) for i in idx], dtype=np.float64)
        sq = sum(v * v for v in h)
        ess = float(Fraction(sum(h) ** 2, sq)) if sq else math.nan
        mag = np.sort(np.abs(u))[::-1]
        total = math.fsum(mag)
        top = math.fsum(mag[:TOP_EPISODES]) / total if total > 0 else math.nan
        dev = u - u.mean()
        m2 = float(np.mean(dev**2))
        skew = float(np.mean(dev**3)) / m2**1.5 if m2 > 0 else math.nan
        out[s] = {"ess": ess, "top5_share": top, "skewness": skew}
    return out
