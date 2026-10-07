"""Per-step timings of the baselines, the inputs to Q13 (milestone M4, stream "runner").

Design §2.6 "Budgets", §8.2 "MPC horizon", §9.7; Q13.

Readings (design §12 M4 row "Runner"): in-process wall (``time.perf_counter``) and CPU (``time.process_time``) time of
``policy.reset`` and of each ``policy.act``, nothing else of the episode, from a serial pass (n_jobs = 1), cold resets
(a fresh process: empty ``naive._PLANS`` and scenario caches) reported apart from warm ones, since each hosted episode
is a fresh container. Cold resets are seeded: F_Q's quantiles arrive in ``PolicyContext`` and sz's transient paths are
put in with ``sz_state_base_stock.remember_paths`` before the timed reset, so no reset times F_Q or the paths (both
computed once per instance and generator, never per episode; a wire child reads the paths from its parent's file,
``PolicyContext.paths_file``, which the timed reset does not include: INT-M4-02); the machine record (platform, CPU
count, load average, versions, the image digest when ``SBF_IMAGE_DIGEST`` is set) beside every table. Timings are
outside every hash (V1) and M4 sets no budget: Q13 stays with the owner. Heavy timing passes run on the worker VM
(``scripts/bash/vm_run.sh``), whose platform the table states; macOS arm64 figures are secondary.

How a reset is timed (design §12 row "Timings" under the head row "M4 stream runner"): the policy's reset runs on the
week-1 observation and Static of an ``Env`` reset without a fallback, so no naive plan (22) is solved for the D9
fallback before it (in a hosted episode the fallback lives in the runner's process, never in the policy's); the episode
then runs in an ``Env`` with the episode's fallback, whose week-1 observation is the same, so the trajectory is
``rollout``'s bit for bit. ``StepTimings.cold`` is True for the first timed reset of the process; ``runner.timing_pass``
runs each cold measurement in a fresh interpreter left as a fresh policy container finds it (design §9.4: one container
per episode, a read-only root and a fresh tmpfs ``/tmp``): omega is drawn by the parent and handed over, so no generator
draw runs in the timed process before the reset, and numba's cache is an empty directory (``fresh_numba_cache``), so a
reset that draws from the generator (the scenario libraries) pays the numba kernels' compile, as a container does.
``StepTimings.kernels_built`` records whether the generator kernels were already built in the process when the reset
started (never on a cold reset of the fresh pass; M4 gate CMP-M4-01).
"""

import importlib.metadata
import os
import platform
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from sbfv.dynamics.env import Env
from sbfv.dynamics.state import Trajectory
from sbfv.policies.base import reset_policy


IMAGE_DIGEST_VAR = "SBF_IMAGE_DIGEST"  # the pinned image's digest, recorded when a run happens inside it (V24)
QUANTILES = (0.5, 0.95)  # the table's median and p95, beside the maximum
VERSIONED = ("numpy", "scipy", "highspy", "numba", "joblib", "shockbench-flow")  # distributions the record names
_TIMED_RESETS = [0]  # timed resets in this process: the first is cold (module docstring)
KERNELS_MODULE = "sbfv.omega._kernels"  # the generator's numba kernels (built lazily, on the first draw)
CACHE_DIR_VAR = "NUMBA_CACHE_DIR"  # numba's cache directory (as ``omega._kernels.CACHE_DIR_VAR``)


@dataclass(frozen=True)
class StepTimings:
    """One episode's policy times in seconds; outside every hash."""

    reset_wall_s: float
    reset_cpu_s: float
    act_wall_s: tuple[float, ...]  # one per week, in week order
    act_cpu_s: tuple[float, ...]
    cold: bool  # the reset ran in a fresh process (empty per-process caches)
    kernels_built: bool = False  # the generator's numba kernels were already built here when the reset started


def kernels_built() -> bool:
    """Whether the generator's numba kernels are built and in use in this process (``omega._kernels.AVAILABLE``).

    Reads the module only if a draw has imported it, so asking imports nothing.
    """
    mod = sys.modules.get(KERNELS_MODULE)
    return bool(mod is not None and mod.AVAILABLE)


def fresh_numba_cache(path) -> None:
    """Point numba's cache at ``path`` (an empty directory) in this process, before any generator kernel is built.

    A fresh policy container compiles the kernels on its first generator draw (its ``/tmp`` is a new tmpfs, design
    §9.4); a reset timed after this call does the same. Sets ``NUMBA_CACHE_DIR``, which numba reads when it is imported
    (the kernel builder imports it lazily), and numba's ``config.CACHE_DIR`` too if numba is already imported.

    Raises:
        RuntimeError: if the kernels are already built in this process (a reset timed here would not pay the compile).

    """
    if kernels_built():
        raise RuntimeError("the generator kernels are already built in this process: its reset cannot be timed cold")
    os.environ[CACHE_DIR_VAR] = str(path)
    config = sys.modules.get("numba.core.config")
    if config is not None:
        config.CACHE_DIR = str(path)


def timed_rollout(
    instance, policy, omega, regime, policy_seed: int, *, marks=None, fallback="naive"
) -> tuple[Trajectory, StepTimings]:
    """``dynamics.env.rollout`` with the policy's reset and act timed; the trajectory hash equals ``rollout``'s.

    The loop mirrors ``rollout`` exactly (``reset_policy``, one ``env.step(policy.act(obs))`` per week) and times only
    the two policy calls, so no environment time enters a step's figure. The reset is timed on the observation of a
    fallback-free ``Env`` reset (module docstring), equal to the episode's own week-1 observation.
    """
    name = getattr(policy, "name", "")
    # builds no naive plan (a hosted episode's D9 fallback lives in the runner's process); F_Q and sz's paths are seeded
    # (module docstring), so sz's reset here excludes the paths file a wire child reads (INT-M4-02; results.md, M4)
    probe = Env(fallback=None)
    obs0, info0 = probe.reset(instance, regime, omega, policy_seed, marks=marks, policy_name=name)
    cold = _TIMED_RESETS[0] == 0
    _TIMED_RESETS[0] += 1
    built = kernels_built()
    w0, c0 = time.perf_counter(), time.process_time()
    reset_policy(policy, info0["static"], obs0, policy_seed, info0.get("omega"))
    reset_wall, reset_cpu = time.perf_counter() - w0, time.process_time() - c0
    env = Env(fallback=fallback)
    obs, _info = env.reset(instance, regime, omega, policy_seed, marks=marks, policy_name=name)
    walls, cpus, done = [], [], False
    while not done:
        w0, c0 = time.perf_counter(), time.process_time()
        action = policy.act(obs)
        walls.append(time.perf_counter() - w0)
        cpus.append(time.process_time() - c0)
        obs, _reward, done, _truncated, _step = env.step(action)
    return env.trajectory, StepTimings(reset_wall, reset_cpu, tuple(walls), tuple(cpus), cold, built)


def installed_version(dist: str) -> str | None:
    """The installed version of distribution ``dist`` from its metadata (nothing imported); None if not installed."""
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return None


def machine_record() -> dict:
    """Platform, machine, CPU count, 1/5/15-minute load, the versions (Python, NumPy, SciPy, highspy, numba, package).

    The digest is ``os.environ[IMAGE_DIGEST_VAR]`` when set, else None; no value enters a hash. Versions come from the
    installed distributions' metadata, so recording them imports neither highspy nor numba.
    """
    try:
        load = [float(x) for x in os.getloadavg()]
    except OSError:  # no load average on this platform
        load = None
    return {
        "system": platform.system(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "load_avg": load,
        "python": platform.python_version(),
        "versions": {d: installed_version(d) for d in VERSIONED},
        "image_digest": os.environ.get(IMAGE_DIGEST_VAR) or None,
    }


def _quantile(values: Sequence[float], p: float) -> float:
    """The smallest sample x with F(x) >= p (``disruption.strata.inverse_cdf``, the package's one quantile rule)."""
    from sbfv.disruption.strata import inverse_cdf

    return inverse_cdf(np.sort(np.asarray(values, dtype=np.float64)), p)


def _stats(prefix: str, values: Sequence[float]) -> dict:
    out: dict = {f"{prefix}_n": len(values)}
    for q in QUANTILES:
        out[f"{prefix}_p{round(q * 100)}"] = _quantile(values, q) if values else None
    out[f"{prefix}_max"] = max(values) if values else None
    return out


def timing_table(timings: Sequence[tuple[str, str, StepTimings]]) -> list[dict]:
    """Per (policy, rung) rows: median, p95 and maximum of act wall and CPU seconds, reset times, cold and warm apart.

    ``timings`` holds (policy, rung label, StepTimings) triples; rows are sorted by policy in ``registry.BASELINES``
    order, then rung. One row per (policy, rung, cold), cold first: a cold row's act figures are the weeks of the
    episodes whose reset was cold; the quantile rule is ``disruption.strata.inverse_cdf`` (``_p50`` the median). Each
    row carries the report label (``results.label``): ``hindsight_consensus`` is "not budget-compliant" here as in every
    report (design §8.2; §12 row "``hindsight_consensus`` (M4 reading)"); ``kernels_prebuilt`` counts the row's resets
    that found the generator kernels already built (``StepTimings.kernels_built``; 0 on every cold row of the fresh
    pass, so a reset that draws from the generator holds the compile).
    """
    from sbfv.evaluation.results import label, policy_order

    groups: dict[tuple[str, str, bool], list[StepTimings]] = {}
    for policy, rung, t in timings:
        groups.setdefault((policy, rung, t.cold), []).append(t)
    rows = []
    for (policy, rung, cold), ts in sorted(
        groups.items(), key=lambda kv: (policy_order(kv[0][0]), kv[0][1], not kv[0][2])
    ):
        row = {"policy": policy, "label": label(policy), "rung": rung, "cold": cold, "episodes": len(ts)}
        row["kernels_prebuilt"] = sum(t.kernels_built for t in ts)  # resets that found the kernels built (cold: 0)
        row |= _stats("reset_wall", [t.reset_wall_s for t in ts]) | _stats("reset_cpu", [t.reset_cpu_s for t in ts])
        row |= _stats("act_wall", [x for t in ts for x in t.act_wall_s])
        row |= _stats("act_cpu", [x for t in ts for x in t.act_cpu_s])
        rows.append(row)
    return rows
