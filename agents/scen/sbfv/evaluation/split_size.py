"""Split sizes from per-episode results: the standard error of RSS_G (56) and of paired gaps at any N_s (design §7.3).

The derivation and its validation on the hackathon board's episodes are in docs/099-split-variance.md; the evidence is
``scripts/python/evidence/split_variance.py`` (``docs/evidence/split_variance.txt``).

- An entry's RSS_G (56) is Delta-hat of (58) for the pair (A, B) = (the entry, naive), and a paired gap
  RSS_G(a) - RSS_G(b) on the same episodes is Delta-hat for (A, B) = (a, b); both are one ratio of stratified means.
- First order, (60): Var = sum_s p_s^2 sigma_s^2 / N_s, sigma_s = SD_{n in s}(upsilon_n) of (58) (ddof 1).
- Second order (the ratio's denominator noise): with CV^2 = sum_s p_s^2 c_s^2 / N_s, c_s = SD_s(D) / D-bar,
  C = sum_s p_s^2 k_s / N_s, k_s = Cov_s(upsilon, D) / D-bar, and K = sum_s p_s^3 m_s / N_s^2,
  m_s = mean_s[(upsilon - upsilon-bar_s)^2 (D - D-bar_s)] / D-bar,
  Var = V1 (1 + 3 CV^2) + 5 C^2 - 2 K, the expansion of L / (1 + delta) to O(N^-2) (docs/099 §2). The bias of the
  ratio is -C to O(1/N).
- Sizes: equal N_s = n, the smallest with SE <= target; Neyman N_s = max(floor, ceil(N p_s sigma_s / sum p sigma)),
  N the smallest with SE <= target. A gap Delta is resolved at power 1 - beta by a one-sided level-alpha test when
  SE <= |Delta| / (z_{1-alpha} + z_{1-beta}). At ``order=1`` with Neyman allocation, alpha = 0.05 / n_fam, power 0.8
  and floor 20 this is (59) (``evaluation.pilot.sample_size``).

Inputs are integer cents (24), as ``scoring.inference``; the moments are floats.
"""

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from numbers import Integral, Real

import numpy as np

from sbfv.scoring import inference
from sbfv.scoring.rss import STRATUM_WEIGHTS


ALLOCATIONS = ("equal", "neyman")


@dataclass(frozen=True)
class Spread:
    """The per-stratum moments of one statistic, from which its standard error at any N_s follows (module docstring).

    ``kind`` is "entry" (RSS_G (56) of one policy, the pair (policy, naive)) or "gap" (RSS_G(a) - RSS_G(b) on the same
    episodes). Per-stratum tuples run over the strata 1..len(weights); a stratum of weight 0 without episodes holds 0.
    """

    label: str
    kind: str
    estimate: float  # RSS_G (56), or the gap Delta-hat_ab of (58)
    weights: tuple[float, ...]
    n: tuple[int, ...]  # episodes per stratum the moments were measured on
    sigma: tuple[float, ...]  # SD_s(upsilon) of (58), ddof 1: (60)'s sigma_res,s
    cv: tuple[float, ...]  # SD_s(D) / D-bar, ddof 1
    cov: tuple[float, ...]  # Cov_s(upsilon, D) / D-bar, ddof 1
    m21: tuple[float, ...]  # mean_s[(upsilon - mean)^2 (D - mean)] / D-bar


@dataclass(frozen=True)
class Episodes:
    """Per-episode costs in integer cents, every policy on the same episodes: the tool's input (``from_summary``)."""

    strata: tuple[int, ...]
    J_naive: tuple[int, ...]
    J_oracle: tuple[int, ...]
    J: Mapping[str, tuple[int, ...]]  # policy -> J^pi_n, in the order of ``strata``
    skipped: Mapping[str, str]  # policy -> why it has no row (a failed or missing run)


def spread(
    J_A: Sequence[int],
    J_B: Sequence[int],
    D: Sequence[int],
    strata: Sequence[int],
    *,
    label: str,
    kind: str = "gap",
    weights: Sequence[float] = STRATUM_WEIGHTS,
) -> Spread:
    """The moments of Delta-hat_AB of (58) for the pair (A, B): an entry is (J^pi, J^naive), a gap a - b is (J^a, J^b).

    Raises:
        TypeError, ValueError: as ``inference.residuals``; a ValueError also for an unknown ``kind`` or a stratum of
            positive weight with fewer than 2 episodes (its SD is undefined).

    """
    if kind not in ("entry", "gap"):
        raise ValueError(f"kind must be 'entry' or 'gap', got {kind!r}")
    ups = np.array(inference.residuals(J_A, J_B, D, strata, weights), dtype=np.float64)
    estimate = inference.delta_hat(J_A, J_B, D, strata, weights)
    p = [float(w) for w in inference._weights(weights)]
    labels = np.array(inference._labels(strata, len(ups), len(p)))
    h = np.array(inference._cents(D, "D"), dtype=np.float64)
    groups = [np.flatnonzero(labels == s) for s in range(1, len(p) + 1)]
    d_bar = math.fsum(w * h[g].mean() for w, g in zip(p, groups, strict=True) if w)
    n, sigma, cv, cov, m21 = [], [], [], [], []
    for s, (w, g) in enumerate(zip(p, groups, strict=True), start=1):
        n.append(len(g))
        if w == 0 and len(g) == 0:
            moments = (0.0, 0.0, 0.0, 0.0)
        elif len(g) < 2:
            raise ValueError(f"stratum {s} holds {len(g)} episode(s): its SD needs at least 2")
        else:
            u, x, k = ups[g] - ups[g].mean(), h[g] - h[g].mean(), len(g) - 1
            moments = (
                math.sqrt(np.sum(u * u) / k),
                math.sqrt(np.sum(x * x) / k) / d_bar,
                float(np.sum(u * x)) / k / d_bar,
                float(np.mean(u * u * x)) / d_bar,
            )
        for acc, v in zip((sigma, cv, cov, m21), moments, strict=True):
            acc.append(float(v))
    return Spread(label, kind, estimate, tuple(p), tuple(n), tuple(sigma), tuple(cv), tuple(cov), tuple(m21))


def _sizes(n: int | Sequence[int], sp: Spread) -> tuple[int, ...]:
    """N_s per stratum from one common n or a sequence; every stratum of positive weight needs N_s >= 1."""
    ns = (n,) * len(sp.weights) if isinstance(n, Integral) and not isinstance(n, bool) else tuple(n)
    if len(ns) != len(sp.weights):
        raise ValueError(f"{len(ns)} sizes for {len(sp.weights)} strata")
    for k, w in zip(ns, sp.weights, strict=True):
        if isinstance(k, bool) or not isinstance(k, Integral) or k < (1 if w else 0):
            raise ValueError(f"N_s must be an integer >= 1 in every stratum of positive weight, got {ns!r}")
    return tuple(int(k) for k in ns)


def variance_terms(sp: Spread, n: int | Sequence[int]) -> dict[str, float]:
    """V1 of (60), CV^2 of D-bar, C and K at N_s = ``n`` (module docstring), over the strata of positive weight."""
    ns = _sizes(n, sp)
    live = [i for i, w in enumerate(sp.weights) if w]
    p = sp.weights
    return {
        "V1": math.fsum(p[i] ** 2 * sp.sigma[i] ** 2 / ns[i] for i in live),
        "CV2": math.fsum(p[i] ** 2 * sp.cv[i] ** 2 / ns[i] for i in live),
        "C": math.fsum(p[i] ** 2 * sp.cov[i] / ns[i] for i in live),
        "K": math.fsum(p[i] ** 3 * sp.m21[i] / ns[i] ** 2 for i in live),
    }


def se(sp: Spread, n: int | Sequence[int], *, order: int = 2) -> float:
    """The standard error of the statistic at N_s = ``n`` (one int for every stratum, or one per stratum).

    ``order=1`` is (60); ``order=2`` adds the ratio's second-order terms, V1 (1 + 3 CV^2) + 5 C^2 - 2 K; NaN if that
    is not positive.

    Raises:
        ValueError: on an order other than 1 or 2, or sizes as ``_sizes`` refuses them.

    """
    if order not in (1, 2):
        raise ValueError(f"order must be 1 or 2, got {order!r}")
    t = variance_terms(sp, n)
    v = t["V1"] if order == 1 else t["V1"] * (1 + 3 * t["CV2"]) + 5 * t["C"] ** 2 - 2 * t["K"]
    return math.sqrt(v) if v > 0 else (0.0 if v == 0 else math.nan)


def neyman(sp: Spread, total: int, *, floor: int = 0) -> tuple[int, ...]:
    """Neyman N_s = max(floor, 1, ceil(total p_s sigma_s / sum p sigma)) as (59), 0 in a stratum of weight 0.

    Raises:
        ValueError: on sum_s p_s sigma_s = 0 (nothing to allocate by), a total < 1 or a floor < 0.

    """
    if isinstance(total, bool) or not isinstance(total, Integral) or total < 1:
        raise ValueError(f"total must be an integer >= 1, got {total!r}")
    if isinstance(floor, bool) or not isinstance(floor, Integral) or floor < 0:
        raise ValueError(f"floor must be an integer >= 0, got {floor!r}")
    ps = math.fsum(w * s for w, s in zip(sp.weights, sp.sigma, strict=True))
    if ps <= 0:
        raise ValueError(f"{sp.label}: sum_s p_s sigma_s = 0, Neyman allocation is undefined")
    return tuple(
        max(floor, 1, math.ceil(total * w * s / ps)) if w else 0 for w, s in zip(sp.weights, sp.sigma, strict=True)
    )


def _smallest(m0: int, ok: Callable[[int], bool]) -> int:
    """The smallest m >= m0 with ok(m), by doubling then bisection (ok is taken as monotone above m0)."""
    if ok(m0):
        return m0
    lo, step = m0, 1
    while not ok(lo + step):
        lo, step = lo + step, 2 * step
        if step > 2**40:
            raise ValueError("no size meets the target (the second-order variance does not fall with N)")
    hi = lo + step
    while hi - lo > 1:
        mid = (lo + hi) // 2
        lo, hi = (lo, mid) if ok(mid) else (mid, hi)
    return hi


def size_for_se(
    sp: Spread, target: float, *, allocation: str = "equal", floor: int = 0, order: int = 2
) -> tuple[int, ...]:
    """The smallest N_s per stratum with ``se(sp, N_s, order=order) <= target``.

    "equal": one n for every stratum of positive weight (at least ``floor``); "neyman": ``neyman(sp, N, floor)`` at
    the smallest N. At ``order=1`` both are closed forms, n = ceil(sum p^2 sigma^2 / target^2) and
    N = ceil((sum p sigma)^2 / target^2), taken as they are (no float re-check at the boundary, so (59) is reproduced
    exactly); ``order=2`` searches upward from them.

    Raises:
        ValueError: on a target that is not a positive finite number, an unknown allocation, or as ``neyman``.

    """
    if isinstance(target, bool) or not isinstance(target, Real) or not math.isfinite(target) or target <= 0:
        raise ValueError(f"target must be a positive finite number, got {target!r}")
    if allocation not in ALLOCATIONS:
        raise ValueError(f"allocation must be one of {ALLOCATIONS}, got {allocation!r}")
    p, sig = sp.weights, sp.sigma
    if allocation == "equal":
        v = math.fsum(w * w * s * s for w, s in zip(p, sig, strict=True))
        n0 = max(int(floor), 1, math.ceil(v / target**2))

        def shape(m: int) -> tuple[int, ...]:
            return tuple(m if w else 0 for w in p)
    else:
        ps = math.fsum(w * s for w, s in zip(p, sig, strict=True))
        n0 = max(1, math.ceil(ps**2 / target**2)) if ps > 0 else 1

        def shape(m: int) -> tuple[int, ...]:
            return neyman(sp, m, floor=floor)

    if order == 1:
        return shape(n0)
    return shape(_smallest(n0, lambda m: se(sp, shape(m), order=order) <= target))


def z_factor(alpha: float, power: float) -> float:
    """z_{1-alpha} + z_power: a gap is resolved (one-sided level alpha, that power) when SE <= |Delta| / this."""
    from scipy.special import ndtri

    for name, v in (("alpha", alpha), ("power", power)):
        if isinstance(v, bool) or not isinstance(v, Real) or not 0 < v < 1:
            raise ValueError(f"{name} must lie in (0, 1), got {v!r}")
    return float(ndtri(1 - alpha) + ndtri(power))


def size_for_gap(
    sp: Spread,
    delta: float,
    *,
    alpha: float = 0.05,
    power: float = 0.80,
    allocation: str = "equal",
    floor: int = 0,
    order: int = 2,
) -> tuple[int, ...]:
    """N_s per stratum at which a true gap ``delta`` is found by a one-sided level-``alpha`` test with ``power``.

    Normal approximation, SE <= |delta| / (z_{1-alpha} + z_power); (59) is ``alpha = 0.05 / n_fam``, power 0.8,
    Neyman, floor 20, ``order=1``.

    Raises:
        ValueError: on delta = 0 or not finite, alpha or power outside (0, 1), or as ``size_for_se``.

    """
    if isinstance(delta, bool) or not isinstance(delta, Real) or not math.isfinite(delta) or delta == 0:
        raise ValueError(f"delta must be a non-zero finite number, got {delta!r}")
    target = abs(delta) / z_factor(alpha, power)
    return size_for_se(sp, target, allocation=allocation, floor=floor, order=order)


def from_summary(summary: Mapping, regime: str) -> Episodes:
    """The episodes of a ``run_eval.py`` or ``run_pilot.py`` summary under one regime: its ``rows`` and ``runs``.

    Episodes whose row is ``excluded`` (§6.3) are dropped for every policy; a policy with a failed run, or no run, on
    a kept episode is left out and named in ``skipped``. Episodes are in the rows' order.

    Raises:
        ValueError: on a (policy, episode) with two runs under the regime, or no kept episode.

    """
    rows = [r for r in summary["rows"] if r.get("excluded") is None]
    if not rows:
        raise ValueError("the summary holds no kept episode")
    by_policy: dict[str, dict[int, Mapping]] = {}
    for run in summary["runs"]:
        if run["regime"] != regime:
            continue
        runs = by_policy.setdefault(run["policy"], {})
        if run["episode"] in runs:
            raise ValueError(f"policy {run['policy']!r} has two runs on episode {run['episode']} under {regime!r}")
        runs[run["episode"]] = run
    J, skipped = {}, {}
    for policy, runs in by_policy.items():
        bad = [r["episode"] for r in rows if r["episode"] not in runs or runs[r["episode"]].get("failed")]
        if bad:
            skipped[policy] = f"no run or a failed run on {len(bad)} kept episode(s), first {bad[0]}"
            continue
        J[policy] = tuple(int(runs[r["episode"]]["J_cents"]) for r in rows)
    return Episodes(
        strata=tuple(int(r["stratum"]) for r in rows),
        J_naive=tuple(int(r["J_naive_cents"]) for r in rows),
        J_oracle=tuple(int(r["J_oracle_cents"]) for r in rows),
        J=J,
        skipped=skipped,
    )


def spreads(
    ep: Episodes,
    *,
    entries: Sequence[str] | None = None,
    pairs: Sequence[tuple[str, str]] = (),
    weights: Sequence[float] = STRATUM_WEIGHTS,
) -> tuple[Spread, ...]:
    """One ``Spread`` per entry (RSS_G (56) against naive; all of ``ep.J`` by default) and per gap a - b in ``pairs``.

    Raises:
        KeyError: on a policy not in ``ep.J``.
        TypeError, ValueError: as ``spread``.

    """
    D = [a - b for a, b in zip(ep.J_naive, ep.J_oracle, strict=True)]
    out = [
        spread(ep.J[e], ep.J_naive, D, ep.strata, label=e, kind="entry", weights=weights)
        for e in (ep.J if entries is None else entries)
    ]
    out += [spread(ep.J[a], ep.J[b], D, ep.strata, label=f"{a} - {b}", weights=weights) for a, b in pairs]
    return tuple(out)


def _cell(size: Callable[[], tuple[int, ...]]) -> str:
    """A table cell: "total (n each)" for equal sizes, "total (N_1/.../N_S)" otherwise, "-" where undefined."""
    try:
        ns = size()
    except ValueError:
        return "-"
    live = {k for k in ns if k}
    each = f"{next(iter(live)):,} each" if len(live) == 1 else "/".join(str(k) for k in ns)
    return f"{sum(ns):,} ({each})"


def plan(
    rows: Sequence[Spread],
    *,
    sizes: Sequence[int] = (5, 10, 25, 50, 100, 200, 400),
    targets: Sequence[float] = (0.05, 0.02, 0.01),
    gaps: Sequence[float] = (0.10, 0.05),
    alpha: float = 0.05,
    power: float = 0.80,
    floor: int = 0,
    order: int = 2,
) -> str:
    """The sizing tables in Markdown: SE against n per stratum, the sizes for each target SE, the sizes for each gap.

    1. per statistic: its estimate, sigma_s, and the SE at n per stratum for each of ``sizes`` (equal allocation), with
       CV(D-bar) at each n in the first row and SE_order / SE_1 at the smallest size in the last column;
    2. per statistic and target SE: the equal and the Neyman sizes (``size_for_se``), each as "total (N_s)";
    3. per gap and Delta (the gap's own |estimate| first, then ``gaps``): the sizes at which a one-sided level-alpha
       test finds Delta with ``power`` (``size_for_gap``), equal and Neyman.

    Raises:
        ValueError: on no rows, or as ``se`` and ``size_for_se``.

    """
    if not rows:
        raise ValueError("plan needs at least one Spread")
    out = [
        f"| statistic | estimate | sigma_s ({'/'.join(str(i + 1) for i in range(len(rows[0].weights)))}) | "
        + " | ".join(f"n={n}" for n in sizes)
        + f" | SE{order}/SE1 at n={sizes[0]} |",
        "| --- | --- | --- | " + " | ".join("---" for _ in sizes) + " | --- |",
        "| CV(D-bar), the denominator's noise | - | - | "
        + " | ".join(f"{math.sqrt(variance_terms(rows[0], n)['CV2']):.3f}" for n in sizes)
        + " | - |",
    ]
    for sp in rows:
        ses = [se(sp, n, order=order) for n in sizes]
        first = se(sp, sizes[0], order=1)
        sig = "/".join(f"{s:.3f}" for s in sp.sigma)
        out.append(
            f"| {sp.label} | {sp.estimate:+.4f} | {sig} | "
            + " | ".join(f"{x:.4f}" for x in ses)
            + f" | {ses[0] / first if first > 0 else math.nan:.3f} |"
        )
    out += [
        "",
        "Sizes as total episodes (per stratum).",
        "",
        "| statistic | " + " | ".join(f"SE <= {t}: equal | SE <= {t}: Neyman" for t in targets) + " |",
        "| --- | " + " | ".join("--- | ---" for _ in targets) + " |",
    ]
    for sp in rows:
        cells = [
            _cell(lambda t=t, a=a: size_for_se(sp, t, allocation=a, floor=floor, order=order))
            for t in targets
            for a in ALLOCATIONS
        ]
        out.append(f"| {sp.label} | " + " | ".join(cells) + " |")
    gap_rows = [sp for sp in rows if sp.kind == "gap"]
    if gap_rows:
        out += [
            "",
            f"Resolving a gap Delta: one-sided level {alpha}, power {power}; sizes as total episodes (per stratum).",
            "",
            "| gap | Delta | equal | Neyman |",
            "| --- | --- | --- | --- |",
        ]
        for sp in gap_rows:
            for d in (abs(sp.estimate), *gaps):
                if d == 0:
                    continue
                cells = [
                    _cell(
                        lambda a=a, d=d: size_for_gap(
                            sp, d, alpha=alpha, power=power, allocation=a, floor=floor, order=order
                        )
                    )
                    for a in ALLOCATIONS
                ]
                tag = f"{d:.4f} (observed)" if d == abs(sp.estimate) else f"{d}"
                out.append(f"| {sp.label} | {tag} | " + " | ".join(cells) + " |")
    return "\n".join(out)
