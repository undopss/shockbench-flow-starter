"""The policy container's CPU, week by week, read outside it (Q113; design §12 "CPU metering (Codabench)").

The owner's rule for the Codabench deployment (Q113, "Meter CPU from the cgroup"): the runner reads the policy
container's cgroup CPU usage before and after each week, outside the agent's reach; a week over its budget (the
task's ``cpu_budget_s``: 2 s on the Development phase, 4 s on the Final, Q115) is played by the D9 fallback and
counted, and a wall-clock cap (the wire's per-week deadline, 10 s) stops hangs. Two readers of one container's
cumulative CPU seconds:

- ``cgroup``: the container's accounting file under the Docker host's cgroup tree, which the Codabench worker mounts
  read-only into the ingestion container (``CGROUP_ROOT_VAR``, default ``DEFAULT_CGROUP_ROOT``): ``cpu.stat``'s
  ``usage_usec`` on cgroup v2, ``cpuacct.usage`` (nanoseconds) on v1 (``read_usage_s``), found by
  ``container_cgroup`` under the systemd layout (``system.slice/docker-<id>.scope``), the cgroupfs layout
  (``docker/<id>``) or a bounded walk. One file read per look.
- ``docker_stats``: the Docker API's one-shot stats (``GET /containers/<id>/stats?stream=false&one-shot=true``) over
  the daemon's unix socket, ``cpu_stats.cpu_usage.total_usage`` in nanoseconds (``DockerStats``, standard library
  HTTP on one keep-alive connection). On cgroup v2 the daemon reads the same ``usage_usec``; a look costs a round trip
  through the daemon, which gathers every other statistic too.

Both count every process of the container (a ``setsid`` worker, a thread, the shim's own conversions), which a
per-pid count misses (§9.4 'Time enforcement', F2). The measured cost of a look, and the readings compared, are in
``docs/evidence/codabench_metering.txt`` (``scripts/bash/evidence/codabench_metering.sh``).

**The week rule** (``WeekCpu``, the runner's ``information.runner.WeekMeter``). ``start`` reads the usage once the
Reset is sent; ``end_week(t)`` reads it after week t's read, and week t's CPU is that reading minus the last one, so
every CPU second after the Reset is charged to some week, whatever runs when: work between two weeks (a thread busy
while the runner steps the environment, an ``act`` still running after its deadline) is charged to the next week. No
cgroup freeze between weeks is needed for the account (§9.4 planned one; F2 measured a median 64 ms per freeze and
thaw through the CLI, 6.7 s per 104-week episode). ``interrupt`` is polled by the transport while a week waits
(``SubprocessTransport.interrupt``, every ``POLL_S[method]`` seconds): a week whose CPU passes the budget ends at once,
so a busy agent costs the budget's wall time per week, not the deadline's. A failed read never ends a week early and
makes ``end_week`` true (fails closed); a meter that cannot start (no accounting file for a container that is up) is
the organiser's failure, which the ingestion reports (``hosting.codabench``) instead of scoring every week as 'cpu'.
The Reset's own reading and the Request of week 1 are the start: the container's start-up, the interpreter, the
imports, the kit's once-per-process work (``shockbench_flow_agent.shim.warm_up``: the instance schema's compile and
the loader's imports, 0.28 s of week 1's CPU on the scoring host before it moved there,
``docs/evidence/hackathon/week_one_cpu_before.txt``) and ``agent.py``'s module level run before it (the start-up
budget, ``startup_s``), while ``Agent(config)`` and the kit's reading of the episode's Static, done when the Reset is
read, are charged to week 1.
"""

import http.client
import json
import math
import os
import re
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


METHODS = ("cgroup", "docker_stats")
POLL_S = {"cgroup": 0.02, "docker_stats": 0.25}  # seconds between two looks while a week waits (not model values)
CGROUP_ROOT_VAR = "SBF_HOST_CGROUP"  # where the worker mounts the Docker host's /sys/fs/cgroup in the ingestion
DEFAULT_CGROUP_ROOT = "/host/sys/fs/cgroup"  # the worker patch's mount point (deploy/codabench/worker)
DOCKER_SOCKET = "/var/run/docker.sock"
STATS_TIMEOUT_S = 5.0  # seconds a stats call may take (not a model value)
CIDFILE_WAIT_S = 10.0  # seconds the cidfile may take to appear after the container is up (not a model value)
WALK_DEPTH = 4  # directory levels ``container_cgroup`` searches below the root beyond the known layouts
_ID = re.compile(r"[0-9a-f]{64}")


class MeterError(RuntimeError):
    """The meter cannot read a container's CPU (no accounting file, a malformed one, a failed API call)."""


def read_usage_s(path: str | Path) -> float:
    """CPU seconds of a cgroup: ``usage_usec`` of a v2 ``cpu.stat``, or a v1 ``cpuacct.usage`` in nanoseconds.

    Raises:
        OSError: if the file cannot be read (the cgroup is gone with its container).
        MeterError: if it holds no usage.

    """
    p = Path(path)
    text = p.read_text()
    if p.name == "cpuacct.usage":
        try:
            return int(text.strip()) / 1e9
        except ValueError:
            raise MeterError(f"{p}: not a cpuacct.usage count") from None
    for line in text.splitlines():
        key, _, value = line.partition(" ")
        if key == "usage_usec":
            return int(value) / 1e6
    raise MeterError(f"{p}: no usage_usec line (not a cgroup v2 cpu.stat)")


def _check_id(container_id: str) -> str:
    if not _ID.fullmatch(container_id):
        raise MeterError(f"not a full container ID (64 hex digits): {container_id!r}")
    return container_id


def container_cgroup(root: str | Path, container_id: str) -> Path:
    """The CPU accounting file of Docker container ``container_id`` under the host cgroup tree mounted at ``root``.

    The known layouts first (cgroup v2 with the systemd or the cgroupfs driver, then v1's), else a walk of at most
    ``WALK_DEPTH`` levels for a directory named ``docker-<id>.scope`` or ``<id>`` holding one.

    Raises:
        MeterError: on an ID that is not 64 hex digits, or when no such file exists.

    """
    cid, base = _check_id(container_id), Path(root)
    scope = f"docker-{cid}.scope"
    known = [
        base / "system.slice" / scope / "cpu.stat",
        base / "docker" / cid / "cpu.stat",
        *(base / ctl / sub / "cpuacct.usage" for ctl in ("cpu,cpuacct", "cpuacct") for sub in (f"docker/{cid}",
                                                                                              f"system.slice/{scope}")),
    ]  # fmt: skip
    for f in known:
        if f.is_file():
            return f
    frontier = [base]
    for _ in range(WALK_DEPTH + 1):
        nxt = []
        for d in frontier:
            try:
                children = sorted(c for c in d.iterdir() if c.is_dir() and not c.is_symlink())
            except OSError:
                continue
            for c in children:
                if c.name in (scope, cid):
                    for name in ("cpu.stat", "cpuacct.usage"):
                        if (c / name).is_file():
                            return c / name
                nxt.append(c)
        frontier = nxt
    raise MeterError(f"no cgroup of container {cid[:12]} under {base} (is the host's cgroup tree mounted there?)")


def read_cidfile(path: str | Path, wait_s: float = CIDFILE_WAIT_S) -> str:
    """The container ID ``docker run --cidfile`` wrote to ``path``, waiting up to ``wait_s`` for it.

    Raises:
        MeterError: if no full container ID is there in time.

    """
    p, deadline = Path(path), time.monotonic() + wait_s
    while True:
        try:
            text = p.read_text().strip()
        except OSError:
            text = None
        if text is not None and _ID.fullmatch(text):
            return text
        if time.monotonic() >= deadline:
            if text is None:
                raise MeterError(f"no container ID in {p} after {wait_s:g} s")
            raise MeterError(f"{p} holds no full container ID: {text[:80]!r}")
        time.sleep(0.01)


class _UnixConnection(http.client.HTTPConnection):
    """An HTTP/1.1 connection over a unix socket (the Docker daemon's API)."""

    def __init__(self, path: str, timeout: float) -> None:
        super().__init__("localhost", timeout=timeout)
        self._path = path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self._path)
        self.sock = sock


class DockerStats:
    """The Docker API's one-shot stats over the daemon's unix socket, on one keep-alive connection."""

    def __init__(self, socket_path: str = DOCKER_SOCKET, timeout_s: float = STATS_TIMEOUT_S) -> None:
        self._conn = _UnixConnection(str(socket_path), timeout_s)

    def usage_s(self, container_id: str) -> float:
        """The container's cumulative CPU seconds (``cpu_stats.cpu_usage.total_usage``, nanoseconds).

        Raises:
            MeterError: on an ID that is not 64 hex digits, a failed call or a reply without the usage.
            OSError: when the socket fails.

        """
        cid = _check_id(container_id)
        for attempt in (0, 1):  # a keep-alive connection the daemon closed is opened again once
            try:
                self._conn.request("GET", f"/containers/{cid}/stats?stream=false&one-shot=true")
                resp = self._conn.getresponse()
                body = resp.read()
                break
            except (http.client.HTTPException, ConnectionError):
                self._conn.close()
                if attempt:
                    raise
        if resp.status != 200:
            raise MeterError(f"stats of {cid[:12]}: HTTP {resp.status}")
        try:
            return int(json.loads(body)["cpu_stats"]["cpu_usage"]["total_usage"]) / 1e9
        except (ValueError, KeyError, TypeError):
            raise MeterError(f"stats of {cid[:12]}: no cpu_stats.cpu_usage.total_usage") from None

    def close(self) -> None:
        self._conn.close()


def cpu_reader(
    method: str, container_id: str, *, cgroup_root: str | Path | None = None, socket_path: str = DOCKER_SOCKET
) -> Callable[[], float]:
    """A function returning the container's cumulative CPU seconds by ``method`` (module docstring).

    ``cgroup_root`` defaults to ``$SBF_HOST_CGROUP``, else ``DEFAULT_CGROUP_ROOT``.

    Raises:
        ValueError: on a method outside ``METHODS``.
        MeterError: where ``container_cgroup`` raises (the cgroup method finds its file here, once).

    """
    if method == "cgroup":
        root = cgroup_root or os.environ.get(CGROUP_ROOT_VAR) or DEFAULT_CGROUP_ROOT
        path = container_cgroup(root, container_id)
        return lambda: read_usage_s(path)
    if method == "docker_stats":
        stats = DockerStats(socket_path)
        return lambda: stats.usage_s(container_id)
    raise ValueError(f"meter method must be one of {METHODS}, got {method!r}")


@dataclass
class WeekCpu:
    """The week rule of the module docstring over one container: an ``information.runner.WeekMeter``.

    ``resolve()`` returns the container's reader (called once, by ``start``). ``weeks`` holds each week's CPU seconds
    (None where a read failed), ``over`` the weeks over ``budget_s``, ``errors`` the failed reads; ``reads`` and
    ``read_s`` count the looks and the wall seconds they took (the meter's own cost).

    Raises:
        ValueError: on a budget that is not a positive finite number of seconds.
    """

    resolve: Callable[[], Callable[[], float]]
    budget_s: float
    poll_s: float = POLL_S["cgroup"]
    started: bool = False
    weeks: list[float | None] = field(default_factory=list)
    over: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    reads: int = 0
    read_s: float = 0.0

    def __post_init__(self) -> None:
        b = self.budget_s
        if isinstance(b, bool) or not isinstance(b, (int, float)) or not math.isfinite(b) or b <= 0:
            raise ValueError(f"the CPU budget must be a positive number of seconds, got {b!r}")
        self._read: Callable[[], float] | None = None
        self._last = 0.0

    def _look(self) -> float:
        t0 = time.perf_counter()
        try:
            return self._read()
        finally:
            self.reads += 1
            self.read_s += time.perf_counter() - t0

    def start(self) -> None:
        """Resolve the reader and take the baseline; a failure leaves the meter unstarted, its error recorded."""
        try:
            self._read = self.resolve()
            self._last = self._look()
            self.started = True
        except (OSError, MeterError, ValueError) as err:
            self.errors.append(f"start: {type(err).__name__}: {err}")

    def interrupt(self) -> bool:
        """Whether the current week has already used more than the budget (a failed read: False)."""
        if not self.started:
            return False
        try:
            return self._look() - self._last > self.budget_s
        except (OSError, MeterError, ValueError):
            return False

    def end_week(self, week: int) -> bool:
        """Close week ``week``: its CPU is the usage now minus at the last reading; True when over the budget.

        An unstarted meter or a failed read is over the budget (fails closed; the error is recorded).
        """
        if not self.started:
            self.weeks.append(None)
            self.over.append(week)
            return True
        try:
            now = self._look()
        except (OSError, MeterError, ValueError) as err:
            self.errors.append(f"week {week}: {type(err).__name__}: {err}")
            self.weeks.append(None)
            self.over.append(week)
            return True
        used, self._last = now - self._last, now
        self.weeks.append(used)
        if used > self.budget_s:
            self.over.append(week)
            return True
        return False

    def summary(self) -> dict:
        """{weeks, median_s, max_s, sum_s, over_budget, reads, read_s, errors} of the weeks metered."""
        got = sorted(w for w in self.weeks if w is not None)
        mid = len(got) // 2
        median = None if not got else (got[mid] if len(got) % 2 else (got[mid - 1] + got[mid]) / 2)
        return {
            "weeks": len(self.weeks),
            "median_s": median,
            "max_s": got[-1] if got else None,
            "sum_s": sum(got),
            "over_budget": list(self.over),
            "reads": self.reads,
            "read_s": self.read_s,
            "errors": list(self.errors),
        }
