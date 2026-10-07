"""A competition split's scenarios: its entropy, and its episodes filled into the harm strata of (44) (§9.5; Q102).

- **Entropy** (``split_entropy``): the dev split draws from a public root, ``DEV_ENTROPY``; the hidden split from the
  secret E_split in the environment variable ``SBF_ENTROPY`` (a decimal integer below 2**128, never in a config, a
  command or an output). The hidden root must differ from the public ones (the dev root and the cut points'
  ``CUT_ENTROPY``), or the hidden scenarios would be public, and must be at least 2**119 (``HIDDEN_MIN_BITS``,
  ``check_root``; M4 re-gate INT-M4R2-02): E_split is 128 bits of entropy (§4.1, ``secrets.randbits(128)``, which
  ``new_hidden_root`` draws), and its one-way uses (the policy seed (27) an agent receives, the commitment a document
  carries) hide it only while it is: a small root comes back from one policy seed by enumeration. A randbits(128)
  draw falls below the bound with probability 2**-9 (``new_hidden_root`` draws again); every guessable root (a date, a
  counter, 424242) does. The dev split never reads the secret. Omega is a function of the root, n and the generator,
  not of the split's label, so a hidden root under the dev label draws the hidden scenarios: a run whose agent is not
  isolated takes a root below the hidden minimum only (``check_public_root``), which no hidden root is.
- **Commitment** (``entropy_commitment``): what an output may carry about a root, in place of the root: SHA-256 over
  ``COMMITMENT_TAG``, the split's name and the root as 16 big-endian bytes (design §12 "Hidden root: minimum and
  commitment"). Domain-separated, so no table of hashes of small integers inverts it; with the minimum above no search
  does either; and a root revealed after the competition can be checked against it.
- **Strata** (``fill_strata``): candidates n = 0, 1, ... are drawn from the split's root, each harm taken from the
  full omega (``harm.episode_harm`` of ``sampler.sample_omega``), its stratum by ``strata.stratum`` on the rung's cut
  points, and the first N_s of each stratum kept in index order; a stratum still unfilled after ``max_candidates`` is
  reported, never padded. This is the rule of M4's ``evaluation.runner.fill_strata`` (design §12 "Episode spec and
  keys (M4 runner)"), re-implemented here so the competition layer does not depend on M4's code; the keys depend
  neither on the batch nor on the worker count. The fill reads omega only, so it is policy-independent.
- **A fill computed elsewhere** (``check_fill``): the trusted runner may take the scenarios from the scripts layer's
  disk cache (``sbf_boundary.strata_fill_cached``, keyed by everything the fill depends on, ``FILL_VERSION`` among
  it) instead of drawing them again; ``check_fill`` refuses a fill whose shape does not answer the request, and each
  played episode re-derives its harm from its own omega (``hosting.trusted``).
"""

import functools
import hashlib
import os
import secrets
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from sbfv.disruption.harm import episode_harm
from sbfv.disruption.params import GeneratorParams, generator_id
from sbfv.disruption.sampler import sample_omega
from sbfv.disruption.strata import CutPoints, stratum
from sbfv.instance.schema import Instance
from sbfv.omega.seeds import check_entropy
from sbfv.parallel import ordered_map


SPLITS = ("dev", "hidden")
ENTROPY_VAR = "SBF_ENTROPY"
DEV_ENTROPY = 0  # SYNTHETIC(placeholder): the public dev root, the default of every local run (sbf_boundary.entropy)
CUT_ENTROPY = 20260927  # SYNTHETIC(placeholder): the cut points' own public root, M4's (configs/run_eval.yaml)
HIDDEN_MIN_BITS = 120  # a hidden root is at least 2**119 (module docstring, 'Entropy'); not a model value
COMMITMENT_TAG = b"shockbench-flow/entropy-commitment/1"  # the commitment's domain tag (module docstring)
BATCH = 64  # candidates per ordered_map call at most while filling (no result depends on it)
FILL_VERSION = 1  # the fill rule's version: bump when fill_strata's selection changes (a key of the fill cache)


@dataclass(frozen=True)
class Scenario:
    """One scenario of a split: its episode index n (omega_n of the split's root), stratum s(omega_n) and harm H."""

    episode: int
    stratum: int
    harm: float


def split_entropy(
    split: str, *, dev_entropy: int = DEV_ENTROPY, cut_entropy: int = CUT_ENTROPY, environ: Mapping | None = None
) -> int:
    """E_split of a split (module docstring, 'Entropy'); ``environ`` defaults to ``os.environ``.

    Raises:
        ValueError: on a split outside ``SPLITS``; for the hidden split, ``SBF_ENTROPY`` unset or empty, not a decimal
            integer, outside [0, 2**128), equal to a public root, or below the minimum (``check_root``).

    """
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}, got {split!r}")
    if split == "dev":
        return check_entropy(dev_entropy)
    raw = (os.environ if environ is None else environ).get(ENTROPY_VAR) or ""
    if not raw:
        raise ValueError(f"{ENTROPY_VAR} is unset: the hidden split draws from the secret E_split in the environment")
    if not raw.isdecimal():
        raise ValueError(f"{ENTROPY_VAR} must be a decimal integer")
    value = int(raw)
    if value >= 2**128:
        raise ValueError(f"{ENTROPY_VAR} must be below 2**128 (27)")
    if value in (dev_entropy, cut_entropy):
        raise ValueError(
            f"{ENTROPY_VAR} equals a public root (dev or cut points): the hidden scenarios would be public"
        )
    return check_root(split, value)


def check_root(split: str, entropy: int) -> int:
    """``entropy`` as a split's root (27), a hidden root held to the minimum (module docstring, 'Entropy').

    Raises:
        ValueError: if the entropy is not in [0, 2**128), or the split is hidden and the root below
            2**(``HIDDEN_MIN_BITS`` - 1).
        TypeError: if it is not an integer (a bool included).

    """
    value = check_entropy(entropy)
    if split == "hidden" and value.bit_length() < HIDDEN_MIN_BITS:
        raise ValueError(
            f"the hidden root has {value.bit_length()} bits, below the minimum of {HIDDEN_MIN_BITS} (at least "
            f"2**{HIDDEN_MIN_BITS - 1}): a small root is recovered from one policy seed (27); draw one with "
            "sbfv.hosting.split.new_hidden_root() (design §4.1: 128 bits of entropy)"
        )
    return value


def check_public_root(entropy: int) -> int:
    """``entropy`` as the root of a run whose agent is not isolated: below the hidden minimum (module docstring).

    The local evaluation (``shockbench_flow_agent.local_eval``) and ``score_submission.py``'s subprocess transport call
    it, so no hidden root, E_split among them, plays unisolated under the dev label (design §12 "Local runs and the
    scorer's secrets").

    Raises:
        ValueError: on a root of at least 2**(``HIDDEN_MIN_BITS`` - 1), the hidden split's size; ValueError and
            TypeError as ``omega.seeds.check_entropy``.

    """
    value = check_entropy(entropy)
    if value.bit_length() >= HIDDEN_MIN_BITS:
        raise ValueError(
            f"a root of {value.bit_length()} bits is of the hidden split's size (at least 2**{HIDDEN_MIN_BITS - 1}): "
            "omega does not depend on the split's label, so this run would play hidden scenarios outside the policy "
            f"container; a local run takes a public root below 2**{HIDDEN_MIN_BITS - 1} (the dev root is {DEV_ENTROPY})"
        )
    return value


def new_hidden_root() -> int:
    """A fresh hidden root: ``secrets.randbits(128)`` (§4.1), drawn again below the minimum (probability 2**-9)."""
    while (root := secrets.randbits(128)).bit_length() < HIDDEN_MIN_BITS:
        pass
    return root


def entropy_commitment(split: str, entropy: int) -> str:
    """The hex SHA-256 of ``COMMITMENT_TAG`` || 0x00 || split || 0x00 || the root as 16 big-endian bytes.

    What a scores document and a recorded command carry about a root (module docstring, 'Commitment').

    Raises:
        ValueError, TypeError: as ``omega.seeds.check_entropy``, or on a split outside ``SPLITS``.

    """
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}, got {split!r}")
    root = check_entropy(entropy).to_bytes(16, "big")
    return hashlib.sha256(COMMITMENT_TAG + b"\x00" + split.encode("ascii") + b"\x00" + root).hexdigest()


def omega_harm(inst: Instance, params: GeneratorParams, entropy: int, split: str, episode: int) -> float:
    """H(omega_n) of (42): ``harm.episode_harm`` of the full omega, under the generator's mark parameters."""
    return episode_harm(inst, sample_omega(inst, params, entropy, episode, split), params.marks)


def _harm(harm_of: Callable, inst: Instance, params: GeneratorParams, entropy: int, split: str, n: int) -> float:
    return float(harm_of(inst, params, entropy, split, n))


def fill_strata(
    inst: Instance,
    params: GeneratorParams,
    entropy: int,
    split: str,
    cuts: CutPoints,
    n_per_stratum: Sequence[int],
    *,
    max_candidates: int,
    n_jobs: int = 1,
    harm_of: Callable | None = None,
) -> tuple[tuple[Scenario, ...], int, tuple[int, ...]]:
    """The split's scenarios (module docstring, 'Strata'): (scenarios by index, candidates drawn, unfilled strata).

    ``harm_of(inst, params, entropy, split, n)`` replaces ``omega_harm`` (tests); it must pickle when ``n_jobs`` != 1.

    Raises:
        ValueError: if the cut points are not of this generator (h_j per size and rung, (44)), ``n_per_stratum`` does
            not give one N_s >= 0 per stratum, or ``max_candidates`` < 1.

    """
    gid = generator_id(params, inst)
    if cuts.generator_id != gid:
        raise ValueError(f"cut points of generator {cuts.generator_id[:12]}... cannot stratify {gid[:12]}... (44)")
    need = [int(x) for x in n_per_stratum]
    if len(need) != len(cuts.values) + 1 or any(x < 0 for x in need):
        raise ValueError(f"n_per_stratum must give one N_s >= 0 per stratum ({len(cuts.values) + 1}), got {need}")
    if max_candidates < 1:
        raise ValueError(f"max_candidates must be >= 1, got {max_candidates}")
    fn = functools.partial(_harm, harm_of or omega_harm, inst, params, entropy, split)
    kept: list[Scenario] = []
    have = [0] * len(need)
    n = 0
    while n < max_candidates and any(h < k for h, k in zip(have, need)):
        missing = sum(k - h for h, k in zip(have, need) if h < k)
        size = min(BATCH, max(2 * missing, 1 if n_jobs == 1 else 4), max_candidates - n)
        batch = list(range(n, n + size))
        for episode, harm in zip(batch, ordered_map(fn, batch, n_jobs)):
            s = stratum(harm, cuts, generator_id=gid)
            if have[s - 1] < need[s - 1]:
                have[s - 1] += 1
                kept.append(Scenario(episode, s, harm))
        n += size
    unfilled = tuple(i + 1 for i, (h, k) in enumerate(zip(have, need)) if h < k)
    drawn = n if unfilled else (max(s.episode for s in kept) + 1 if kept else 0)
    return tuple(kept), drawn, unfilled


def check_fill(fill: tuple, n_per_stratum: Sequence[int]) -> tuple[tuple[Scenario, ...], int, tuple[int, ...]]:
    """``fill`` (scenarios, candidates drawn, unfilled strata) as ``fill_strata`` returns it, checked against N_s.

    The checks ``fill_strata``'s rule implies: episodes distinct and in index order, below the candidates drawn; each
    stratum in 1..len(``n_per_stratum``) holding exactly N_s scenarios, or fewer and then listed as unfilled; the
    unfilled strata exactly those. Harms are not recomputed here (the played episodes re-derive theirs).

    Raises:
        ValueError: on any of them.

    """
    scenarios, drawn, unfilled = fill
    scenarios, unfilled, need = tuple(scenarios), tuple(int(s) for s in unfilled), [int(x) for x in n_per_stratum]
    if not all(isinstance(s, Scenario) for s in scenarios):
        raise ValueError("a fill's scenarios must be split.Scenario records")
    episodes = [s.episode for s in scenarios]
    if episodes != sorted(set(episodes)) or any(n < 0 for n in episodes) or (episodes and episodes[-1] >= drawn):
        raise ValueError("a fill's episodes must be distinct, >= 0, in index order and below the candidates drawn")
    have = [0] * len(need)
    for s in scenarios:
        if not 1 <= s.stratum <= len(need):
            raise ValueError(f"stratum {s.stratum} outside 1..{len(need)}")
        have[s.stratum - 1] += 1
    short = tuple(i + 1 for i, (h, k) in enumerate(zip(have, need)) if h < k)
    if any(h > k for h, k in zip(have, need)) or short != unfilled:
        raise ValueError(f"a fill of {have} per stratum (unfilled {list(unfilled)}) does not answer N_s = {need}")
    return scenarios, int(drawn), unfilled
