"""Stored-action conformance, V24 (milestone M4, stream "conformance").

Design §9.4 "Scoring", §9.5 "Conformance", §10 V24; Q73, Q94, Q100 (5).

Conformance re-simulates each reference policy's stored action log and compares integer cents (24); it solves no LP
at all (§9.4 "re-simulation runs no LP", §9.5: not the LP baselines' warm solves, Q95, and not naive's reset-time plan
(22) either) and never re-samples omega. Pass rule: exact on the pinned Linux image (``PINNED_IMAGE`` on
``PINNED_PLATFORM``, run by Docker on the worker VM), ±1 cent per week against macOS arm64 (Q100 (5)). Readings
(design §12 M4 row "Conformance record"):

- **The record ships omega**: the stored ``.npz`` beside the record (``save_entry``), its hash checked at replay,
  since omega regenerated from its key differs across platforms in its last bits (§12 "Calibrated baseline of `tiny`";
  0 of 24 omega pins hold on Linux aarch64).
- **The fallback travels with the record** (``FallbackRecord``): naive's F_Q quantiles as ``float.hex``, the
  ``generator_id``, the instance content digest and Q98's ``end_aware``, the episode's D9 spec as data; only "naive"
  and an end-aware ``NaiveFallback`` (the D9 fallbacks of §9.3, Q98) make a record. The fallback's action of each D9
  week is stored too (``fallback_actions``: the week's ``StepRecord.requested`` and ``override_requested`` of the
  original run, in the action format), and ``replay_record`` installs a callable fallback that plays them and raises on
  any other week, so a replay rebuilds neither F_Q (1,000 generator replications, platform-specific) nor naive's plan
  (22) (a ``linprog`` inside ``Env.reset`` whenever a naive spec is installed): no solver runs, and a week that takes
  the fallback on one side only shows as an error or a cent difference.
- **Regimes** are registry names only (``information.theta.REGIME_NAMES``); a custom theta is refused.
- **±1 cent per week** applies to each weekly C^¢_t and to S^¢_T (the adopted reading), so J^¢ may differ by up to
  T + 1 cents and week T's reward r_T = -C^¢_T + S^¢_T of (25) by 2: looser than the owner's "±1 cent per week" read on
  r_t, which would bound J^¢ by T (said so in the §12 row); SHA-256 equality is reported, never gated (a float that
  moves by an ulp changes the hash, not the cents).
- ``provenance`` records the platform and versions of the producing run (never hashed into the comparison).
"""

import copy
import json
import math
import os
import platform
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal

import numpy as np

from sbfv.dynamics.env import Env, took_fallback
from sbfv.dynamics.state import Trajectory
from sbfv.evaluation.timings import IMAGE_DIGEST_VAR, installed_version
from sbfv.information import runner
from sbfv.information.theta import REGIME_NAMES
from sbfv.instance.io import canonical_json
from sbfv.instance.schema import Instance
from sbfv.marks import compute_marks
from sbfv.omega.container import Omega, load_omega
from sbfv.oracle.replay import trajectory_usd
from sbfv.policies.naive import NaiveFallback


CONFORMANCE_SCHEMA = 1
CROSS_PLATFORM_CENTS = 1  # V24: ±1 cent per week (and on S^¢_T) against macOS arm64 (Q73)
# the pinned Linux image of V24 (Q100 (5)): referenced by digest only, never pulled or re-tagged by tag, run with
# ``--platform PINNED_PLATFORM`` on the worker VM (SBF_VM_HOST, x86_64; Docker 26.1.5). The digest is an OCI image index
# of linux/amd64 and linux/arm64 images, so the platform names the one image V24 runs: its amd64 manifest is
# ``PINNED_PLATFORM_MANIFEST`` (registry query of 2026-09-27: GET ghcr.io/v2/astral-sh/uv/manifests/<index digest>)
PINNED_IMAGE = (
    "ghcr.io/astral-sh/uv:python3.13-bookworm-slim"
    "@sha256:531f855bda2c73cd6ef67d56b733b357cea384185b3022bd09f05e002cd144ca"
)
PINNED_PLATFORM = "linux/amd64"
PINNED_PLATFORM_MANIFEST = "sha256:847b5e690018bc6b9d97a0848da65f721b785f1e78d9c7067b8947c7010b2718"
# Env's fallback specs as record kinds: "naive", "naive_plain", a NaiveFallback ("generator"), None ("none"); only
# "naive" and an end-aware "generator" make a conformance record (``conformance_record``), the others are test-only
FALLBACK_KINDS = ("naive", "naive_plain", "generator", "none")
RECORD_FALLBACK_KINDS = ("naive", "generator")  # the D9 fallbacks of §9.3 (Q98); "generator" with end_aware True
Mode = Literal["exact", "cross_platform"]
PROVENANCE_KEYS = (  # what ``provenance`` records of the producing run (never compared, never hashed)
    "system",
    "machine",
    "cpu",
    "python",
    "numpy",
    "scipy",
    "highspy",
    "numba",
    "package",
    "image",
    "openblas_coretype",
)
_HEX = frozenset("0123456789abcdef")
_STRING_KINDS = {"naive": True, "naive_plain": False, "none": True}  # kind -> the end_aware it states
_NAME_UNSAFE = re.compile(r"[^A-Za-z0-9_.+=-]")


def _is_digest(x: object) -> bool:
    return isinstance(x, str) and len(x) == 64 and set(x) <= _HEX


def _quantile_key(key: object) -> tuple:
    """A quantile key (c, pool, j, k) as a tuple of JSON scalars: ints (not bools) and strings only."""
    if not isinstance(key, (tuple, list)) or not key:
        raise ValueError(f"a quantile key must be a non-empty tuple (c, pool, j, k), got {key!r}")
    out = []
    for x in key:
        if isinstance(x, bool) or not isinstance(x, (int, str)):
            raise ValueError(f"a quantile key holds ints and strings only, got {key!r}")
        out.append(int(x) if isinstance(x, int) else str(x))
    return tuple(out)


def _quantile_text(text: object) -> float:
    """The float of a quantile's ``float.hex`` text, refusing any other spelling, a non-finite or a negative value."""
    if not isinstance(text, str):
        raise ValueError(f"a quantile must be the float.hex text of a float, got {text!r}")
    try:
        q = float.fromhex(text)
    except (ValueError, OverflowError) as err:
        raise ValueError(f"a quantile must be the float.hex text of a float, got {text!r}") from err
    if not math.isfinite(q) or q < 0.0 or q.hex() != text:
        raise ValueError(f"a quantile must be float.hex of a finite float >= 0, got {text!r}")
    return q


@dataclass(frozen=True)
class FallbackRecord:
    """The episode's D9 fallback as data (``dynamics.env.FallbackSpec`` without callables).

    ``kind`` "naive" and "naive_plain" are Env's string specs (F_Q the point mass at 0); "generator" is a
    ``NaiveFallback`` whose quantiles are kept as sorted (key, ``float.hex``) pairs; "none" plays the empty action.
    A string kind states its ``end_aware``: True for "naive" (and "none", where it means nothing), False for
    "naive_plain".

    Raises:
        ValueError: on a kind outside ``FALLBACK_KINDS``, generator fields on a string kind or missing on "generator",
            or a quantile text that is not a ``float.hex`` of a finite float >= 0.

    """

    kind: str
    generator_id: str | None = None
    instance_digest: str | None = None
    fq_quantile: tuple[tuple[tuple, str], ...] = ()  # ((c, pool, j, k), float.hex(q)), sorted by repr(key)
    end_aware: bool = True

    def __post_init__(self) -> None:
        if self.kind not in FALLBACK_KINDS:
            raise ValueError(f"fallback kind must be one of {FALLBACK_KINDS}, got {self.kind!r}")
        if type(self.end_aware) is not bool:
            raise ValueError(f"end_aware must be a bool, got {self.end_aware!r}")
        if self.kind in _STRING_KINDS:
            if self.generator_id is not None or self.instance_digest is not None or self.fq_quantile:
                raise ValueError(f"the string fallback {self.kind!r} carries no generator, digest or quantiles")
            if self.end_aware is not _STRING_KINDS[self.kind]:
                raise ValueError(f"the string fallback {self.kind!r} states end_aware={_STRING_KINDS[self.kind]}")
            return
        if not _is_digest(self.generator_id):
            raise ValueError(f"a generator fallback needs its generator_id (SHA-256 hex), got {self.generator_id!r}")
        if self.instance_digest is not None and not _is_digest(self.instance_digest):
            raise ValueError(f"instance_digest must be a SHA-256 hex digest or None, got {self.instance_digest!r}")
        pairs = []
        for item in self.fq_quantile:
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                raise ValueError(f"a quantile entry is a (key, float.hex) pair, got {item!r}")
            key = _quantile_key(item[0])
            _quantile_text(item[1])
            pairs.append((key, item[1]))
        ordered = tuple(sorted(pairs, key=lambda kv: repr(kv[0])))
        if len({repr(k) for k, _ in ordered}) != len(ordered):
            raise ValueError("a quantile key appears twice")
        object.__setattr__(self, "fq_quantile", ordered)

    def spec(self):
        """The ``Env`` fallback spec this record stands for: "naive", "naive_plain", a ``NaiveFallback`` or None."""
        if self.kind == "none":
            return None
        if self.kind in _STRING_KINDS:
            return self.kind
        return NaiveFallback(
            self.generator_id,
            {key: _quantile_text(text) for key, text in self.fq_quantile},
            instance_digest=self.instance_digest,
            end_aware=self.end_aware,
        )

    @staticmethod
    def of(spec) -> "FallbackRecord":
        """The record of an ``Env`` fallback spec.

        Raises:
            ValueError: on a callable spec (a test-only fallback has no record), or a string that is no Env spec.

        """
        if spec is None:
            return FallbackRecord("none")
        if isinstance(spec, NaiveFallback):
            return FallbackRecord(
                "generator",
                generator_id=spec.generator_id,
                instance_digest=spec.instance_digest,
                fq_quantile=tuple((_quantile_key(k), float(q).hex()) for k, q in spec.fq_quantile.items()),
                end_aware=spec.end_aware,
            )
        if isinstance(spec, str) and spec in ("naive", "naive_plain"):
            return FallbackRecord(spec, end_aware=_STRING_KINDS[spec])
        if callable(spec):
            raise ValueError("a callable fallback (test-only) has no conformance record")
        raise ValueError(f"not an Env fallback spec: {spec!r}")

    def as_json(self) -> dict:
        return {
            "kind": self.kind,
            "generator_id": self.generator_id,
            "instance_digest": self.instance_digest,
            "fq_quantile": [[list(k), text] for k, text in self.fq_quantile],
            "end_aware": self.end_aware,
        }


@dataclass(frozen=True)
class ConformanceRecord:
    """One reference trajectory as a V24 record: what re-simulates it and the integer cents it must reproduce."""

    schema: int
    instance_hash: str
    instance_digest: str
    omega_hash: str
    regime: str  # a registry name
    policy: str
    policy_seed: int
    fallback: FallbackRecord
    actions: tuple  # Trajectory.actions as stored (JSON-safe)
    fallback_actions: tuple[tuple[int, dict], ...]  # (week, the fallback's action as applied) of every D9 week
    wire_failures: tuple[tuple[int, str], ...]
    week_cents: tuple[int, ...]  # C^¢_t, t = 1..T (24)
    salvage_cents: int  # S^¢_T
    J_cents: int
    J_usd: str  # float.hex of replay.trajectory_usd
    trajectory_sha256: str
    provenance: tuple[tuple[str, str], ...]  # system, machine, python, numpy, scipy, highspy, numba, package, image

    @property
    def name(self) -> str:
        """The entry's file stem: policy, regime, omega hash prefix and policy seed, filename-safe."""
        parts = (self.policy or "anonymous", self.regime, self.omega_hash[:16], str(self.policy_seed))
        return "__".join(_NAME_UNSAFE.sub("-", p) for p in parts)


@dataclass(frozen=True)
class ConformanceResult:
    """A replay against its record: per-week and salvage differences in cents, J's difference, and SHA equality."""

    week_diffs: tuple[int, ...]
    salvage_diff: int
    J_diff: int
    sha_equal: bool  # reported, never gated

    def passes(self, mode: Mode) -> bool:
        """Mode "exact": every difference 0; "cross_platform": |d| <= ``CROSS_PLATFORM_CENTS`` weekly and on S^¢_T.

        Raises:
            ValueError: on another mode.

        """
        if mode == "exact":
            return self.salvage_diff == 0 and self.J_diff == 0 and all(d == 0 for d in self.week_diffs)
        if mode == "cross_platform":
            tol = CROSS_PLATFORM_CENTS
            return abs(self.salvage_diff) <= tol and all(abs(d) <= tol for d in self.week_diffs)
        raise ValueError(f"mode must be 'exact' or 'cross_platform', got {mode!r}")


# ----- making a record -----------------------------------------------------------------------------------------------
def _cpu() -> str:
    """The CPU model: /proc/cpuinfo's first "model name" on Linux, else ``platform.processor()`` (no subprocess)."""
    info = Path("/proc/cpuinfo")
    if info.is_file():
        for line in info.read_text(errors="replace").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor()


def machine_provenance() -> dict[str, str]:
    """The producing run's platform and versions (``PROVENANCE_KEYS``), read without importing highspy or numba.

    ``image`` is ``os.environ[timings.IMAGE_DIGEST_VAR]`` (set by the conformance Dockerfile to ``PINNED_IMAGE``),
    else ""; ``openblas_coretype`` is ``OPENBLAS_CORETYPE`` when set (OpenBLAS picks its kernels per CPU otherwise).
    """
    import numpy
    import scipy

    return {
        "system": platform.system(),
        "machine": platform.machine(),
        "cpu": _cpu(),
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "highspy": installed_version("highspy") or "not installed",
        "numba": installed_version("numba") or "not installed",
        "package": installed_version("shockbench-flow") or "not installed",
        "image": os.environ.get(IMAGE_DIGEST_VAR, ""),
        "openblas_coretype": os.environ.get("OPENBLAS_CORETYPE", ""),
    }


def _action_of(week: int, record) -> dict:
    """The fallback's action as applied in a D9 week, in the wire format: ``requested`` and ``override_requested``.

    Slots in increasing order (the record keeps them sorted); ``overrides`` None when the fallback overrode nothing
    (naive never does, §8.1 step 6) and no hold (the record keeps none; naive sends none).
    """
    flows = sorted(record.requested.items())
    out = {"week": int(week), "flows": {"slot": [int(s) for s, _ in flows], "qty": [float(q) for _, q in flows]}}
    ov = sorted(record.override_requested.items())
    out["overrides"] = {"slot": [int(s) for s, _ in ov], "qty": [float(q) for _, q in ov]} if ov else None
    out["hold"] = None
    return out


def conformance_record(
    inst: Instance, traj: Trajectory, *, policy_seed: int, fallback, provenance: Mapping[str, str] | None = None
) -> ConformanceRecord:
    """The record of a finished trajectory (``fallback`` its episode's ``Env`` spec, a D9 fallback of §9.3).

    ``fallback_actions`` are read from the trajectory's D9 weeks (``dynamics.env.took_fallback``). ``provenance``
    defaults to ``machine_provenance()``.

    Raises:
        ValueError: on a failed or unfinished trajectory, a regime that is no registry name, a fallback other than
            "naive" or an end-aware ``NaiveFallback`` (``RECORD_FALLBACK_KINDS``; "naive_plain", None and callables
            are test-only), or an instance whose hash or content digest is not the trajectory's.

    """
    if traj.failed is not None:
        raise ValueError(f"a failed trajectory ({traj.failed}) has no conformance record")
    if traj.salvage_cents is None or traj.salvage is None or len(traj.records) != inst.T:
        raise ValueError("an unfinished trajectory has no conformance record")
    if traj.regime not in REGIME_NAMES:
        raise ValueError(f"V24 records registry regimes only ({REGIME_NAMES}), got {traj.regime!r}")
    inst = inst.at_digest(traj.instance_digest)  # the trajectory's rung: its warm start block (§2.3; M5-O37 (b))
    if inst.hash != traj.instance_hash or inst.content_digest != traj.instance_digest:
        raise ValueError("the instance is not the trajectory's (hash or content digest, V3)")
    fb = FallbackRecord.of(fallback)
    if fb.kind not in RECORD_FALLBACK_KINDS or not fb.end_aware:
        raise ValueError(f"only 'naive' or an end-aware NaiveFallback make a record (§9.3, Q98), got {fb.kind!r}")
    if fb.kind == "generator" and fb.instance_digest != inst.family_digest:
        raise ValueError("the fallback's F_Q was computed for other instance content (or binds none)")
    if isinstance(policy_seed, bool) or not isinstance(policy_seed, int) or policy_seed < 0:
        raise ValueError(f"policy_seed must be an integer >= 0, got {policy_seed!r}")
    prov = machine_provenance() if provenance is None else dict(provenance)
    return ConformanceRecord(
        schema=CONFORMANCE_SCHEMA,
        instance_hash=traj.instance_hash,
        instance_digest=traj.instance_digest,
        omega_hash=traj.omega_hash,
        regime=traj.regime,
        policy=traj.policy,
        policy_seed=int(policy_seed),
        fallback=fb,
        actions=tuple(copy.deepcopy(traj.actions)),
        fallback_actions=tuple((r.week, _action_of(r.week, r)) for r in traj.records if took_fallback(r)),
        wire_failures=tuple((int(w), str(c)) for w, c in traj.wire_failures),
        week_cents=tuple(int(r.cost_cents) for r in traj.records),
        salvage_cents=int(traj.salvage_cents),
        J_cents=int(traj.J_cents),
        J_usd=float(trajectory_usd(traj)).hex(),
        trajectory_sha256=traj.sha256(),
        provenance=tuple(sorted((str(k), str(v)) for k, v in prov.items())),
    )


# ----- the JSON form -------------------------------------------------------------------------------------------------
_FIELDS = tuple(f.name for f in fields(ConformanceRecord))


def dumps(rec: ConformanceRecord) -> str:
    """Canonical JSON of a record (``instance.io`` canonical form; floats as ``float.hex`` where exactness matters).

    The actions keep their JSON floats: Python writes a float by its shortest round-trip ``repr``, so ``loads`` gives
    the same double; ``J_usd`` and the quantiles are ``float.hex`` texts.
    """
    doc = {
        "schema": rec.schema,
        "instance_hash": rec.instance_hash,
        "instance_digest": rec.instance_digest,
        "omega_hash": rec.omega_hash,
        "regime": rec.regime,
        "policy": rec.policy,
        "policy_seed": rec.policy_seed,
        "fallback": rec.fallback.as_json(),
        "actions": list(rec.actions),
        "fallback_actions": [[w, a] for w, a in rec.fallback_actions],
        "wire_failures": [[w, c] for w, c in rec.wire_failures],
        "week_cents": list(rec.week_cents),
        "salvage_cents": rec.salvage_cents,
        "J_cents": rec.J_cents,
        "J_usd": rec.J_usd,
        "trajectory_sha256": rec.trajectory_sha256,
        "provenance": [[k, v] for k, v in rec.provenance],
    }
    return canonical_json(doc)


def _int(x: object, what: str) -> int:
    if isinstance(x, bool) or not isinstance(x, int):
        raise ValueError(f"malformed record: {what} must be an integer, got {x!r}")
    return x


def _str(x: object, what: str) -> str:
    if not isinstance(x, str):
        raise ValueError(f"malformed record: {what} must be a string, got {x!r}")
    return x


def _pairs(x: object, what: str) -> list:
    if not isinstance(x, list) or any(not isinstance(p, list) or len(p) != 2 for p in x):
        raise ValueError(f"malformed record: {what} must be a list of pairs")
    return x


def loads(text: str) -> ConformanceRecord:
    """The record of ``dumps``' text; ``loads(dumps(r)) == r``.

    Raises:
        ValueError: on another schema version or a malformed record: among others a ``J_usd`` that is not the
            ``float.hex`` text of a finite float, fallback weeks that are not distinct increasing weeks of 1..T or
            whose action names another week, and a wire failure outside 1..T. (A fallback week in 1..T that the
            original run did not take is not seen here: the replay never asks for it, so it cannot move a cent.)

    """
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as err:
        raise ValueError(f"malformed record: not JSON ({err})") from err
    if not isinstance(doc, dict):
        raise ValueError("malformed record: not a JSON object")
    if doc.get("schema") != CONFORMANCE_SCHEMA:
        raise ValueError(f"conformance schema {doc.get('schema')!r}, this package reads {CONFORMANCE_SCHEMA}")
    if set(doc) != set(_FIELDS):
        raise ValueError(f"malformed record: fields {sorted(set(doc) ^ set(_FIELDS))} missing or unknown")
    for name in ("instance_hash", "instance_digest", "omega_hash", "trajectory_sha256"):
        if not _is_digest(doc[name]):
            raise ValueError(f"malformed record: {name} must be a SHA-256 hex digest")
    fb = doc["fallback"]
    if not isinstance(fb, dict) or set(fb) != {"kind", "generator_id", "instance_digest", "fq_quantile", "end_aware"}:
        raise ValueError("malformed record: fallback")
    fallback = FallbackRecord(
        kind=_str(fb["kind"], "fallback.kind"),
        generator_id=fb["generator_id"],
        instance_digest=fb["instance_digest"],
        fq_quantile=tuple((tuple(k), q) for k, q in _pairs(fb["fq_quantile"], "fallback.fq_quantile")),
        end_aware=fb["end_aware"],
    )
    if not isinstance(doc["actions"], list) or not isinstance(doc["week_cents"], list):
        raise ValueError("malformed record: actions and week_cents must be lists")
    T = len(doc["week_cents"])
    fallback_actions = []
    for w, a in _pairs(doc["fallback_actions"], "fallback_actions"):
        if not isinstance(a, dict):
            raise ValueError("malformed record: a fallback action must be an object")
        fallback_actions.append((_int(w, "a fallback week"), a))
    fb_weeks = [w for w, _a in fallback_actions]
    if any(not 1 <= w <= T for w in fb_weeks) or fb_weeks != sorted(set(fb_weeks)):
        raise ValueError(f"malformed record: fallback weeks {fb_weeks} are not distinct increasing weeks of 1..{T}")
    if any(type(a.get("week")) is not int or a["week"] != w for w, a in fallback_actions):
        raise ValueError("malformed record: a fallback action's week is not the week it is stored under")
    wire = [(_int(w, "a wire week"), _str(c, "a wire code")) for w, c in _pairs(doc["wire_failures"], "wire_failures")]
    if any(not 1 <= w <= T for w, _c in wire):
        raise ValueError(f"malformed record: a wire failure's week lies outside 1..{T}")
    J_usd = _str(doc["J_usd"], "J_usd")
    try:
        usd = float.fromhex(J_usd)
    except (ValueError, OverflowError) as err:
        raise ValueError(f"malformed record: J_usd must be float.hex text, got {J_usd!r}") from err
    if not math.isfinite(usd) or usd.hex() != J_usd:
        raise ValueError(f"malformed record: J_usd must be the float.hex text of a finite float, got {J_usd!r}")
    weeks = [_int(c, "a weekly cost") for c in doc["week_cents"]]
    salvage, J = _int(doc["salvage_cents"], "salvage_cents"), _int(doc["J_cents"], "J_cents")
    if sum(weeks) - salvage != J or len(doc["actions"]) != len(weeks):
        raise ValueError("malformed record: J^¢ is not sum C^¢_t - S^¢_T (24), or the actions are not one per week")
    return ConformanceRecord(
        schema=CONFORMANCE_SCHEMA,
        instance_hash=doc["instance_hash"],
        instance_digest=doc["instance_digest"],
        omega_hash=doc["omega_hash"],
        regime=_str(doc["regime"], "regime"),
        policy=_str(doc["policy"], "policy"),
        policy_seed=_int(doc["policy_seed"], "policy_seed"),
        fallback=fallback,
        actions=tuple(doc["actions"]),
        fallback_actions=tuple(fallback_actions),
        wire_failures=tuple(wire),
        week_cents=tuple(weeks),
        salvage_cents=salvage,
        J_cents=J,
        J_usd=J_usd,
        trajectory_sha256=doc["trajectory_sha256"],
        provenance=tuple(
            (_str(k, "a provenance key"), _str(v, "a provenance value"))
            for k, v in _pairs(doc["provenance"], "provenance")
        ),
    )


# ----- entries on disk -----------------------------------------------------------------------------------------------
def omega_file(directory: Path, omega_hash: str) -> Path:
    """The omega ``.npz`` of an entry: ``omega-<hash>.npz`` beside the record, shared by the records of one omega."""
    return Path(directory) / f"omega-{omega_hash}.npz"


def save_entry(directory: Path, rec: ConformanceRecord, omega) -> Path:
    """Write ``<name>.json`` and omega's ``.npz`` side by side; return the JSON path.

    The JSON is ``rec.name`` + ``.json``; omega goes to ``omega_file`` (written once per omega: an existing file must
    hold the record's omega), as ``omega.container.save_omega`` stores it but compressed (``np.savez_compressed``, no
    pickles; ``load_omega`` reads both), since a generated `tiny` omega is 0.5-0.9 MB uncompressed and the committed
    conformance set holds four.

    Raises:
        ValueError: if omega's hash is not the record's, or an existing omega file holds another omega.

    """
    if omega.hash != rec.omega_hash:
        raise ValueError("omega's hash is not the record's")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    npz = omega_file(directory, rec.omega_hash)
    if npz.exists():
        if load_omega(npz).hash != rec.omega_hash:
            raise ValueError(f"{npz.name} holds another omega")
    else:
        np.savez_compressed(npz, **{k: np.asarray(v) for k, v in omega.arrays.items()})
    path = directory / f"{rec.name}.json"
    path.write_text(dumps(rec) + "\n", encoding="utf-8")
    return path


def load_entry(path: Path) -> tuple[ConformanceRecord, object]:
    """The record and its omega from ``save_entry``'s files, the omega hash checked.

    Raises:
        ValueError: on a malformed record, or an omega file whose hash is not the record's.

    """
    path = Path(path)
    rec = loads(path.read_text(encoding="utf-8"))
    omega = load_omega(omega_file(path.parent, rec.omega_hash))
    if omega.hash != rec.omega_hash:
        raise ValueError(f"the omega beside {path.name} is not the record's (hash)")
    return rec, omega


# ----- replay and comparison -----------------------------------------------------------------------------------------
class _StoredFallback:
    """The replay's D9 fallback: the stored action of a recorded D9 week, an error on any other (logged, then raised).

    ``Env`` catches a fallback's exception and plays the empty action, so ``replay_record`` reads ``unexpected``
    after the episode and raises there: a week that takes the fallback in the replay but not in the record is an
    error, never a silent empty action.
    """

    def __init__(self, table: tuple[tuple[int, dict], ...]) -> None:
        self.table = {int(w): a for w, a in table}
        self.unexpected: list[int] = []

    def __call__(self, obs: dict) -> dict:
        week = int(obs["week"])
        if week not in self.table:
            self.unexpected.append(week)
            raise LookupError(f"V24 replay: week {week} took the D9 fallback, which the record did not")
        return copy.deepcopy(self.table[week])


def replay_record(inst: Instance, rec: ConformanceRecord, omega) -> Trajectory:
    """Re-simulate a record: ``information.runner.replay`` from its stored actions, the fallback from the record.

    The ``Env``'s fallback is a callable that plays ``rec.fallback_actions`` (the stored action on a recorded D9
    week, an error on any other). No LP is solved (not naive's plan (22): no naive spec is installed) and no F_Q is
    recomputed. ``omega`` is an ``Omega`` or its ``.npz`` path. The marks are omega's own (``compute_marks`` under its
    ``meta_mark_params``, as every episode's), so the stored trajectory carries their digest and the record's instance
    digest for ``runner.replay``'s V3 guard; the record's ``trajectory_sha256`` (which covers the marks digest) is
    compared by ``compare``.

    Raises:
        ValueError: unless the instance's hash and content digest and omega's hash are the record's; on a regime that
            is no registry name; or when the replay took the D9 fallback in a week the record did not (tampered
            actions).

    """
    om = omega if isinstance(omega, Omega) else load_omega(omega)
    inst = inst.at_digest(rec.instance_digest)  # the record's rung: its block of the warm start per rung (§2.3)
    if inst.hash != rec.instance_hash or inst.content_digest != rec.instance_digest:
        raise ValueError("the instance is not the record's (hash or content digest, V3)")
    if om.hash != rec.omega_hash:
        raise ValueError("omega is not the record's (hash)")
    if rec.regime not in REGIME_NAMES:
        raise ValueError(f"V24 records registry regimes only ({REGIME_NAMES}), got {rec.regime!r}")
    marks = compute_marks(inst, om)
    stored = Trajectory(
        instance_hash=rec.instance_hash,
        omega_hash=rec.omega_hash,
        instance_digest=rec.instance_digest,
        marks_digest=marks.digest,
        policy=rec.policy,
        regime=rec.regime,
        actions=list(copy.deepcopy(rec.actions)),
        wire_failures=list(rec.wire_failures),
    )
    fallback = _StoredFallback(rec.fallback_actions)
    traj = runner.replay(
        Env(fallback=fallback), inst, stored, regime=rec.regime, omega=om, policy_seed=rec.policy_seed, marks=marks
    )
    if fallback.unexpected:
        raise ValueError(f"V24 replay took the D9 fallback in weeks {fallback.unexpected} the record did not")
    return traj


def compare(rec: ConformanceRecord, traj: Trajectory) -> ConformanceResult:
    """The cent differences (replay minus record) week by week, on S^¢_T and on J^¢, and SHA equality.

    Raises:
        ValueError: if the trajectory's week count is not the record's, or it is unfinished.

    """
    if len(traj.records) != len(rec.week_cents):
        raise ValueError(f"the replay has {len(traj.records)} weeks, the record {len(rec.week_cents)}")
    if traj.salvage_cents is None:
        raise ValueError("the replay is unfinished (no terminal credit)")
    return ConformanceResult(
        week_diffs=tuple(int(r.cost_cents) - c for r, c in zip(traj.records, rec.week_cents, strict=True)),
        salvage_diff=int(traj.salvage_cents) - rec.salvage_cents,
        J_diff=int(traj.J_cents) - rec.J_cents,
        sha_equal=traj.sha256() == rec.trajectory_sha256,
    )


def platform_label() -> str:
    """``<system> <machine>`` of this process, e.g. "Darwin arm64" or "Linux x86_64" (for reports)."""
    return f"{platform.system()} {platform.machine()} (Python {sys.version.split()[0]})"
