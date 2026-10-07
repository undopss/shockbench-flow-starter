"""The scoring server's limits in one place: what it applies to every submission (``LIMITS``).

``LIMITS`` is the one public record, re-exported as ``shockbench_flow_agent.LIMITS``; the server's task files carry
these values, and the kit's local runs take them as their defaults.

- **Per week**: 10 s of wall clock for a reply (``deadline_s``) and a CPU budget metered from the container
  (``cpu_budget_s``: 2 s on `small`, the Development phase; 4 s on `full`, the Final; `tiny` is not hosted and takes
  the Development budget for local meters). Over either, the week is the naive rule's. No overage bank
  (``bank_seconds`` 0). A reply line is at most ``max_reply_bytes`` (1 MiB).
- **Start-up**: 60 s for the container to start and import ``agent.py`` (``startup_s``), charged to no week;
  ``Agent(config)`` counts toward week 1.
- **Per episode**: a kill timer from the container's start (``episode_timeout_s``), fitted to each phase's execution
  time limit (``fitted_episode_timeout``): 0.9 x 3,000 s / 14 rounds of 15 episodes = 192.9 s on `small` and
  0.9 x 15,000 s / 27 rounds = 500 s on `full`, above the 164 s and 476 s a policy at the whole start-up and CPU
  budgets needs. The weeks after it are the naive rule's.
- **The container** (``ContainerLimits``): one CPU, 4 GB of memory without swap, 128 processes and threads, a 256 MiB
  ``/tmp`` and a 64 MiB ``/dev/shm``, no network, a read-only file system, an unprivileged user.
- **The submission** (``SubmissionLimits``, which the validator ``hosting.submission`` checks with): 500 MiB
  unpacked in all and per file, at most 1,000 files.

The server's task files pin these values, so none moves while the competition runs.
"""

# Sources (docs/decisions.md): the per-week wall clock and CPU meter Q113 (2 s) and Q115 (4 s on `full`), no bank Q113
# reading 2, Agent(config) in week 1 Q113 reading 1, the kill timers Q116, the container Q113 (one CPU, 4 GB, 128 pids),
# the submission Q113 reading 5; the start-up, the reply cap, /tmp and /dev/shm were tagged placeholders until the
# owner settled every limit at the sealed tasks' values on 2026-09-30 (Q117). tests/test_hosting_limits.py holds them
# equal to the sealed tasks of both phases (docs/results.md "Leaderboards sealed": docs/evidence/lb_seal/
# <phase>_summary.json, the wire of each task.json) and to configs/build_codabench_reference.yaml.

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


DEADLINE_S = 10.0  # wall-clock seconds for a week's reply
STARTUP_S = 60.0  # seconds for the container to start and import agent.py
MAX_REPLY_BYTES = 1 << 20  # bytes of one reply line; a longer one is a whole-week failure
BANK_SECONDS = 0.0  # no overage bank: remaining_bank is sent as 0
# CPU seconds per week metered on each hosted task; tiny is not hosted: the Development budget, for local meters
CPU_BUDGET_S = {"tiny": 2.0, "small": 2.0, "full": 4.0}
PHASE_TASKS = {"development": "small", "final": "full"}  # the task each Codabench phase scores
# the task builder's inputs of the kill timer (configs/build_codabench_reference.yaml): each phase's Codabench
# execution time limit and episode count, the worker's episodes in parallel and the share of the limit they may take
EXECUTION_TIME_LIMIT_S = {"development": 3000.0, "final": 15000.0}
PHASE_EPISODES = {"development": 200, "final": 400}
WORKER_EPISODE_JOBS = 15
TIME_LIMIT_SHARE = 0.9
# the submission's size: the owner's "500 MB" as MiB, unpacked, and its file count
MAX_SUBMISSION_BYTES = 500 * 2**20
MAX_SUBMISSION_FILES = 1000
MAX_NAME = 1024  # characters of one member name (not a model value: a sanity bound)
ZIP_OVERHEAD = 76 + 2 * MAX_NAME  # bytes per member a stored zip adds at most (headers and the name twice)
ZIP_END = 22  # bytes of the end-of-central-directory record
_SIZE = re.compile(r"^[1-9][0-9]*[kmg]$")


def stored_zip_bytes(max_bytes: int, max_files: int) -> int:
    """The largest stored zip of ``max_files`` files and ``max_bytes`` unpacked: the bytes plus every header."""
    return max_bytes + max_files * ZIP_OVERHEAD + ZIP_END


def fitted_episode_timeout(
    limit_s: float, episodes: int, jobs: int = WORKER_EPISODE_JOBS, share: float = TIME_LIMIT_SHARE
) -> float:
    """The per-episode kill timer the task builder fits: ``share`` x ``limit_s`` / ceil(``episodes`` / ``jobs``)."""
    return share * limit_s / max(math.ceil(episodes / jobs), 1)


EPISODE_TIMEOUT_S = {
    task: fitted_episode_timeout(EXECUTION_TIME_LIMIT_S[phase], PHASE_EPISODES[phase])
    for phase, task in PHASE_TASKS.items()
}


@dataclass(frozen=True)
class ContainerLimits:
    """The scoring container's resource caps: one CPU, 4 GB without swap, 128 processes, 256 MiB /tmp, 64 MiB shm."""

    cpus: str = "1"  # one CPU (cpu.max)
    memory: str = "4g"  # 4 GB (memory.max); swap off by --memory-swap equal
    pids: int = 128  # processes and threads: a fork bomb stops here
    tmpfs: str = "256m"  # the size cap of the tmpfs /tmp
    shm: str = "64m"  # the private /dev/shm

    def __post_init__(self) -> None:
        """Refuse values docker would read otherwise than meant.

        Raises:
            ValueError: on a CPU count that is not a positive decimal, a size that is not <n>k|m|g, or a pids limit
                that is not an integer >= 1.

        """
        if not re.fullmatch(r"[0-9]+(\.[0-9]+)?", str(self.cpus)) or float(self.cpus) <= 0:
            raise ValueError(f"cpus must be a positive decimal string, got {self.cpus!r}")
        for name in ("memory", "tmpfs", "shm"):
            if not _SIZE.match(str(getattr(self, name))):
                raise ValueError(f"{name} must be a size such as 4g or 256m, got {getattr(self, name)!r}")
        if isinstance(self.pids, bool) or not isinstance(self.pids, int) or self.pids < 1:
            raise ValueError(f"pids must be an integer >= 1, got {self.pids!r}")


@dataclass(frozen=True)
class SubmissionLimits:
    """A submission's archive limits, the scoring server's by default: 500 MiB unpacked, 1,000 files.

    ``max_zip_bytes`` bounds the archive (those files stored, with their headers), ``max_total_bytes`` and
    ``max_file_bytes`` the unpacked bytes of all members and of one, ``max_files`` the entries. ``max_ratio`` is the
    local check's guard against a zip bomb (uncompressed over compressed bytes of one member): the server checks the
    canonical zip it builds from the unpacked folder, which is stored.
    """

    max_zip_bytes: int = stored_zip_bytes(MAX_SUBMISSION_BYTES, MAX_SUBMISSION_FILES)
    max_total_bytes: int = MAX_SUBMISSION_BYTES
    max_file_bytes: int = MAX_SUBMISSION_BYTES
    max_files: int = MAX_SUBMISSION_FILES
    max_ratio: float = 200.0  # a sanity bound (not a model value)


def _frozen(mapping: Mapping) -> Mapping:
    return MappingProxyType(dict(mapping))


@dataclass(frozen=True)
class Limits:
    """What the scoring server applies to every submission (module docstring); ``LIMITS`` holds the hosted values.

    ``cpu_budget_s`` and ``episode_timeout_s`` are read-only mappings by task (``episode_timeout_s`` has the hosted
    tasks only, `small` and `full`); ``phases`` maps each Codabench phase to its task; ``container`` and ``submission``
    are the container's caps and the submission's size. ``task(name)`` gives one task's values as a plain dict, and
    ``as_dict()`` the whole record.
    """

    deadline_s: float = DEADLINE_S
    startup_s: float = STARTUP_S
    max_reply_bytes: int = MAX_REPLY_BYTES
    bank_seconds: float = BANK_SECONDS
    cpu_budget_s: Mapping[str, float] = field(default_factory=lambda: _frozen(CPU_BUDGET_S))
    episode_timeout_s: Mapping[str, float] = field(default_factory=lambda: _frozen(EPISODE_TIMEOUT_S))
    phases: Mapping[str, str] = field(default_factory=lambda: _frozen(PHASE_TASKS))
    container: ContainerLimits = field(default_factory=ContainerLimits)
    submission: SubmissionLimits = field(default_factory=SubmissionLimits)

    def task(self, name: str) -> dict:
        """One task's limits as a plain dict: the per-week, start-up and reply limits, its CPU budget and kill timer.

        ``episode_timeout_s`` is None on a task that is not hosted (`tiny`).

        Raises:
            KeyError: on a task without a CPU budget.

        """
        if name not in self.cpu_budget_s:
            raise KeyError(f"no limits for task {name!r}; tasks: {sorted(self.cpu_budget_s)}")
        return {
            "deadline_s": self.deadline_s,
            "startup_s": self.startup_s,
            "max_reply_bytes": self.max_reply_bytes,
            "bank_seconds": self.bank_seconds,
            "cpu_budget_s": self.cpu_budget_s[name],
            "episode_timeout_s": self.episode_timeout_s.get(name),
        }

    def as_dict(self) -> dict:
        """Every field as plain JSON values (nested dicts for the mappings, the container and the submission)."""
        from dataclasses import asdict

        return {
            "deadline_s": self.deadline_s,
            "startup_s": self.startup_s,
            "max_reply_bytes": self.max_reply_bytes,
            "bank_seconds": self.bank_seconds,
            "cpu_budget_s": dict(self.cpu_budget_s),
            "episode_timeout_s": dict(self.episode_timeout_s),
            "phases": dict(self.phases),
            "container": asdict(self.container),
            "submission": asdict(self.submission),
        }


LIMITS = Limits()

__all__ = [
    "BANK_SECONDS",
    "CPU_BUDGET_S",
    "DEADLINE_S",
    "EPISODE_TIMEOUT_S",
    "LIMITS",
    "MAX_REPLY_BYTES",
    "MAX_SUBMISSION_BYTES",
    "MAX_SUBMISSION_FILES",
    "PHASE_TASKS",
    "STARTUP_S",
    "ContainerLimits",
    "Limits",
    "SubmissionLimits",
    "fitted_episode_timeout",
    "stored_zip_bytes",
]
