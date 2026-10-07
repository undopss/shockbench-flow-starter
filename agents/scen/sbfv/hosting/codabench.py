"""The Codabench adapter of the trusted runner: ingestion, scoring and the task documents (Q113; design §12 rows).

Codabench runs a competition task in two containers of the owner's compute worker, both from the runner image
(``deploy/codabench/images/runner``), neither ever executing participant code:

- **ingestion** (``python -m sbfv.hosting.codabench ingest <input_data> <output> <ingested_program>``):
  reads the task's input spec (``task.json``: instance, rung, regime, split, the episodes with their strata, naive's
  F_Q; ``secret.json``: the predictions key and, on the hidden split, the secret root), checks the submission
  directory Codabench unpacked with the kit's validator rules (``check_submission_dir``, then
  ``submission.check_zip`` of its canonical zip), starts one policy container per episode through the Docker socket
  the worker mounts (``hosting.docker.DockerTransport``, the §9.4 flags), meters each week's CPU from the container's
  cgroup (``hosting.metering``: over ``cpu_budget_s`` is the week's D9, 'cpu'), re-simulates every episode from its
  action log once its container is gone, and writes ``predictions.json``, signed with the task's predictions key.
- **scoring** (``score`` / ``score-final <input> <output>``): reads ``res/predictions.json`` and ``ref/reference.json``,
  refuses a document whose signature, task or episode set differs from the reference's, applies the one RSS rule
  (``evaluation.results.exclusion_cause`` through the sealed statuses, ``episode_rss`` through
  ``hosting.trusted.rss_table``) with the oracle bound on each episode, and writes ``scores.json``:
  ``{rss, fallback_count}`` on both phases. Codabench gives every phase the bundle's first leaderboard (its v2
  unpacker, ``phase['leaderboard'] = leaderboards[0]``) and keeps only the scores whose keys are that board's columns,
  so both phases write the one board's keys; the board shows each phase's submissions apart (Q116).

**The phases' splits** (``PHASES``, Q116): both phases score the hidden split, each from its own secret root (the
Development phase's public board on `small`, the Final's private board on `full`). A Development task on the dev
split's public root is accepted for a local test of the adapter against the trusted runner
(``deploy/codabench/local_test.py``, ``PHASE_SPLITS``); ``deploy/codabench/validate_bundle.py`` refuses it in a
bundle.

**The submission's mount** (``submission_mount``). The policy container must mount the submission from a path of the
Docker *host*, which the ingestion container does not know. Two ways, both implemented: ``host_path``, the host path
of the directory Codabench unpacked, which the patched worker passes as ``SBF_SUBMISSION_HOST_DIR``
(``deploy/codabench/worker``), used when every file of it is world-readable (the container runs as uid 65534); and
``volume``, a fresh named volume the ingestion fills through the socket alone (``docker create`` of a stopped helper
with the volume, ``docker cp`` of the validated copy, whose files are 0644 and directories 0755, then ``docker rm``),
removed at the end. ``auto`` (the default) takes the first that applies.

**What reaches Codabench's logs.** The policy's stdout carries the wire and its stderr goes to /dev/null
(``DockerTransport``; the container logs nothing, ``--log-driver none``); this program prints counts and timings only,
never an agent's output, a root, a key or a cost. The final phase also hides its output (``hide_output``).

**Why the predictions are signed.** The stock worker copies the submission's files into the scoring container's
``input/res`` beside ``predictions.json`` (``_copy_submission_to_input_res``), so a submission holding its own
``predictions.json`` would replace the ingestion's; the HMAC with a key held only by ``input_data`` and
``reference_data`` refuses it (and the patched worker skips the copy; a submission naming ``predictions.json`` at its
root is refused at ingestion with a clear reason).

**One machine type** (Q94; design §12 "Arithmetic across CPU types (M4 re-gate)"). The task's episodes carry each
omega's SHA-256 and harm as the reference builder drew them (``scripts/python/build_codabench_reference.py``); the
ingestion draws each omega again and refuses to play on a machine whose draws differ (an organiser error, exit 3),
since J^naive and J^oracle in ``reference.json`` are the builder's. The runner's package must also be the builder's
(``package_sha256``).

Exit statuses: 0 done; 1 a scoring check failed or the documents disagree (no score is published); 2 the submission is
refused (its reason on stderr; ``predictions.json`` records it, signed, and the scoring exits 2 on it); 3 the
organiser's setup is wrong (task, image, package, machine type, metering).
"""

import functools
import hashlib
import json
import math
import os
import platform
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

import sbfv
from sbfv.hosting import metering
from sbfv.hosting.docker import ContainerLimits, DockerTransport, docker_cli_env, image_id
from sbfv.hosting.limits import (
    BANK_SECONDS,
    CPU_BUDGET_S,
    DEADLINE_S,
    MAX_REPLY_BYTES,
    PHASE_TASKS,
    STARTUP_S,
)
from sbfv.hosting.split import Scenario, check_root, entropy_commitment
from sbfv.hosting.submission import (  # noqa: F401 - ZIP_OVERHEAD re-exported (it was defined here)
    MAX_SUBMISSION_BYTES,
    MAX_SUBMISSION_FILES,
    ZIP_OVERHEAD,
    SubmissionError,
    SubmissionLimits,
    build_submission,
    check_zip,
    extract_submission,
    stored_zip_bytes,
)
from sbfv.information.theta import REGIME_NAMES
from sbfv.information.wire import WireLimits


TASK_SCHEMA = "sbf-codabench-task/1"
SECRET_SCHEMA = "sbf-codabench-secret/1"
REFERENCE_SCHEMA = "sbf-codabench-reference/1"
PREDICTIONS_SCHEMA = "sbf-codabench-predictions/1"
PHASES = {"development": "hidden", "final": "hidden"}  # a Codabench phase and the split it scores (Q116; Q113)
# the splits a phase's task may carry: PHASES's, and the public dev root for the Development phase's local test only
PHASE_SPLITS = {"development": ("hidden", "dev"), "final": ("hidden",)}
# scores.json's keys per phase: the one leaderboard's columns on both (module docstring, 'scoring'; Q116)
SCORE_KEYS = {"development": ("rss", "fallback_count"), "final": ("rss", "fallback_count")}
RSS_DIGITS = 8  # decimals of the RSS in scores.json (the leaderboards show 4; the owner's shell wrote 8)
TASK_FILE, SECRET_FILE, REFERENCE_FILE = "task.json", "secret.json", "reference.json"
PREDICTIONS_FILE = "predictions.json"
SCORES_FILE, DETAIL_FILE = "scores.json", "scores_detail.json"
RESERVED_ROOT_NAMES = (PREDICTIONS_FILE,)  # what the stock worker's copy would shadow in the scoring's input/res
MOUNTS = ("auto", "host_path", "volume")
METERS = ("auto", *metering.METHODS)
HOST_DIR_VAR = "SBF_SUBMISSION_HOST_DIR"  # the worker's host path of the unpacked submission (deploy/codabench/worker)
RUN_ID_VAR = "SBF_RUN_ID"  # the worker's run name, the label its cleanup removes leftovers by
EPISODE_JOBS_VAR = "SBF_EPISODE_JOBS"  # episodes in parallel, overriding the task's (local tests on a larger machine)
RUN_LABEL, ROLE_LABEL = "sbf.run", "sbf.role"
OMEGA_REGIMES = ("clairvoyant",)  # regimes whose Reset carries omega to the policy: never on the hidden split
DONE, CHECK_FAILED, REFUSED, ORGANISER = 0, 1, 2, 3
# the owner's words for the D9 causes (Q113): over the CPU budget, late, invalid, crashed
CAUSE_GROUPS = {
    "cpu": "over_budget",
    "timeout": "late",
    "action": "invalid",
    "unparsable": "invalid",
    "too_long": "invalid",
    "tags": "invalid",
    "killed": "crashed",
}
DOCKER_CALL_TIMEOUT_S = 120.0  # seconds a volume or cleanup call may take (a docker cp of 500 MB included)


class OrganiserError(RuntimeError):
    """The organiser's setup is wrong (task, image, package, machine type, metering): exit 3, nothing scored."""


# ----- small helpers -------------------------------------------------------------------------------------------------
def canonical(doc: object) -> bytes:
    """The canonical JSON of a document (sorted keys, no spaces, no NaN): what is hashed and signed."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sign(doc: Mapping, key: bytes) -> dict:
    """``doc`` with ``signature`` = HMAC-SHA256 over the canonical JSON of the rest (``trusted.sign_scores``)."""
    from sbfv.hosting.trusted import sign_scores

    return sign_scores(doc, key)


def verify(doc: Mapping, key: bytes) -> bool:
    """Whether ``doc``'s signature is the HMAC of its body under ``key`` (``trusted.verify_scores``)."""
    from sbfv.hosting.trusted import verify_scores

    return verify_scores(doc, key)


def package_sha256() -> str:
    """SHA-256 of the package source that runs, as ``sbf_boundary.package_sha256`` computes it (the same rule)."""
    pkg = Path(sbfv.__file__).parent
    h = hashlib.sha256()
    for path in sorted(pkg.rglob("*.py")):
        h.update(path.relative_to(pkg).as_posix().encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


def cpu_model() -> str:
    """The CPU's model name (``/proc/cpuinfo`` on Linux, else ``platform.processor()``): recorded, never compared."""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def machine() -> dict:
    """Where a document was made: OS, architecture, CPU model, Python, NumPy and SciPy (Q94: one machine type)."""
    import numpy
    import scipy

    return {
        "platform": f"{platform.system()} {platform.machine()}",
        "cpu_model": cpu_model(),
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
    }


def _read_json(path: Path, what: str) -> dict:
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError) as err:
        raise OrganiserError(f"{what} {path}: {err}") from None
    if not isinstance(doc, dict):
        raise OrganiserError(f"{what} {path}: not a JSON object")
    return doc


def quantiles_record(quantiles: Mapping[tuple, float]) -> list[list]:
    """Naive's F_Q quantiles as JSON rows ``[c, pool, j, k, value]`` in key order (floats round-trip exactly)."""
    return [[int(c), str(p), int(j), int(k), float(v)] for (c, p, j, k), v in sorted(quantiles.items(), key=str)]


def quantiles_from_record(rows: Sequence) -> dict[tuple, float]:
    """The inverse of ``quantiles_record``.

    Raises:
        OrganiserError: on a malformed row.

    """
    out = {}
    for row in rows:
        if not (isinstance(row, list) and len(row) == 5 and isinstance(row[4], float)):
            raise OrganiserError(f"task.json: malformed F_Q row {row!r}")
        c, p, j, k, v = row
        out[(int(c), str(p), int(j), int(k))] = v
    return out


# ----- the task's input spec -----------------------------------------------------------------------------------------
@dataclass(frozen=True)
class TaskEpisode:
    """One scored episode of a task: its index n, harm stratum, harm H (42) and omega's SHA-256, as the builder drew."""

    episode: int
    stratum: int
    harm_usd: float
    omega_sha256: str

    def scenario(self) -> Scenario:
        return Scenario(self.episode, self.stratum, self.harm_usd)


@dataclass(frozen=True)
class Runtime:
    """How the ingestion runs on the worker: the policy image, episodes in parallel, the meter and the mount."""

    policy_image: str = "sbf-policy:local"
    policy_image_id: str | None = None  # pinned: the worker's image must have this ID
    episode_jobs: int | None = None  # None: the worker's CPU count minus one (one CPU per container, one for the rest)
    meter: str = "auto"  # auto (cgroup when the host tree is mounted, else docker_stats), cgroup, docker_stats
    mount: str = "auto"  # auto (host_path when the worker passes it and it is readable, else volume), host_path, volume

    def __post_init__(self) -> None:
        """Refuse an unknown meter or mount, or a job count below 1."""
        if self.meter not in METERS:
            raise OrganiserError(f"runtime.meter must be one of {METERS}, got {self.meter!r}")
        if self.mount not in MOUNTS:
            raise OrganiserError(f"runtime.mount must be one of {MOUNTS}, got {self.mount!r}")
        j = self.episode_jobs
        if j is not None and (isinstance(j, bool) or not isinstance(j, int) or j < 1):
            raise OrganiserError(f"runtime.episode_jobs must be null or an integer >= 1, got {j!r}")


@dataclass(frozen=True)
class Wire:
    """The wire's limits and the week rule (Q113): per-week deadline, start-up budget, CPU budget, episode watchdog.

    The defaults are the hosted values (``hosting.limits``, Q117), the Development phase's CPU budget; the task builder
    writes each phase's into ``task.json`` (``configs/build_codabench_reference.yaml``).
    """

    deadline_s: float = DEADLINE_S  # the wall-clock cap per week (the owner's 'e.g. 10 s')
    startup_s: float = STARTUP_S  # the container's start-up and agent.py's import (Q117)
    max_reply_bytes: int = MAX_REPLY_BYTES  # a longer reply line is a whole-week failure (Q117)
    # CPU s per week: the builder writes 2 on Development (Q113), 4 on the Final (Q115)
    cpu_budget_s: float = CPU_BUDGET_S[PHASE_TASKS["development"]]
    bank_seconds: float = BANK_SECONDS  # no overage bank under Q113: remaining_bank is sent as 0
    episode_timeout_s: float | None = None  # None: 2 startup_s + T (deadline_s + 5 s), the trusted runner's watchdog

    def __post_init__(self) -> None:
        """Refuse a non-positive time or size (the bank may be 0)."""
        for name in ("deadline_s", "startup_s", "cpu_budget_s"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
                raise OrganiserError(f"wire.{name} must be a positive number of seconds, got {v!r}")
        m = self.max_reply_bytes
        if isinstance(m, bool) or not isinstance(m, int) or m < 1:
            raise OrganiserError(f"wire.max_reply_bytes must be an integer >= 1, got {m!r}")
        if not isinstance(self.bank_seconds, (int, float)) or self.bank_seconds < 0:
            raise OrganiserError(f"wire.bank_seconds must be >= 0, got {self.bank_seconds!r}")

    def watchdog_s(self, T: int) -> float:
        """The per-episode kill timer: ``episode_timeout_s``, else the trusted runner's bound for ``T`` weeks."""
        from sbfv.hosting.trusted import RUNNER_SLACK_S

        if self.episode_timeout_s is not None:
            return float(self.episode_timeout_s)
        return 2 * self.startup_s + T * (self.deadline_s + RUNNER_SLACK_S)


@dataclass(frozen=True)
class Task:
    """A Codabench task's input spec (``task.json``), checked; the secrets are ``load_task``'s."""

    phase: str
    split: str
    instance: str
    instance_hash: str
    instance_digest: str
    profile: str
    gamma: float
    generator_id: str
    regime: str
    fq_replications: int
    quantiles: Mapping[tuple, float]
    n_per_stratum: tuple[int, ...]
    episodes: tuple[TaskEpisode, ...]
    entropy: int | None  # the dev split's public root; None on the hidden split (secret.json holds it)
    entropy_commitment: str
    package_sha256: str
    wire: Wire = field(default_factory=Wire)
    container: ContainerLimits = field(default_factory=ContainerLimits)
    submission: SubmissionLimits = field(default_factory=SubmissionLimits)
    runtime: Runtime = field(default_factory=Runtime)
    sha256: str = ""  # of task.json's bytes: what predictions.json and reference.json name the task by


def submission_limits(max_bytes: int, max_files: int = MAX_SUBMISSION_FILES) -> SubmissionLimits:
    """The kit's limits for a submission of at most ``max_bytes`` unpacked (the owner's 500 MB, a parameter).

    At the hosted size (``MAX_SUBMISSION_BYTES``, ``MAX_SUBMISSION_FILES``) they are ``SubmissionLimits()``.
    """
    return SubmissionLimits(
        max_zip_bytes=stored_zip_bytes(max_bytes, max_files),  # the canonical zip is stored: its bytes plus headers
        max_total_bytes=max_bytes,
        max_file_bytes=max_bytes,
        max_files=max_files,
    )


def task_document(**fields) -> dict:
    """``task.json``'s body from the builder's fields (``scripts/python/build_codabench_reference.py``), checked.

    Raises:
        OrganiserError: as ``parse_task`` does.

    """
    doc = {"schema": TASK_SCHEMA, **fields}
    parse_task(doc, b"")  # refuses what the ingestion would
    return doc


def parse_task(doc: Mapping, raw: bytes) -> Task:
    """A ``Task`` from ``task.json``'s document (``raw`` its bytes, hashed as the task's identity).

    Raises:
        OrganiserError: on another schema, an unknown phase or a split that is not the phase's, a missing field, an
            episode list whose strata do not answer ``n_per_stratum``, a dev split without its root or a hidden one
            with a root in it.

    """
    if doc.get("schema") != TASK_SCHEMA:
        raise OrganiserError(f"task.json: schema {doc.get('schema')!r}, expected {TASK_SCHEMA}")
    try:
        phase, split = doc["phase"], doc["split"]
        if split not in PHASE_SPLITS.get(phase, ()):
            allowed = PHASE_SPLITS.get(phase)
            raise OrganiserError(f"task.json: phase {phase!r} scores a split of {allowed}, not {split!r}")
        episodes = tuple(
            TaskEpisode(int(e["episode"]), int(e["stratum"]), float(e["harm_usd"]), str(e["omega_sha256"]))
            for e in doc["episodes"]
        )
        n_per = tuple(int(x) for x in doc["n_per_stratum"])
        have = Counter(e.stratum for e in episodes)
        if [have.get(s, 0) for s in range(1, len(n_per) + 1)] != list(n_per) or len(episodes) != sum(n_per):
            raise OrganiserError(f"task.json: the episodes' strata {dict(have)} do not answer n_per_stratum {n_per}")
        if len({e.episode for e in episodes}) != len(episodes):
            raise OrganiserError("task.json: an episode index appears twice")
        regime = str(doc["regime"])
        if regime not in REGIME_NAMES or (split != "dev" and regime in OMEGA_REGIMES):
            raise OrganiserError(f"task.json: regime {regime!r} is not a registry name, or sends omega on {split}")
        entropy = doc.get("entropy")
        if (split == "dev") != (entropy is not None):
            raise OrganiserError("task.json: the dev split carries its public root, the hidden one none (secret.json)")
        sub = doc.get("submission", {})
        return Task(
            phase=phase,
            split=split,
            instance=str(doc["instance"]),
            instance_hash=str(doc["instance_hash"]),
            instance_digest=str(doc["instance_digest"]),
            profile=str(doc["profile"]),
            gamma=float(doc["gamma"]),
            generator_id=str(doc["generator_id"]),
            regime=regime,
            fq_replications=int(doc["fq_replications"]),
            quantiles=quantiles_from_record(doc["fq_quantiles"]),
            n_per_stratum=n_per,
            episodes=episodes,
            entropy=None if entropy is None else int(entropy),
            entropy_commitment=str(doc["entropy_commitment"]),
            package_sha256=str(doc["package_sha256"]),
            wire=Wire(**doc.get("wire", {})),
            container=ContainerLimits(**doc.get("container", {})),
            submission=submission_limits(
                int(sub.get("max_bytes", MAX_SUBMISSION_BYTES)), int(sub.get("max_files", MAX_SUBMISSION_FILES))
            ),
            runtime=Runtime(**doc.get("runtime", {})),
            sha256=hashlib.sha256(raw).hexdigest(),
        )
    except (KeyError, TypeError, ValueError) as err:
        raise OrganiserError(f"task.json: {type(err).__name__}: {err}") from None


def load_task(input_dir: str | Path) -> tuple[Task, int, bytes]:
    """(the task, E_split, the predictions key) from ``<input_dir>/task.json`` and ``secret.json``.

    On the hidden split the root is ``secret.json``'s ``entropy``, held to the minimum (``split.check_root``) and to
    the task's commitment; on the dev split it is the task's public root, and ``secret.json`` holds the key only.

    Raises:
        OrganiserError: on a missing or malformed file, a root that fails its checks or its commitment, a key that is
            not 32 bytes of hex.

    """
    base = Path(input_dir)
    raw = (base / TASK_FILE).read_bytes() if (base / TASK_FILE).is_file() else b""
    if not raw:
        raise OrganiserError(f"no {TASK_FILE} in {base} (the reference builder writes it into the task's input_data)")
    task = parse_task(_read_json(base / TASK_FILE, "task"), raw)
    secret = _read_json(base / SECRET_FILE, "secret")
    if secret.get("schema") != SECRET_SCHEMA:
        raise OrganiserError(f"secret.json: schema {secret.get('schema')!r}, expected {SECRET_SCHEMA}")
    key = str(secret.get("predictions_key", ""))
    if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
        raise OrganiserError("secret.json: predictions_key must be 64 hex digits")
    if task.split == "hidden":
        if "entropy" not in secret:
            raise OrganiserError("secret.json: the hidden split's root (entropy) is missing")
        root = secret["entropy"]
        if isinstance(root, bool) or not isinstance(root, int):
            raise OrganiserError("secret.json: entropy must be an integer")
    else:
        if "entropy" in secret:
            raise OrganiserError("secret.json: the dev split's root is public (task.json); secret.json holds none")
        root = task.entropy
    try:
        check_root(task.split, root)
    except (ValueError, TypeError) as err:
        raise OrganiserError(f"the {task.split} root: {err}") from None
    if entropy_commitment(task.split, root) != task.entropy_commitment:
        raise OrganiserError("the split's root does not match task.json's entropy_commitment")
    return task, root, bytes.fromhex(key)


# ----- the submission ------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CheckedSubmission:
    """A submission directory that passed ``prepare_submission``: its canonical zip's SHA-256 and the clean copy."""

    sha256: str
    files: int
    bytes: int
    clean_dir: Path  # the validated copy (files 0644, directories 0755)
    raw_dir: Path  # the directory Codabench unpacked (``/app/ingested_program``)


def check_submission_dir(src: str | Path, limits: SubmissionLimits) -> tuple[int, int]:
    """(files, bytes) of an unpacked submission, every file counted, after the rules a directory can break.

    Refused (``SubmissionError``): ``no_submission`` (no directory), ``symlink``, ``special_file``,
    ``too_many_files``, ``too_large`` (a file over ``max_file_bytes`` or all over ``max_total_bytes``, the files the
    canonical zip leaves out included, since the container mounts them), ``reserved_name`` (a ``predictions.json`` at
    the root, module docstring). The rest of the kit's rules run on the canonical zip (``prepare_submission``).
    """
    root = Path(src)
    if not root.is_dir() or root.is_symlink():
        raise SubmissionError("no_submission", "the submission is not a directory (Codabench unpacks the zip there)")
    files = total = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in sorted(dirnames + filenames):
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            st = path.lstat()
            if stat.S_ISLNK(st.st_mode):
                raise SubmissionError("symlink", f"{rel}: a symbolic link cannot be submitted")
            if stat.S_ISDIR(st.st_mode):
                continue
            if not stat.S_ISREG(st.st_mode):
                raise SubmissionError("special_file", f"{rel}: only regular files and directories are allowed")
            files, total = files + 1, total + st.st_size
            if st.st_size > limits.max_file_bytes:
                raise SubmissionError("too_large", f"{rel}: {st.st_size} bytes, at most {limits.max_file_bytes}")
            if files > limits.max_files:
                raise SubmissionError("too_many_files", f"more than {limits.max_files} files")
            if total > limits.max_total_bytes:
                raise SubmissionError("too_large", f"more than {limits.max_total_bytes} bytes unpacked")
    for name in RESERVED_ROOT_NAMES:
        if (root / name).exists():
            raise SubmissionError(
                "reserved_name", f"{name} at the root of the zip is reserved for the scorer; rename or move it"
            )
    return files, total


def prepare_submission(src: str | Path, work: str | Path, limits: SubmissionLimits) -> CheckedSubmission:
    """Check an unpacked submission with the kit's validator and make its clean copy (module docstring).

    ``check_submission_dir``, then the canonical zip (``submission.build_submission``: sorted members, fixed times and
    modes, so its SHA-256 follows from the files: the policy seed's salt (27), and the SHA-256 a participant's own
    ``build_submission`` of the same folder gives) checked by ``submission.check_zip`` (``agent.py`` at the root,
    parses, binds ``Agent``, names, sizes) and extracted into ``<work>/clean``.

    Raises:
        SubmissionError: on the first rule the submission breaks.

    """
    raw, out = Path(src).resolve(), Path(work)
    files, total = check_submission_dir(raw, limits)
    zip_path = out / "submission.zip"
    build_submission(raw, zip_path)
    checked = check_zip(zip_path, limits)
    clean = extract_submission(zip_path, out / "clean", limits)
    zip_path.unlink()
    return CheckedSubmission(checked.sha256, files, total, Path(clean.root), raw)


def world_readable(root: Path) -> bool:
    """Whether uid 65534 can read every file and enter every directory of ``root`` by their mode bits."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        if os.stat(dirpath).st_mode & 0o005 != 0o005:
            return False
        for name in filenames:
            if os.lstat(os.path.join(dirpath, name)).st_mode & 0o004 == 0:
                return False
    return True


@dataclass(frozen=True)
class Mount:
    """How the policy containers mount the submission: a host directory or a named volume (module docstring)."""

    kind: str  # "host_path" or "volume"
    host_dir: str | None = None
    volume: str | None = None


def _docker_call(docker: Sequence[str], *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*docker, *args], env=docker_cli_env(), stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=DOCKER_CALL_TIMEOUT_S, check=False,
    )  # fmt: skip


def _checked_call(docker: Sequence[str], *args: str) -> str:
    out = _docker_call(docker, *args)
    if out.returncode != 0:
        raise OrganiserError(f"docker {args[0]} failed ({out.returncode}): {out.stderr.strip()[:300]}")
    return out.stdout


def fill_volume(clean_dir: Path, image: str, docker: Sequence[str], run_id: str) -> str:
    """A fresh named volume holding ``clean_dir``'s files, filled through the socket alone (module docstring).

    Raises:
        OrganiserError: when a docker call fails (the volume is removed then).

    """
    token = secrets.token_hex(8)
    name, helper = f"sbf-sub-{token}", f"sbf-fill-{token}"
    labels = ["--label", f"{RUN_LABEL}={run_id}", "--label", f"{ROLE_LABEL}=submission"]
    _checked_call(docker, "volume", "create", *labels, name)
    try:
        _checked_call(
            docker, "create", "--pull", "never", "--name", helper, *labels, "--network", "none",
            "--mount", f"type=volume,source={name},target=/submission", image,
        )  # fmt: skip
        try:
            _checked_call(docker, "cp", f"{clean_dir}/.", f"{helper}:/submission")
        finally:
            _docker_call(docker, "rm", "-f", helper)
    except BaseException:
        _docker_call(docker, "volume", "rm", "-f", name)
        raise
    return name


def submission_mount(
    mode: str, sub: CheckedSubmission, image: str, docker: Sequence[str], run_id: str, environ: Mapping
) -> Mount:
    """The submission's mount by ``mode`` (module docstring, 'The submission's mount').

    Raises:
        OrganiserError: on ``host_path`` without the worker's ``SBF_SUBMISSION_HOST_DIR`` or with files uid 65534
            cannot read, or a failed volume fill.

    """
    host = environ.get(HOST_DIR_VAR) or ""
    if mode in ("auto", "host_path"):
        if host and os.path.isabs(host) and world_readable(sub.raw_dir):
            return Mount("host_path", host_dir=host)
        if mode == "host_path":
            raise OrganiserError(
                f"runtime.mount host_path: {HOST_DIR_VAR} is unset, not absolute, or the unpacked files are not "
                "world-readable (the policy runs as uid 65534)"
            )
    return Mount("volume", volume=fill_volume(sub.clean_dir, image, docker, run_id))


def cleanup(docker: Sequence[str], run_id: str, mount: Mount | None) -> None:
    """Remove this run's leftover policy containers (by label) and its volume; never raises."""
    try:
        out = _docker_call(docker, "ps", "-aq", "--filter", f"label={RUN_LABEL}={run_id}")
        ids = out.stdout.split() if out.returncode == 0 else []
        if ids:
            _docker_call(docker, "rm", "-f", *ids)
        if mount is not None and mount.volume:
            _docker_call(docker, "volume", "rm", "-f", mount.volume)
    except (OSError, subprocess.TimeoutExpired):
        pass


# ----- one episode ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class EpisodeContext:
    """What one episode's worker needs (plain values; pickled to the joblib workers)."""

    task: Task
    entropy: int
    submission_sha256: str
    image: str  # the policy image's ID
    mount: Mount
    meter: str  # a method of ``metering.METHODS``
    cgroup_root: str | None
    socket_path: str
    run_id: str
    docker: tuple[str, ...] = ("docker",)


@functools.lru_cache(maxsize=4)
def _instance(name: str):
    from sbfv.instance import load_instance

    return load_instance(name)


@functools.lru_cache(maxsize=4)
def _params(name: str, profile: str, gamma: float):
    from sbfv.policies.registry import GeneratorRef

    return GeneratorRef(profile, gamma).params(_instance(name))


def check_generator(task: Task) -> None:
    """The instance and generator this process builds are the task's (content, hash, ``generator_id``).

    Raises:
        OrganiserError: on any difference (another package, instance file or machine type made the task).

    """
    from sbfv.disruption.params import generator_id

    inst = _instance(task.instance)
    if (inst.hash, inst.content_digest) != (task.instance_hash, task.instance_digest):
        raise OrganiserError(f"instance {task.instance!r} here is not the task's (hash or content digest differs)")
    gid = generator_id(_params(task.instance, task.profile, task.gamma), inst)
    if gid != task.generator_id:
        raise OrganiserError(
            f"generator {gid[:12]}... here, the task's is {task.generator_id[:12]}...: build the task on this machine "
            "type (Q94; design §12 'Arithmetic across CPU types')"
        )


def _meter(ctx: EpisodeContext, cidfile: Path) -> metering.WeekCpu:
    def resolve():
        cid = metering.read_cidfile(cidfile)
        return metering.cpu_reader(ctx.meter, cid, cgroup_root=ctx.cgroup_root, socket_path=ctx.socket_path)

    return metering.WeekCpu(resolve, budget_s=ctx.task.wire.cpu_budget_s, poll_s=metering.POLL_S[ctx.meter])


def fallback_counts(substitutions: Sequence[Sequence]) -> tuple[dict[str, int], dict[str, int]]:
    """(D9 weeks by code, by the owner's cause) of an episode's substitutions (week, code)."""
    by_code = Counter(str(code) for _w, code in substitutions)
    by_cause = Counter()
    for code, n in by_code.items():
        by_cause[CAUSE_GROUPS.get(code, "invalid")] += n
    causes = {c: by_cause.get(c, 0) for c in ("over_budget", "late", "invalid", "crashed")}
    return dict(sorted(by_code.items())), causes


def episode_world(task: Task, entropy: int, ep: TaskEpisode) -> tuple:
    """(instance, generator, omega, marks, D9 fallback) of one task episode, as the trusted runner builds them.

    The instance is the task's at its generator's rung (``Instance.at_rung(params.hawkes.gamma)``: that rung's warm
    start, §2.3; M5-O37 (b)), as ``hosting.trusted._load`` and ``evaluation.runner._resolve`` give it, and the
    fallback is ``NaiveFallback`` of the task's F_Q keyed by the instance's ``family_digest`` (its content at the
    file's own rung, which F_Q reads, since it reads no stock), as ``trusted._references`` and ``runner._fallback`` key
    it (design §12 "Warm start per rung"; M5 re-gate DET-M5R-3). At the file's own rung the two digests agree; at
    another rung ``Env.reset`` refuses a fallback keyed by the rung's content digest.

    Raises:
        OrganiserError: when omega's SHA-256 or harm differs from the task's (another machine type or code).

    """
    from sbfv.disruption.harm import episode_harm
    from sbfv.disruption.sampler import sample_omega
    from sbfv.marks import compute_marks
    from sbfv.policies.naive import NaiveFallback

    params = _params(task.instance, task.profile, task.gamma)
    inst = _instance(task.instance).at_rung(params.hawkes.gamma)
    n = ep.episode
    omega = sample_omega(inst, params, entropy, n, task.split)
    if omega.hash != ep.omega_sha256 or episode_harm(inst, omega, params.marks) != ep.harm_usd:
        raise OrganiserError(
            f"episode {n}: omega here differs from the task's (its SHA-256 or harm): the task was built on another "
            "machine type or code (Q94; design §12 'Arithmetic across CPU types'); rebuild it on the scoring machine"
        )
    marks = compute_marks(inst, omega)
    fallback = NaiveFallback(omega.generator_id, task.quantiles, instance_digest=inst.family_digest)
    return inst, params, omega, marks, fallback


def play_episode(ctx: EpisodeContext, ep: TaskEpisode) -> dict:
    """One episode: omega checked against the task, the policy container metered, the re-simulation, replay (53).

    The episode's instance, omega, marks and D9 fallback are ``episode_world``'s (the trusted runner's).

    Raises:
        OrganiserError: when omega's SHA-256 or harm differs from the task's (another machine type or code), or the
            meter could not start on a container that came up.

    """
    from sbfv.dynamics.env import Env
    from sbfv.evaluation.results import replay_checks, substitution_counts
    from sbfv.hosting.trusted import TimedTransport, _checks_record
    from sbfv.information.runner import play_wire_episode, replay
    from sbfv.omega.seeds import policy_seed
    from sbfv.oracle.lp import build_lp
    from sbfv.oracle.replay import trajectory_usd

    start = time.perf_counter()
    task = ctx.task
    n = ep.episode
    inst, _gen, omega, marks, fallback = episode_world(task, ctx.entropy, ep)
    pseed = policy_seed(ctx.entropy, task.split, n, ctx.submission_sha256)
    w = task.wire
    work = Path(tempfile.mkdtemp(prefix="sbf-episode-"))
    cidfile = work / "cid"
    meter = _meter(ctx, cidfile)
    transport = DockerTransport(
        ctx.image,
        ctx.mount.host_dir,
        volume=ctx.mount.volume,
        deadline_s=w.deadline_s,
        startup_s=w.startup_s,
        max_reply_bytes=w.max_reply_bytes,
        limits=task.container,
        docker=ctx.docker,
        stderr=subprocess.DEVNULL,  # no policy output anywhere (module docstring)
        episode_timeout_s=w.watchdog_s(inst.T),
        labels={ROLE_LABEL: "policy", RUN_LABEL: ctx.run_id},
        cidfile=cidfile,
    )
    transport.interrupt, transport.interrupt_poll_s = meter.interrupt, meter.poll_s
    timed = TimedTransport(transport)
    try:
        wired = play_wire_episode(
            Env(fallback=fallback),
            inst,
            timed,
            limits=WireLimits(max_reply_bytes=w.max_reply_bytes, bank_seconds=float(w.bank_seconds)),
            regime=task.regime,
            omega=omega,
            policy_seed=pseed,
            marks=marks,
            policy_name="submission",
            meter=meter,
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if not meter.started and transport.ready_s is not None:
        raise OrganiserError(f"episode {n}: the CPU meter did not start on a running container: {meter.errors}")
    traj = wired.trajectory
    # §9.4 'Scoring': the container is gone; re-simulate from the action log and the wire failures, to the cent
    again = replay(Env(fallback=fallback), inst, traj, regime=task.regime, omega=omega, policy_seed=pseed, marks=marks)
    checks = replay_checks(build_lp(inst, marks), traj, None, False)  # the bound needs J^oracle: the scorer checks it
    substitutions = [[int(t), str(code)] for t, code in wired.substitutions]
    by_code, by_cause = fallback_counts(substitutions)
    return {
        "episode": n,
        "stratum": ep.stratum,
        "harm_usd": ep.harm_usd,
        "omega_sha256": omega.hash,
        "J_agent_cents": traj.J_cents,
        "J_agent_usd": trajectory_usd(traj),
        "trajectory_sha256": traj.sha256(),
        "fallback_count": len(substitutions),
        "fallbacks": by_code,
        "fallback_causes": by_cause,
        "substitutions": substitutions,
        "stale": [list(s) for s in wired.stale],
        "invalid_entries": substitution_counts(traj)[0],
        "checks": _checks_record(checks),
        "rescored_equal": again.sha256() == traj.sha256() and again.J_cents == traj.J_cents,
        "cpu": meter.summary(),
        "round_trip_s": timed.summary(),
        "ready_s": transport.ready_s,
        "container_gone": transport.container_gone,
        "watchdog_fired": transport.watchdog_fired,
        "wall_s": time.perf_counter() - start,
    }


# ----- the ingestion -------------------------------------------------------------------------------------------------
def _write(path: Path, doc: Mapping) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, allow_nan=False) + "\n")
    os.replace(tmp, path)


def _say(*parts: object) -> None:
    print("ShockBench-Flow:", *parts, flush=True)


def episode_jobs(task: Task, environ: Mapping) -> int:
    """Episodes in parallel: ``SBF_EPISODE_JOBS``, else the task's, else the CPU count minus one (at least 1)."""
    raw = environ.get(EPISODE_JOBS_VAR)
    if raw:
        if not raw.isdecimal() or int(raw) < 1:
            raise OrganiserError(f"{EPISODE_JOBS_VAR} must be an integer >= 1, got {raw!r}")
        return int(raw)
    if task.runtime.episode_jobs is not None:
        return task.runtime.episode_jobs
    return max(1, (os.cpu_count() or 2) - 1)


def meter_method(task: Task, environ: Mapping) -> tuple[str, str | None]:
    """(the meter method, the host cgroup root): ``auto`` takes the cgroup when the host tree is mounted."""
    root = environ.get(metering.CGROUP_ROOT_VAR) or metering.DEFAULT_CGROUP_ROOT
    mounted = Path(root).is_dir()
    method = task.runtime.meter
    if method == "auto":
        method = "cgroup" if mounted else "docker_stats"
    if method == "cgroup" and not mounted:
        raise OrganiserError(f"runtime.meter cgroup: no host cgroup tree at {root} ({metering.CGROUP_ROOT_VAR})")
    return method, root if method == "cgroup" else None


def ingest(
    input_dir: str | Path,
    output_dir: str | Path,
    submission_dir: str | Path,
    *,
    environ: Mapping | None = None,
    docker: Sequence[str] = ("docker",),
    socket_path: str = metering.DOCKER_SOCKET,
) -> int:
    """The ingestion program (module docstring); returns the exit status and writes ``predictions.json``."""
    from sbfv.parallel import ordered_map

    env = os.environ if environ is None else environ
    t0 = time.perf_counter()
    out = Path(output_dir)
    try:
        task, entropy, key = load_task(input_dir)
    except OrganiserError as err:
        print(f"ShockBench-Flow: organiser error: {err}", file=sys.stderr)
        return ORGANISER
    head = {"schema": PREDICTIONS_SCHEMA, "phase": task.phase, "task_sha256": task.sha256}
    work = Path(tempfile.mkdtemp(prefix="sbf-ingest-"))
    run_id = env.get(RUN_ID_VAR) or f"sbf-{secrets.token_hex(8)}"
    mount = None
    try:
        try:
            sub = prepare_submission(submission_dir, work, task.submission)
        except SubmissionError as err:
            _write(out / PREDICTIONS_FILE, sign({**head, "refused": {"code": err.code, "message": str(err)}}, key))
            print(f"ShockBench-Flow: the submission is refused: {err}", file=sys.stderr)
            return REFUSED
        if package_sha256() != task.package_sha256:
            raise OrganiserError("the runner's package is not the one the task was built with (package_sha256)")
        check_generator(task)
        try:
            image = image_id(task.runtime.policy_image, docker)
        except (ValueError, OSError, subprocess.TimeoutExpired) as err:
            raise OrganiserError(f"the policy image: {err} (load it on the worker; --pull never)") from None
        if task.runtime.policy_image_id is not None and image != task.runtime.policy_image_id:
            raise OrganiserError(f"policy image {task.runtime.policy_image!r} is {image}, the task pins another ID")
        method, cgroup_root = meter_method(task, env)
        jobs = episode_jobs(task, env)
        mount = submission_mount(task.runtime.mount, sub, image, docker, run_id, env)
        _say(
            f"{task.phase} task: {len(task.episodes)} episodes of {task.instance}, regime {task.regime}; "
            f"submission {sub.sha256[:12]} ({sub.files} files, {sub.bytes} bytes), mount {mount.kind}, meter {method}, "
            f"{jobs} in parallel, {task.wire.cpu_budget_s:g} s CPU per week"
        )
        ctx = EpisodeContext(task, entropy, sub.sha256, image, mount, method, cgroup_root, socket_path, run_id,
                             tuple(docker))  # fmt: skip
        try:
            episodes = ordered_map(functools.partial(play_episode, ctx), task.episodes, jobs)
        except OrganiserError:
            raise
        except Exception as err:  # noqa: BLE001 - a worker's OrganiserError comes back wrapped by joblib at times
            if "OrganiserError" in f"{type(err).__name__}{err}":
                raise OrganiserError(str(err)) from None
            raise
        total = sum(e["fallback_count"] for e in episodes)
        doc = {
            **head,
            "submission": {"sha256": sub.sha256, "files": sub.files, "bytes": sub.bytes, "mount": mount.kind},
            "policy_image": image,
            "package_sha256": task.package_sha256,
            "regime": task.regime,
            "metering": {"method": method, "cpu_budget_s": task.wire.cpu_budget_s, "poll_s": metering.POLL_S[method]},
            "episode_jobs": jobs,
            "machine": machine(),
            "episodes": episodes,
            "fallback_count": total,
            "wall_s": time.perf_counter() - t0,
        }
        _write(out / PREDICTIONS_FILE, sign(doc, key))
        walls = sorted(e["wall_s"] for e in episodes)
        _say(
            f"{len(episodes)} episodes played in {doc['wall_s']:.1f} s (per episode median {walls[len(walls) // 2]:.1f}"
            f" s, max {walls[-1]:.1f} s); {total} D9 weeks"
        )
        return DONE
    except OrganiserError as err:
        print(f"ShockBench-Flow: organiser error: {err}", file=sys.stderr)
        return ORGANISER
    finally:
        cleanup(docker, run_id, mount)
        shutil.rmtree(work, ignore_errors=True)


# ----- the reference -------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class _ReferenceTask:
    """The fields ``hosting.trusted._references`` reads of its task: one code for the reference and the scorer."""

    instance: str
    instance_hash: str
    params: object
    entropy: int
    split: str
    quantiles: Mapping
    check_harm: bool = True


def reference_row(rtask: _ReferenceTask, scenario: Scenario) -> dict:
    """One episode's sealed row: omega's SHA-256, the anchor's J^naive and V5, the oracle on omega and omega^0.

    ``hosting.trusted._references``, the trusted scorer's own code (the anchor prediction-free, the oracle LP, the
    event-free twin, the exclusion cause), so a Codabench score equals ``score_submission.py``'s on the same episodes.
    The anchor's seed is the baselines' (``trusted.BASELINE_SEED_ID``): naive draws nothing from it.
    """
    from sbfv.hosting.trusted import BASELINE_SEED_ID, _checks_record, _references
    from sbfv.omega.seeds import policy_seed

    inst = _instance(rtask.instance)
    if inst.hash != rtask.instance_hash:
        raise OrganiserError("the worker loaded another instance than the builder's")
    inst = inst.at_rung(rtask.params.hawkes.gamma)  # the rung's warm start, as ``trusted._load`` (``episode_world``)
    n = scenario.episode
    ref = _references(inst, rtask, scenario, policy_seed(rtask.entropy, rtask.split, n, BASELINE_SEED_ID))
    return {
        "episode": n,
        "stratum": scenario.stratum,
        "harm_usd": scenario.harm,
        "omega_sha256": ref.omega.hash,
        **ref.record(),
        "J_oracle_usd": ref.oracle.J_usd if ref.optimal else None,
        "anchor_checks": _checks_record(ref.anchor_checks),
    }


def reference_rows(
    instance: str, instance_hash: str, params, entropy: int, split: str, quantiles: Mapping, scenarios, n_jobs: int
) -> list[dict]:
    """``reference_row`` of every scenario, over ``n_jobs`` workers, in order (the builder's)."""
    from sbfv.parallel import ordered_map

    rtask = _ReferenceTask(instance, instance_hash, params, entropy, split, dict(quantiles))
    return ordered_map(functools.partial(reference_row, rtask), list(scenarios), n_jobs)


def anchor_failures(rows: Sequence[Mapping]) -> list[str]:
    """The anchor's V5 failures over the rows ("ep<n>: ..."): a reference with any is never written (a bug, §6.2)."""
    from sbfv.evaluation.results import ReplayChecks

    return [f"ep{r['episode']}: {f}" for r in rows for f in ReplayChecks(**r["anchor_checks"]).failures]


def task_bytes(doc: Mapping) -> bytes:
    """``task.json``'s bytes as written (the task's SHA-256 is of these bytes)."""
    return (json.dumps(doc, indent=1, allow_nan=False) + "\n").encode()


def build_documents(
    *,
    phase: str,
    inst,
    instance_name: str,
    profile: str,
    gamma: float,
    params,
    regime: str,
    fq_replications: int,
    quantiles: Mapping[tuple, float],
    cuts,
    cut_entropy: int,
    n_per_stratum: Sequence[int],
    fill: tuple,
    entropy: int,
    wire: Wire,
    container: ContainerLimits,
    max_bytes: int,
    max_files: int,
    runtime: Runtime,
    n_jobs: int = 1,
    command: str | None = None,
    split: str | None = None,
) -> tuple[bytes, dict, dict]:
    """(``task.json``'s bytes, ``secret.json``, ``reference.json``) of one Codabench task (the reference builder's).

    ``fill`` is the split's strata fill (``split.fill_strata`` or the scripts layer's cache: scenarios, candidates
    drawn, unfilled strata) on ``cuts``; ``quantiles`` are naive's F_Q of ``params`` from ``fq_replications``. Each
    scenario's reference row is ``reference_row`` (the anchor, the oracle on omega and omega^0, the exclusion); the
    predictions key is fresh (``secrets.token_hex(32)``); on the hidden split ``secret.json`` holds the root and
    ``task.json`` its commitment only. ``split`` defaults to the phase's (``PHASES``); ``dev`` on the Development
    phase is the local test's (``PHASE_SPLITS``).

    Raises:
        OrganiserError: on a phase outside ``PHASES`` or a split outside its ``PHASE_SPLITS``, an unfilled stratum
            (never padded), or an anchor that fails V5 on any episode (a bug, §6.2).

    """
    from sbfv.disruption.params import generator_id
    from sbfv.scoring.rss import STRATUM_WEIGHTS

    if phase not in PHASES:
        raise OrganiserError(f"phase must be one of {tuple(PHASES)}, got {phase!r}")
    split = PHASES[phase] if split is None else split
    if split not in PHASE_SPLITS[phase]:
        raise OrganiserError(f"phase {phase!r} scores a split of {PHASE_SPLITS[phase]}, not {split!r}")
    check_root(split, entropy)
    scenarios, drawn, unfilled = fill
    if unfilled:
        raise OrganiserError(f"strata {list(unfilled)} unfilled after {drawn} candidates: raise max_candidates")
    rows = reference_rows(instance_name, inst.hash, params, entropy, split, quantiles, scenarios, n_jobs)
    failed = anchor_failures(rows)
    if failed:
        raise OrganiserError(f"the anchor failed V5 on {len(failed)} check(s) (a bug, §6.2): {failed[:3]}")
    key = secrets.token_hex(32)
    where = machine()
    doc = task_document(
        phase=phase,
        split=split,
        instance=instance_name,
        instance_id=inst.instance_id,
        instance_hash=inst.hash,
        instance_digest=inst.content_digest,
        profile=profile,
        gamma=gamma,
        generator_id=generator_id(params, inst),
        regime=regime,
        anchor_regime="prediction_free",
        fq_replications=fq_replications,
        fq_quantiles=quantiles_record(quantiles),
        cut_points={
            "draws": cuts.draws,
            "entropy": cut_entropy,
            "quantiles": list(cuts.quantiles),
            "values_usd": list(cuts.values),
            "generator_id": cuts.generator_id,
        },  # fmt: skip
        n_per_stratum=[int(x) for x in n_per_stratum],
        candidates_drawn=int(drawn),
        episodes=[{k: r[k] for k in ("episode", "stratum", "harm_usd", "omega_sha256")} for r in rows],
        entropy=entropy if split == "dev" else None,
        entropy_commitment=entropy_commitment(split, entropy),
        package_version=sbfv.__version__,
        package_sha256=package_sha256(),
        wire=asdict(wire),
        container=asdict(container),
        submission={"max_bytes": int(max_bytes), "max_files": int(max_files)},
        runtime=asdict(runtime),
        machine=where,
        command=command,
    )
    raw = task_bytes(doc)
    secret = {"schema": SECRET_SCHEMA, "predictions_key": key, **({"entropy": entropy} if split == "hidden" else {})}
    reference = {
        "schema": REFERENCE_SCHEMA,
        "phase": phase,
        "task_sha256": hashlib.sha256(raw).hexdigest(),
        "predictions_key": key,
        "weights": list(STRATUM_WEIGHTS),
        "episodes": rows,
        "machine": where,
        "command": command,
    }
    return raw, secret, reference


def write_documents(out_dir: str | Path, raw: bytes, secret: Mapping, reference: Mapping) -> dict[str, Path]:
    """Write a task's ``input_data/{task,secret}.json`` and ``reference_data/reference.json`` under ``out_dir``.

    ``secret.json`` is written 0600 (the hidden root and the predictions key); the directories are the bundle's
    ``<phase>/input_data`` and ``<phase>/reference_data`` (``deploy/codabench/build_bundle.py`` copies them).
    """
    base = Path(out_dir)
    inp, ref = base / "input_data", base / "reference_data"
    inp.mkdir(parents=True, exist_ok=True)
    ref.mkdir(parents=True, exist_ok=True)
    (inp / TASK_FILE).write_bytes(raw)
    fd = os.open(inp / SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(secret, indent=1) + "\n")
    _write(ref / REFERENCE_FILE, reference)
    return {"task": inp / TASK_FILE, "secret": inp / SECRET_FILE, "reference": ref / REFERENCE_FILE}


# ----- the scoring ---------------------------------------------------------------------------------------------------
class ScoringError(RuntimeError):
    """The documents disagree or a check failed: no score is written (exit 1, or 2 for a refused submission)."""

    def __init__(self, message: str, status: int = CHECK_FAILED) -> None:
        super().__init__(message)
        self.status = status


def score_documents(pred: Mapping, ref: Mapping, phase: str) -> tuple[dict, dict]:
    """(scores.json, the detail) from the predictions and the reference (module docstring, 'scoring').

    Raises:
        ScoringError: on another schema or phase, a signature that fails, another task, a refused submission
            (status 2), an episode set or a stratum that differs, or a failed check (RSS undefined, with its reason).

    """
    from sbfv.hosting.trusted import rss_table
    from sbfv.oracle.replay import oracle_bound_holds

    if ref.get("schema") != REFERENCE_SCHEMA or ref.get("phase") != phase:
        raise ScoringError(f"reference.json is not a {phase} reference of schema {REFERENCE_SCHEMA}")
    key = bytes.fromhex(str(ref["predictions_key"]))
    if pred.get("schema") != PREDICTIONS_SCHEMA or not verify(pred, key):
        raise ScoringError("predictions.json is not the ingestion's (schema or signature): nothing is scored")
    if pred.get("task_sha256") != ref["task_sha256"] or pred.get("phase") != phase:
        raise ScoringError("predictions.json was made for another task than this reference's")
    if "refused" in pred:
        r = pred["refused"]
        raise ScoringError(f"the submission was refused at ingestion: {r['message']}", REFUSED)
    by_ref = {int(e["episode"]): e for e in ref["episodes"]}
    by_pred = {int(e["episode"]): e for e in pred["episodes"]}
    if len(by_pred) != len(pred["episodes"]) or set(by_pred) != set(by_ref):
        missing, extra = sorted(set(by_ref) - set(by_pred)), sorted(set(by_pred) - set(by_ref))
        raise ScoringError(f"the predictions' episodes differ from the reference's (missing {missing}, extra {extra})")
    records = []
    for n in sorted(by_ref):
        r, p = by_ref[n], by_pred[n]
        if int(p["stratum"]) != int(r["stratum"]) or p.get("omega_sha256") != r["omega_sha256"]:
            raise ScoringError(f"episode {n}: its stratum or omega differs from the reference's")
        optimal = r["J_oracle_cents"] is not None
        checks = {**p["checks"], "oracle_bound_holds": (
            oracle_bound_holds(float(r["J_oracle_usd"]), float(p["J_agent_usd"])) if optimal else None
        )}  # fmt: skip
        records.append(
            {
                "episode": n,
                "stratum": int(r["stratum"]),
                "excluded": r["excluded"],
                "J_policy_cents": int(p["J_agent_cents"]),
                "J_naive_cents": int(r["J_naive_cents"]),
                "J_oracle_cents": r["J_oracle_cents"],
                "checks": checks,
                "anchor_checks": r["anchor_checks"],
                "rescored_equal": bool(p["rescored_equal"]),
            }
        )
    table = rss_table(records, tuple(ref["weights"]))
    fallbacks = sum(int(e["fallback_count"]) for e in pred["episodes"])
    if fallbacks != int(pred["fallback_count"]):
        raise ScoringError("predictions.json's fallback_count is not the sum of its episodes'")
    if table["pooled"] is None:
        raise ScoringError(f"RSS is undefined: {table['pooled_reason']}")
    rss_key, fb_key = SCORE_KEYS[phase]
    scores = {rss_key: round(float(table["pooled"]), RSS_DIGITS), fb_key: fallbacks}
    causes = Counter()
    for e in pred["episodes"]:
        causes.update(e["fallback_causes"])
    detail = {
        "phase": phase,
        "rss_pooled": table["pooled"],
        "rss_strata": {s: v["rss"] for s, v in table["strata"].items()},
        "n_strata": {s: v["n"] for s, v in table["strata"].items()},
        "excluded": sum(r["excluded"] is not None for r in records),
        "episodes": len(records),
        "fallback_count": fallbacks,
        "fallback_causes": dict(sorted(causes.items())),
    }
    return scores, detail


def score(input_dir: str | Path, output_dir: str | Path, *, phase: str) -> int:
    """The scoring program: ``<input>/res/predictions.json`` and ``<input>/ref/reference.json`` to ``scores.json``."""
    base, out = Path(input_dir), Path(output_dir)
    try:
        pred = _read_json(base / "res" / PREDICTIONS_FILE, "predictions")
        ref = _read_json(base / "ref" / REFERENCE_FILE, "reference")
        scores, detail = score_documents(pred, ref, phase)
    except OrganiserError as err:
        print(f"ShockBench-Flow scoring: {err}", file=sys.stderr)
        return CHECK_FAILED
    except ScoringError as err:
        print(f"ShockBench-Flow scoring: {err}", file=sys.stderr)
        return err.status
    except (KeyError, TypeError, ValueError) as err:
        print(f"ShockBench-Flow scoring: malformed document ({type(err).__name__}: {err})", file=sys.stderr)
        return CHECK_FAILED
    out.mkdir(parents=True, exist_ok=True)
    _write(out / DETAIL_FILE, detail)
    _write(out / SCORES_FILE, scores)
    print(json.dumps(scores), flush=True)
    return DONE


# ----- the entry point -----------------------------------------------------------------------------------------------
USAGE = (
    "usage: python -m sbfv.hosting.codabench ingest <input_data> <output> <ingested_program>\n"
    "       python -m sbfv.hosting.codabench score|score-final <input> <output>"
)


def main(argv: Sequence[str]) -> int:
    """``ingest``, ``score`` or ``score-final`` (module docstring); returns the exit status."""
    args = list(argv)
    if args[:1] == ["ingest"] and len(args) == 4:
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))  # a stop runs the cleanup (the finally blocks)
        return ingest(args[1], args[2], args[3])
    if args[:1] in (["score"], ["score-final"]) and len(args) == 3:
        return score(args[1], args[2], phase="final" if args[0] == "score-final" else "development")
    print(USAGE, file=sys.stderr)
    return 64


if __name__ == "__main__":
    # run the package's copy of this module, not __main__'s, so the episodes' functions pickle by their package name
    # for the joblib workers (a worker cannot import __main__ of ``python -m``)
    from sbfv.hosting import codabench as _module

    sys.exit(_module.main(sys.argv[1:]))
