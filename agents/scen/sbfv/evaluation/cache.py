"""Disk caches of the costly reset-time results: naive's F_Q with its load (69), and the harm cut points of (44).

Moved from the scripts layer (``scripts/python/sbf_boundary.py``, which re-exports every name here) so that the
installed package's local evaluation (``shockbench_flow_agent.evaluate``) and the Hydra entry points share one cache
and one key. Nothing here imports hydra (Q18).

Naive's F_Q is the costly part of a generated run (design §12 row "Generated entry point"), so ``fq_quantiles``
computes it with naive's load (69) in one pass over the replications (``naive_fq.generator_quantiles_and_load``) and
keeps both in a joblib disk cache under ``cache_dir``, keyed by the instance's content digest at its file's own rung
(``Instance.family_digest``, which covers its hash label; F_Q reads no stock, so every rung's instance of one file
shares it; never the label alone, which a ``dataclasses.replace`` variant of other content carries over, DET-M2-3),
``generator_id``, the replication count, the SHA-256 of the package source and the NumPy, SciPy and Python versions
(the generator draws through NumPy, ``scipy.linalg`` and ``scipy.stats``), so a content, code or library change can
never serve a stale F_Q: the same command gives the same trajectory warm or cold, V1. A hit enters ``naive_fq``'s
process cache through ``naive_fq.remember_quantiles``, the package's one trusted seam for quantiles computed elsewhere,
which checks their keys and types but does not recompute them; the load is a diagnostic that naive never reads.
``cut_points_cached`` keeps the cut points of (44) the same way.

Where: the entry points pass ``eval.cache_dir`` (``outputs/cache`` under the project root); the installed package's
default is ``default_cache_dir()``: ``SBF_CACHE_DIR`` when set, else ``~/.cache/shockbench-flow`` (joblib writes under
``<dir>/joblib/``). Never under ``src/``.
"""

import hashlib
import os
import platform
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import scipy

from sbfv.disruption.params import GeneratorParams, generator_id
from sbfv.disruption.strata import CutPoints, cut_points
from sbfv.instance.schema import Instance
from sbfv.policies.naive_fq import generator_quantiles_and_load, remember_quantiles, routed_demand


CACHE_VAR = "SBF_CACHE_DIR"  # the environment variable naming the installed package's cache directory
USER_CACHE = Path("~/.cache/shockbench-flow")  # its default (numba's JIT cache sits beside it, under numba/)


def default_cache_dir() -> Path:
    """The installed package's cache directory: ``SBF_CACHE_DIR`` when set and not empty, else ``~/.cache/...``."""
    raw = os.environ.get(CACHE_VAR, "").strip()
    return Path(raw).expanduser() if raw else USER_CACHE.expanduser()


def package_sha256() -> str:
    """SHA-256 of the package source that runs: every ``*.py`` of ``sbfv`` by relative path and content.

    Part of the F_Q cache key, so an edit of the generator or of naive can never serve quantiles computed by older code
    (``generator_id`` binds the parameters, not the code). The package is located from the imported module, not from
    the project root, so the digest is of the code this process executes (an installed wheel's as a checkout's).
    """
    import sbfv

    pkg = Path(sbfv.__file__).parent
    h = hashlib.sha256()
    for path in sorted(pkg.rglob("*.py")):
        h.update(path.relative_to(pkg).as_posix().encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


FQ_CACHE_IGNORE = ("inst", "params", "n_jobs")  # arguments of ``_fq_compute`` outside the cache key


def fq_cache_key(inst: Instance, params: GeneratorParams, replications: int) -> tuple[str | int, ...]:
    """The F_Q disk-cache key: instance family digest, ``generator_id``, replications, ``package_sha256``, versions.

    The instance enters by its content (``Instance.family_digest``: the V3 content digest, which covers its hash label,
    at the file's own rung, since F_Q reads no stock and every rung's instance of one file shares it; design §12 'Warm
    start per rung'), as in ``naive_fq``'s process cache: F_Q is a function of what the instance holds, and a
    ``dataclasses.replace`` variant of other content keeps the label (DET-M2-3). NumPy, SciPy (the conflict matrix of
    (28) through ``scipy.linalg`` expm and logm, the latent normaliser through ``scipy.stats.norm``) and Python each
    take part in the draws, so a change of any of their versions misses.
    """
    return (
        inst.family_digest,
        generator_id(params, inst),
        replications,
        package_sha256(),
        np.__version__,
        scipy.__version__,
        platform.python_version(),
    )


def _fq_compute(
    instance_digest: str,
    generator: str,
    replications: int,
    package: str,
    numpy_version: str,
    scipy_version: str,
    python_version: str,
    *,
    inst: Instance,
    params: GeneratorParams,
    n_jobs: int,
) -> dict[str, dict]:
    """``naive_fq.generator_quantiles_and_load`` as plain dicts: the function the disk cache memoises.

    The key is the first seven arguments (``fq_cache_key``: instance content digest, ``generator_id``, replications,
    ``package_sha256``, the NumPy, SciPy and Python versions); ``inst``, ``params`` and ``n_jobs`` are ignored by it
    (``FQ_CACHE_IGNORE``), and ``fq_quantiles`` builds the first two from them.

    Returns:
        ``{"quantiles": (c, pool, j, k) -> F_Q quantile, "load": (c, pool) -> the load (69)}``, from one pass.

    """
    quantiles, load = generator_quantiles_and_load(inst, params, replications, n_jobs)
    return {"quantiles": dict(quantiles), "load": dict(load)}


@dataclass(frozen=True)
class FQResult:
    """Naive's F_Q quantiles and load (69) of one generator, and how they came.

    ``quantiles`` has the keys (c, pool, j, k) of ``critical_quantiles``, ``load`` the keys (c, pool) of the pairs a
    lane of naive's plan passes (``naive_fq.naive_load``), both from the same replications.
    """

    quantiles: dict[tuple, float]
    cache: str  # "hit", "miss" (computed and stored) or "off" (computed, no cache)
    seconds: float  # wall time of this call, the lookup included
    load: dict[tuple[int, str], float]  # varrho_cb of (69), >= 1 an overloaded rung (§8.1)


def fq_quantiles(
    inst: Instance, params: GeneratorParams, replications: int, *, n_jobs: int = 1, cache_dir: str | Path | None = None
) -> FQResult:
    """Naive's F_Q quantiles and load (69), ``naive_fq.generator_quantiles_and_load``, disk-cached.

    With ``cache_dir`` a joblib ``Memory`` there memoises them under ``fq_cache_key`` (instance content digest,
    ``generator_id``, replications, ``package_sha256``, the NumPy, SciPy and Python versions): a hit returns the
    pickled floats a miss computed, bit for bit, in any process; ``n_jobs`` only spreads the replications and is not in
    the key. Without it they are computed in this process. Either way the quantiles end in ``naive_fq``'s per-process
    cache (through ``remember_quantiles``, the trusted seam, which refuses a map with other keys or non-float values),
    so ``naive_fq.anchor_policy`` and ``naive_fq.fallback_spec`` of this generator take them and a hit is never
    recomputed in the process. The load is refused unless its keys are the pairs of ``naive_fq.routed_demand``.

    Raises:
        TypeError, ValueError: as ``naive_fq.fq_laws`` (replications not an integer >= 1, gamma not a rung), and
            ValueError on a cached load of other pairs.

    """
    start = time.perf_counter()
    if cache_dir is None:  # generator_quantiles_and_load keeps the quantiles in naive_fq's process cache itself
        q, load = generator_quantiles_and_load(inst, params, replications, n_jobs)
        return FQResult(dict(q), "off", time.perf_counter() - start, dict(load))
    from joblib import Memory

    key = fq_cache_key(inst, params, replications)
    cached = Memory(location=str(cache_dir), verbose=0).cache(_fq_compute, ignore=list(FQ_CACHE_IGNORE))
    kwargs = {"inst": inst, "params": params, "n_jobs": n_jobs}
    hit = cached.check_call_in_cache(*key, **kwargs)
    if not hit:  # loguru imported here: the package imports numpy, scipy and fastjsonschema only at module level
        from loguru import logger

        logger.info(
            "F_Q: {} replications per (chokepoint, pool) for generator {}... (cache miss in {})",
            replications,
            key[1][:12],
            cache_dir,
        )
    record = cached(*key, **kwargs)
    q = dict(remember_quantiles(inst, params, replications, record["quantiles"]))
    load = dict(record["load"])
    if set(load) != set(routed_demand(inst)):
        raise ValueError("the cached load (69) is not keyed by the (chokepoint, pool) pairs of naive's plan")
    return FQResult(q, "hit" if hit else "miss", time.perf_counter() - start, load)


def _cuts_compute(
    instance_digest: str,
    generator: str,
    draws: int,
    entropy: int,
    package: str,
    numpy_version: str,
    scipy_version: str,
    python_version: str,
    *,
    inst: Instance,
    params: GeneratorParams,
    n_jobs: int,
) -> dict:
    """``strata.cut_points`` as a plain dict: the function the cut-point disk cache memoises (``cut_points_cached``)."""
    c = cut_points(inst, params, draws, entropy, n_jobs)
    return {"quantiles": list(c.quantiles), "values": list(c.values), "draws": c.draws, "generator_id": c.generator_id}


def cut_points_cached(
    inst: Instance, params: GeneratorParams, draws: int, entropy: int, n_jobs: int, cache_dir: str | Path | None
) -> CutPoints:
    """The harm cut points of (44) (``strata.cut_points``), disk-cached like naive's F_Q.

    The key is the instance content digest, ``generator_id``, M (``draws``), the cut points' public root, the package
    source and the NumPy, SciPy and Python versions; ``n_jobs`` only spreads the draws. Without ``cache_dir`` they are
    computed in this process. The competition's trusted runner and the local evaluation share it
    (``score_submission.py``, ``eval_submission.py``, ``shockbench_flow_agent.evaluate``), so they compute the strata
    once and alike.
    """
    if cache_dir is None:
        return cut_points(inst, params, draws, entropy, n_jobs)
    from joblib import Memory

    key = (
        inst.content_digest,
        generator_id(params, inst),
        draws,
        entropy,
        package_sha256(),
        np.__version__,
        scipy.__version__,
        platform.python_version(),
    )
    cached = Memory(location=str(cache_dir), verbose=0).cache(_cuts_compute, ignore=list(FQ_CACHE_IGNORE))
    record = cached(*key, inst=inst, params=params, n_jobs=n_jobs)
    return CutPoints(tuple(record["quantiles"]), tuple(record["values"]), record["draws"], record["generator_id"])
