"""The policy container transport: one container per episode with the §9.4 flags, spoken to over stdin/stdout.

``DockerTransport`` implements M3's ``information.runner.Transport`` over ``docker run -i`` of the policy image
(``shockbench_flow_agent/policy_image/Dockerfile``): the §9.2 wire on the container's stdin and stdout, under the
wire's per-week deadline, with every kill and every close going through ``docker kill <name>``, which ends the
container's PID 1 and so tears down its PID namespace, a ``setsid()`` worker included. Killing the ``docker run``
client instead would leave the container running (design §9.4 'Time enforcement': kills never by pid).
``LocalShimTransport`` runs the same launcher and shim as a local child without Docker and without isolation, for
local runs (``--transport=subprocess``).

Readings of design §9.4 (a reading, recorded here and in ``docs/099-hosting.md``):

- **Flags** (``docker_run_argv``): ``--network none``, ``--read-only``, a size-capped tmpfs ``/tmp`` (nosuid, nodev),
  ``--cap-drop ALL``, ``--security-opt no-new-privileges``, ``--user 65534:65534``, ``--cpus 1``, ``--memory 4g`` with
  ``--memory-swap`` equal (no swap), ``--pids-limit``, a private IPC namespace with a capped ``/dev/shm``,
  ``--ulimit core=0`` (no core file leaves the container through the host's core pattern), ``--log-driver none`` (the
  daemon stores none of the policy's output), ``--pull never`` (only the image the runner names, by ID), and one mount,
  the submission directory, read-only at ``/submission`` (a bind of a directory on the Docker host, or a named volume
  the runner filled, ``volume=``: the Codabench ingestion's two ways, Q113). With ``cidfile=`` the client writes the
  container's ID there when it creates it, which the runner's CPU meter reads (``hosting.metering``). No ``-e``: the
  container's environment is the image's. The
  ``docker`` client itself runs with a scrubbed environment (``docker_cli_env``), so ``SBF_ENTROPY`` and the scorer's
  key never reach even the client process.
- **Start-up** (``ReadyTransport``): the image's entry point (``hosting/launch.py``) writes ``launch.READY_LINE``
  once the interpreter, NumPy, the kit and the submission's ``agent.py`` are imported (the kit's shim signals it); the
  first ``send`` (the Reset) waits for it within ``startup_s`` and consumes it, then writes the Reset under M3's
  start-up rule, so the container's start-up and the submission's import are charged to no week (``docker run -i``'s
  client reads the Reset at once, so M3's read probe alone would not see the container's start-up) and the ready line
  is never counted stale. A container that writes no ready line in time is killed, and
  the runner plays every week as 'killed' (naive, §9.3).
- **Watchdog**: ``episode_timeout_s`` arms a per-episode timer that docker-kills the container whatever the runner is
  doing (§9.4 'Global kill timer').
- **Not built here** (M6, §9.4 'Time enforcement'): the cgroup freeze between steps, the per-step CPU metering and the
  overage bank; only the wall-clock deadline of the wire applies.

**The scorer's secrets and local runs** (design §12 "Local runs and the scorer's secrets"; M4 re-gate INT-M4R2-01).
Only the container isolates: a local child (``LocalShimTransport``, the kit's local evaluation) runs with the runner's
uid, so it reads the runner's environment (``/proc/$PPID/environ`` on Linux, ``ps -E`` on macOS) and files (``.env``)
whatever environment it is given, and an in-process agent shares the process. So E_split and the scorer's HMAC key
(``SECRET_VARS``) never coexist with participant code outside a container: ``check_unisolated`` refuses a local run
while either is set (``LocalShimTransport`` calls it before starting its child; the scripts load ``.env`` into the
environment first, and the package's local evaluation, which loads none, reads the ``.env`` beside it with
``check_dotenv``), the hidden split is scored through
``DockerTransport`` only (``hosting.trusted.score_submission``), every policy process's own environment is an
allow-list (``docker_cli_env`` for the client, the image's for the container, ``local_child_env`` for a local child),
and an in-process agent runs with the secret-like variables out of ``os.environ`` (``without_secret_like``). What a
local child can still read (API keys exported in the runner's shell, any file of the user's) is the reason untrusted
code is scored through Docker only.
"""

import contextlib
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator, Mapping, MutableMapping, Sequence
from pathlib import Path

from sbfv.hosting.launch import READY_LINE
from sbfv.hosting.limits import ContainerLimits  # defined in hosting.limits since Q117; importable here
from sbfv.information.runner import SubprocessTransport


LAUNCHER = Path(__file__).with_name("launch.py")  # copied to /opt/sbf/launch.py in the image
SUBMISSION_MOUNT = "/submission"
POLICY_USER = "65534:65534"  # nobody:nogroup (§9.4 'uid 65534')
DOCKER_CALL_TIMEOUT_S = 60.0  # seconds a `docker kill` or `docker inspect` call may take (not a model value)
GONE_POLL_S, GONE_WAIT_S = 0.1, 20.0  # polling for the container's removal after a kill (not model values)
CLI_ENV_KEYS = (
    "PATH",
    "HOME",
    "DOCKER_HOST",
    "DOCKER_CONFIG",
    "DOCKER_CONTEXT",
    "DOCKER_CERT_PATH",
    "DOCKER_TLS_VERIFY",
    "XDG_RUNTIME_DIR",
)
THREAD_ENV = {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}  # a courtesy (§9.6)
SECRET_VARS = ("SBF_ENTROPY", "SBF_SCORES_KEY")  # E_split and the scorer's HMAC key: the trusted runner's (§4.1, §9.4)
SECRET_LIKE = re.compile(r"KEY|TOKEN|SECRET|PASSW|CREDENTIAL|AUTH", re.IGNORECASE)  # what without_secret_like drops
DOTENV = ".env"
_DOTENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(.*?)\s*$")


def secrets_set(environ: Mapping[str, str] | None = None) -> list[str]:
    """The names of ``SECRET_VARS`` set to a non-empty value in ``environ`` (default ``os.environ``), in that order."""
    env = os.environ if environ is None else environ
    return [name for name in SECRET_VARS if env.get(name)]


def check_unisolated(environ: Mapping[str, str] | None = None) -> None:
    """Refuse to run participant code without a container while a scorer secret is set (module docstring).

    Raises:
        ValueError: naming each of ``SECRET_VARS`` set in ``environ`` (default ``os.environ``, which the entry points
            fill from ``.env`` too).

    """
    names = secrets_set(environ)
    if names:
        raise ValueError(
            f"{', '.join(names)} set: participant code outside a container can read this process's environment and "
            "files (a local child through /proc/$PPID/environ or ps -E), so no local agent runs while the scorer's "
            "secrets are here; unset them in the environment and in .env, or score through the policy container "
            "(transport=docker)"
        )


def find_dotenv(start: str | Path) -> Path | None:
    """The ``.env`` a run from ``start`` would load, or None: the first in ``start`` or a parent (``usecwd=True``)."""
    here = Path(start).resolve()
    return next((d / DOTENV for d in (here, *here.parents) if (d / DOTENV).is_file()), None)


def dotenv_file() -> Path | None:
    """The ``.env`` beside this run: ``find_dotenv`` of the working directory."""
    return find_dotenv(Path.cwd())


def dotenv_values(path: str | Path) -> dict[str, str]:
    """The ``NAME=value`` lines of a ``.env`` file, as python-dotenv reads them for ``check_unisolated``.

    ``export`` is allowed, a quoted value loses its quotes, an unquoted one its comment after a blank and ``#``; other
    lines are skipped. It is not python-dotenv's whole grammar, only enough that a set name is never read as unset. An
    unreadable file reads as empty (the agent, of the same uid, cannot read it either).
    """
    try:
        text = Path(path).read_text(errors="replace")
    except OSError:
        return {}
    values = {}
    for line in text.splitlines():
        if m := _DOTENV_LINE.match(line):
            name, raw = m[1], m[2]
            if raw[:1] in ("'", '"'):
                values[name] = raw[1:].split(raw[0], 1)[0]
            else:
                values[name] = re.split(r"\s#", raw, maxsplit=1)[0]
    return values


def check_dotenv() -> None:
    """``check_unisolated`` of the ``.env`` beside this run (``dotenv_file``), for entry points that load none.

    A local agent can read that file whatever its environment (module docstring), so a scorer secret it sets refuses
    the run as an exported one does.

    Raises:
        ValueError: naming the file and each of ``SECRET_VARS`` it sets to a non-empty value.

    """
    path = dotenv_file()
    if path is None:
        return
    try:
        check_unisolated(dotenv_values(path))
    except ValueError as err:
        raise ValueError(f"{path} sets them: {err}") from None


@contextlib.contextmanager
def without_secret_like(environ: MutableMapping[str, str] | None = None) -> Iterator[None]:
    """``environ`` (default ``os.environ``) without ``SECRET_VARS`` and names ``SECRET_LIKE`` matches, then restored.

    For an agent played in this process (module docstring): the variables leave the mapping, so the agent's
    ``os.environ`` and its children's environments lack them; a process's initial environment block (what
    ``/proc/self/environ`` shows) is not rewritten, which is why ``check_unisolated`` refuses the scorer's secrets.
    """
    env = os.environ if environ is None else environ
    removed = {k: env.pop(k) for k in list(env) if k in SECRET_VARS or SECRET_LIKE.search(k)}
    try:
        yield
    finally:
        env.update(removed)


def _mount(submission_dir: Path | None, volume: str | None) -> str:
    """The ``--mount`` value of the submission: a read-only bind of ``submission_dir`` or of the named ``volume``."""
    if (submission_dir is None) == (volume is None):
        raise ValueError("give exactly one of the submission directory and a named volume")
    if volume is not None:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", volume):
            raise ValueError(f"not a volume name: {volume!r}")
        return f"type=volume,source={volume},target={SUBMISSION_MOUNT},readonly,volume-nocopy"
    src = str(submission_dir)
    if not os.path.isabs(src) or any(c in src for c in ",=") or any(ord(c) < 32 for c in src):
        raise ValueError(f"the submission directory must be an absolute path without ',' '=' or controls: {src!r}")
    return f"type=bind,source={src},target={SUBMISSION_MOUNT},readonly"


def docker_run_argv(
    image: str,
    submission_dir: Path | None,
    name: str,
    limits: ContainerLimits,
    docker: Sequence[str] = ("docker",),
    labels: dict[str, str] | None = None,
    *,
    volume: str | None = None,
    cidfile: Path | None = None,
) -> list[str]:
    """The ``docker run`` argv of one policy container (module docstring, 'Flags'); the image's entry point runs.

    The submission is ``submission_dir`` (a directory on the Docker host) or the named ``volume``, never both;
    ``cidfile`` asks the client to write the container's ID to that file (a path the client sees).

    Raises:
        ValueError: if ``submission_dir`` is not an absolute path free of ',', '=' and control characters (the
            ``--mount`` syntax would read them), ``volume`` or ``name`` is not a Docker name, both or neither of them
            are given, or ``cidfile`` is not an absolute path.

    """
    mount = _mount(submission_dir, volume)
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", name):
        raise ValueError(f"not a container name: {name!r}")
    if cidfile is not None and not os.path.isabs(str(cidfile)):
        raise ValueError(f"the cidfile must be an absolute path: {cidfile!r}")
    argv = [
        *docker,
        "run",
        "--rm",
        "-i",
        "--pull",
        "never",
        "--name",
        name,
        "--hostname",
        "policy",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        f"/tmp:rw,nosuid,nodev,size={limits.tmpfs}",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        POLICY_USER,
        "--cpus",
        str(limits.cpus),
        "--memory",
        limits.memory,
        "--memory-swap",
        limits.memory,
        "--pids-limit",
        str(limits.pids),
        "--ipc",
        "private",
        "--shm-size",
        limits.shm,
        "--ulimit",
        "core=0",
        "--log-driver",
        "none",
    ]
    for key, value in sorted((labels or {}).items()):
        argv += ["--label", f"{key}={value}"]
    if cidfile is not None:
        argv += ["--cidfile", str(cidfile)]
    return [*argv, "--mount", mount, image]


def docker_cli_env() -> dict[str, str]:
    """The ``docker`` client's environment: the variables it needs (``CLI_ENV_KEYS``) and nothing else."""
    return {k: os.environ[k] for k in CLI_ENV_KEYS if k in os.environ}


def image_id(image: str, docker: Sequence[str] = ("docker",)) -> str:
    """The local image's ID (``sha256:<hex>``, the digest of its configuration), which the runner pins and records.

    Raises:
        ValueError: if docker finds no such local image.

    """
    out = subprocess.run(
        [*docker, "image", "inspect", "--format", "{{.Id}}", image],
        env=docker_cli_env(),
        capture_output=True,
        text=True,
        timeout=DOCKER_CALL_TIMEOUT_S,
        check=False,
    )
    ident = out.stdout.strip()
    if out.returncode != 0 or not re.fullmatch(r"sha256:[0-9a-f]{64}", ident):
        raise ValueError(
            f"no local policy image {image!r} (build one: shockbench_flow_agent.build_image, or the organisers' "
            "scripts/bash/hosting/build_policy_image.sh)"
        )
    return ident


def local_child_env(shim_module: str, kit_path: Sequence[str | Path], *, home: str | Path) -> dict[str, str]:
    """A local shim child's environment: PATH, a private HOME, the launcher's two variables and ``THREAD_ENV``."""
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "SBF_SHIM_MODULE": shim_module,
        "SBF_KIT_PATH": os.pathsep.join(str(p) for p in kit_path),
        **THREAD_ENV,
    }


class ReadyTransport(SubprocessTransport):
    """A ``SubprocessTransport`` whose child writes ``READY_LINE`` when it is up (module docstring, 'Start-up').

    ``ready_s`` is the seconds from the first send to the ready line (None when it never came).
    """

    ready_s: float | None = None

    def send(self, line: bytes) -> int:
        if self._started:
            return super().send(line)
        start = time.monotonic()
        self._deadline = start + self.startup_s
        while True:
            r = self.receive()
            if r.kind == "line" and r.line == READY_LINE:
                self.ready_s = time.monotonic() - start
                return super().send(line)
            if r.kind == "line":
                continue  # before the ready line nothing of the submission has run: discarded
            self._started = True  # the start-up is over: a deadline kills, a closed channel is closed
            if r.kind == "deadline":
                self.kill()
            self._gone = True
            self._close_probe()
            return 0


class LocalShimTransport(ReadyTransport):
    """The launcher and the kit's shim as a local child: no Docker and no isolation (local and dev runs only).

    The child is ``sys.executable -I -B -u launch.py <submission_dir>`` with ``local_child_env`` (a fresh HOME in a
    temporary directory removed at close), its stderr ``stderr`` (None inherits the runner's). It is never started
    while a scorer secret is set (``check_unisolated``, module docstring).

    Raises:
        ValueError: from ``check_unisolated``, before anything is started.
    """

    def __init__(
        self,
        submission_dir: str | Path,
        *,
        shim_module: str,
        kit_path: Sequence[str | Path],
        deadline_s: float,
        startup_s: float,
        max_reply_bytes: int,
        stderr: int | None = None,
    ) -> None:
        check_unisolated()
        self._home = tempfile.mkdtemp(prefix="sbf-policy-home-")
        argv = [sys.executable, "-I", "-B", "-u", str(LAUNCHER), str(Path(submission_dir).resolve())]
        try:
            super().__init__(
                argv,
                deadline_s=deadline_s,
                startup_s=startup_s,
                max_reply_bytes=max_reply_bytes,
                env=local_child_env(shim_module, kit_path, home=self._home),
                stderr=stderr,
            )
        except BaseException:
            shutil.rmtree(self._home, ignore_errors=True)
            raise

    def close(self) -> None:
        try:
            super().close()
        finally:
            shutil.rmtree(self._home, ignore_errors=True)


class DockerTransport(ReadyTransport):
    """One policy container per episode over ``docker run -i`` (module docstring).

    ``name`` is a fresh random container name (never derived from the episode); ``stderr`` receives the container's
    standard error (DEVNULL by default: scored runs show no policy output, §9.5 'Logs'); ``labels`` are added to the
    container (for a runner's cleanup). ``submission_dir`` None with ``volume`` mounts that named volume instead, and
    ``cidfile`` has the client write the container's ID there (``docker_run_argv``). After ``close``,
    ``container_gone`` says whether ``docker inspect`` no longer finds the container, and ``watchdog_fired`` whether
    the per-episode timer killed it.
    """

    def __init__(
        self,
        image: str,
        submission_dir: str | Path | None,
        *,
        deadline_s: float,
        startup_s: float,
        max_reply_bytes: int,
        limits: ContainerLimits = ContainerLimits(),
        docker: Sequence[str] = ("docker",),
        name: str | None = None,
        stderr: int | None = subprocess.DEVNULL,
        episode_timeout_s: float | None = None,
        labels: dict[str, str] | None = None,
        volume: str | None = None,
        cidfile: str | Path | None = None,
    ) -> None:
        self.name = name or f"sbf-policy-{secrets.token_hex(8)}"
        self.docker = tuple(docker)
        self.container_gone: bool | None = None
        self.watchdog_fired = False
        self._cli_env = docker_cli_env()
        src = None if submission_dir is None else Path(submission_dir).resolve()
        cid = None if cidfile is None else Path(cidfile)
        argv = docker_run_argv(image, src, self.name, limits, self.docker, labels, volume=volume, cidfile=cid)
        super().__init__(
            argv,
            deadline_s=deadline_s,
            startup_s=startup_s,
            max_reply_bytes=max_reply_bytes,
            env=self._cli_env,
            stderr=stderr,
        )
        self._timer: threading.Timer | None = None
        if episode_timeout_s is not None:
            self._timer = threading.Timer(float(episode_timeout_s), self._watchdog)
            self._timer.daemon = True
            self._timer.start()

    def _docker(self, *args: str) -> int:
        try:
            return subprocess.run(
                [*self.docker, *args],
                env=self._cli_env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=DOCKER_CALL_TIMEOUT_S,
                check=False,
            ).returncode
        except subprocess.TimeoutExpired:
            return -1

    def docker_kill(self) -> int:
        """``docker kill <name>``: SIGKILL to the container's PID 1, which ends every process of its namespace."""
        return self._docker("kill", self.name)

    def _watchdog(self) -> None:
        self.watchdog_fired = True
        self.docker_kill()

    def _reap(self) -> None:
        try:
            self.proc.wait(timeout=DOCKER_CALL_TIMEOUT_S)
        except subprocess.TimeoutExpired:  # the client hangs although the container is killed: end the client
            self.proc.kill()
            self.proc.wait()

    def kill(self) -> None:
        self._gone = True
        self.docker_kill()
        self._reap()

    def exists(self) -> bool:
        """Whether ``docker inspect`` still finds the container."""
        return self._docker("inspect", self.name) == 0

    def close(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._close_probe()
        if self._in >= 0:
            try:
                os.close(self._in)
            except OSError:
                pass
            self._in = -1
        self._gone = True
        self.docker_kill()  # the episode is over: nothing more is read, and the namespace goes with PID 1
        self._reap()
        deadline = time.monotonic() + GONE_WAIT_S
        while self.exists() and time.monotonic() < deadline:  # --rm removes it once PID 1 is gone
            time.sleep(GONE_POLL_S)
        self.container_gone = not self.exists()
        self._sel.close()
        self.proc.stdout.close()
