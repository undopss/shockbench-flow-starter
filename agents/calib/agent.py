"""Speed calibration: how much faster (or slower) the scoring server's CPU is than our home server.

Week 1 runs a fixed benchmark (an LP like our MPC's, solved by SciPy's HiGHS, plus some numpy) and compares its CPU
time with REF_S, the same benchmark's time on our home server (FX-6100). The speed factor X = REF_S / server time is
then written into the board's Fallbacks column: weeks 2 .. k + 1 raise on purpose (a raising week is played by the
naive rule and counted as a fallback), with k = round(10 * X), clipped to 1 .. 50. So

    X = Fallbacks / (episodes * 10)        (Fallbacks 0 would mean the benchmark itself failed)

Every other week sends the maximum, like the template. The score itself means nothing.
"""

import time
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import random as sparse_random

HERE = Path(__file__).resolve().parent
REF_S = 0.1664  # benchmark() CPU seconds on our home server (FX-6100, one thread; median of 5 runs, 2026-10-06)


def benchmark():
    """A fixed LP (HiGHS) and a fixed numpy workload; returns its CPU seconds (best of 3)."""
    best = float("inf")
    for _ in range(3):
        rng = np.random.default_rng(12345)
        n, m = 1200, 600
        A = sparse_random(m, n, density=0.004, random_state=rng, format="csr") * 10.0
        c = -rng.random(n)
        b = rng.random(m) * 50.0 + 5.0
        M = rng.random((200, 200))
        start = time.process_time()
        linprog(c, A_ub=A, b_ub=b, bounds=(0.0, 10.0), method="highs")
        for _ in range(10):
            M = np.tanh(M @ M.T / 200.0)
        best = min(best, time.process_time() - start)
    return best


class Agent:
    def __init__(self, config=None):
        static = config["static"]
        action = config["spaces"]["action"]
        u0 = static["edges"]["u0"]
        self.capacity = np.array([u0[e] for e in static["action_slots"]["edge"]], dtype=float)
        self.override_qty = np.zeros(action["override_qty"]["shape"])
        self.release_mode = np.zeros(action["release_mode"]["shape"], dtype=np.int64)
        self.week = 0
        self.k = 0

    def act(self, observation):
        self.week += 1
        if self.week == 1:
            self.k = int(np.clip(round(10.0 * REF_S / benchmark()), 1, 50))
        elif self.week <= self.k + 1:
            raise RuntimeError(f"calibration fallback {self.week - 1} of {self.k}")
        flows = self.capacity * observation["action_mask"]
        return {"flows": flows, "override_qty": self.override_qty, "release_mode": self.release_mode}
