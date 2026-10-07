"""The public tasks: the instances and the generator a participant trains and evaluates on (§9.5; Q102, Q108).

A task names a packaged instance, its generator profile (a function of ``disruption.profiles``, looked up by name as
``policies.registry.PROFILES`` names it for the instance's kind, which a test holds equal) and the policy-block rung the
competition plays (the anchor, §2.6); its instance is the file's at that rung (``Instance.at_rung``: the rung's warm
start on `small` and `full`, §2.3, M5-O37 (b); `tiny` has one start for every rung). Its scenarios are the public
generator's: episode n of root E is ``sampler.sample_omega(inst, params, E, n, label)``, the
label ``dev`` for the dev split's public root ``split.DEV_ENTROPY`` (so the dev episodes are the local evaluation's,
omega for omega) and ``train`` for any other root (a participant's own training root, as the starter guide's). The
hidden split draws from the same generator under the secret E_split, which nothing here reads.

``shockbench_flow_gym`` registers one environment per task (``gym.make("ShockBench/Tiny-v0")``, ``Task.env_id``) and
``shockbench_flow_agent.evaluate`` scores on a task's dev episodes. The dev split's size, the cut points' draws and the
fill's candidate budget are the trusted runner's (``configs/score_submission.yaml``; a test holds them equal).

`small` and `full` joined at the M5 merge, one line each in ``TASKS`` (their profile ``flagship_profile``, §4.2, Q110
M5-O12 (a)), which registers ``ShockBench/Small-v0`` and ``ShockBench/Full-v0`` too. Q113 plays `small` in Codabench's
Development phase and `full` in its Final.
"""

import functools
import importlib
from collections.abc import Callable
from dataclasses import dataclass

from sbfv.disruption.params import RUNGS, GeneratorParams
from sbfv.disruption.sampler import sample_omega
from sbfv.hosting.split import DEV_ENTROPY
from sbfv.instance import load_instance
from sbfv.instance.schema import Instance
from sbfv.omega.container import Omega


ANCHOR = RUNGS[0]  # the anchor rung gamma = 0.62 (§2.6, Q39): configs/disruption/generated_tiny.yaml
DEV_SPLIT, TRAIN_SPLIT = "dev", "train"  # the omega labels of the public dev root and of any other root
# the trusted runner's dev split and strata (configs/score_submission.yaml): N_s per stratum on dev (the owner,
# 2026-09-28, Q108), the cut points' M (SYNTHETIC(placeholder), M4's run_eval), the fill's candidate budget
DEV_PER_STRATUM = (5, 5, 5, 5)
CUT_DRAWS = 2000
MAX_CANDIDATES = 10_000


@dataclass(frozen=True)
class Task:
    """One public task: a packaged instance, its generator profile's function name, and the rung played."""

    name: str
    instance: str
    profile: str  # a function (inst, gamma) -> GeneratorParams of ``sbfv.disruption.profiles``
    gamma: float = ANCHOR

    @property
    def env_id(self) -> str:
        """The gymnasium id, ``ShockBench/<Name>-v0``."""
        return f"ShockBench/{self.name.capitalize()}-v0"


TASKS: dict[str, Task] = {
    "tiny": Task("tiny", "tiny", "tiny_profile"),  # design §2.4
    "small": Task("small", "small", "flagship_profile"),  # design §2.2, §4.2 (M5)
    "full": Task("full", "full", "flagship_profile"),  # design §2.2, §4.2 (M5)
}


def get_task(name: str) -> Task:
    """The task named ``name``.

    Raises:
        ValueError: if no task has that name.

    """
    if name not in TASKS:
        raise ValueError(f"task must be one of {tuple(TASKS)}, got {name!r}")
    return TASKS[name]


@functools.cache
def task_generator(name: str, gamma: float | None = None) -> tuple[Instance, GeneratorParams]:
    """(instance, generator parameters) of a task at its rung, or at ``gamma`` (a rung of §2.6); once per process.

    The instance is the file's at the generator's rung (``Instance.at_rung``, the rung's warm start; module docstring),
    as the runner's and the trusted runner's.

    Raises:
        ValueError: on an unknown task, or as the profile (a gamma that is not a rung, an instance of another kind).

    """
    task = get_task(name)
    inst = load_instance(task.instance)
    params = profile_function(task)(inst, task.gamma if gamma is None else gamma)
    return inst.at_rung(params.hawkes.gamma), params


def profile_function(task: Task) -> Callable[[Instance, float], GeneratorParams]:
    """The generator profile of a task: its function of ``sbfv.disruption.profiles`` (``Task.profile``)."""
    return getattr(importlib.import_module("sbfv.disruption.profiles"), task.profile)


def generator_profiles() -> dict[str, Callable[[Instance, float], GeneratorParams]]:
    """Each task instance's generator profile, keyed by the instance's name, which is its ``Instance.kind``.

    The one table of profiles: ``shockbench_flow_gym.wrappers.PROFILES`` (the scenario pool's generator) and the
    dashboard (the generator whose F_Q naive plays) read it, so a task added to ``TASKS`` reaches both.
    """
    return {task.instance: profile_function(task) for task in TASKS.values()}


def split_label(entropy: int) -> str:
    """The omega label of a root: ``dev`` for the public dev root, ``train`` for any other (module docstring)."""
    return DEV_SPLIT if entropy == DEV_ENTROPY else TRAIN_SPLIT


def scenario(task: str, episode: int, *, entropy: int = DEV_ENTROPY, gamma: float | None = None) -> Omega:
    """Omega of episode n of a task's public generator under root ``entropy`` (the dev root by default).

    With the dev root it is dev episode n of the local evaluation (``eval_submission.py``, ``evaluate``), bit for bit.
    """
    inst, params = task_generator(task, gamma)
    return sample_omega(inst, params, entropy, episode, split_label(entropy))
