"""Precompute what agents/scen would otherwise draw in week 1: naive's F_Q quantiles and mpc_scen's scenario library.

Both depend only on the task (instance and public generator), never on the episode, so they ship as data files:
agents/scen/data/<task>.pkl. Run with the full package installed (it needs the sampler):

    uv run python outputs/scen_precompute.py
"""

import pickle
import sys
import time
from pathlib import Path

import numpy as np
from shockbench_flow.evaluation.cache import default_cache_dir, fq_quantiles
from shockbench_flow.hosting.tasks import get_task, task_generator
from shockbench_flow.policies import scenarios as S_
from shockbench_flow.policies.mpc_scen import budget_S
from shockbench_flow.policies.naive_fq import REPLICATIONS, RUNGS, generator_quantiles
from shockbench_flow.policies.registry import GeneratorRef

OUT = Path(__file__).resolve().parents[1] / "agents" / "scen" / "data"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for task in sys.argv[1:] or ("small", "full"):
        t0 = time.time()
        inst, params = task_generator(task)
        fq_quantiles(inst, params, REPLICATIONS, cache_dir=default_cache_dir())  # the disk cache, as sbf evaluate's
        quantiles = dict(generator_quantiles(inst, params, REPLICATIONS))
        ref = GeneratorRef(task, get_task(task).gamma)
        gen = S_.generator_params(inst, ref)
        S = budget_S(inst.kind)
        library = S_.scenario_library(inst, gen, S_.TAG_MPC_SCEN, S)
        draws = [
            {
                "index": d.index,
                "entropy_sha256": d.entropy_sha256,
                "generator_id": d.generator_id,
                "events": {k: np.array(v) for k, v in d.events.items()},
            }
            for d in library
        ]
        rungs = {float(g): task_generator(task, g)[0].content_digest for g in RUNGS}
        data = {
            "kind": inst.kind,
            "rung_digests": rungs,  # instance content digest per rung, to tell which instance the scorer sends
            "gamma": float(ref.gamma),
            "replications": REPLICATIONS,
            "S": S,
            "content_digest": inst.content_digest,
            "quantiles": quantiles,
            "draws": draws,
        }
        path = OUT / f"{task}.pkl"
        path.write_bytes(pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL))
        print(f"{task}: S={S}, {len(quantiles)} quantiles, {path.stat().st_size / 1e6:.2f} MB, {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
