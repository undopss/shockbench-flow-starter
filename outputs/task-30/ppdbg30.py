"""Task 30: why does the pulse planner not pulse crude at JP? Plays one Full episode and logs the planner's inputs for
one grid (V, ehat, base, per-fuel terminal / grid stock / arrivals) and its release."""
import sys
from pathlib import Path
import numpy as np


def main(n=5, grid="grid_jp", agent="agents/mpc_imit_room", w0=30, w1=50):
    n, w0, w1 = int(n), int(w0), int(w1)
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _label, _metered_shim, _policy_seed
    from shockbench_flow.disruption.sampler import sample_omega
    from shockbench_flow.hosting.tasks import task_generator
    from shockbench_flow.marks import compute_marks
    from shockbench_flow_agent.shim import load_agent_class
    inst, gparams = task_generator("full")
    omega = sample_omega(inst, gparams, 0, n, _label(0))
    marks = compute_marks(inst, omega)
    cls = load_agent_class(str(Path(agent).resolve()), "dbg_agent")
    mod = sys.modules[cls.__module__]
    PP = mod._pplan.PulsePlanner
    ids = [nd.id for nd in inst.nodes]
    log = {}
    orig_pg, orig_enum = PP._plan_grid, PP._enum

    def pg(self, obs, gr, arr, fab_plan=None):
        w = int(obs["week"][0])
        res = orig_pg(self, obs, gr, arr, fab_plan)
        if ids[gr["node"]] == grid and w0 <= w <= w1:
            print(f"wk {w} plan_grid -> {None if res is None else {k: round(v) for k, v in res.items()}}", flush=True)
        return res

    def en(self, gr, ctrl, base, ehat, ybar, V, obs):
        w = int(obs["week"][0])
        res = orig_enum(self, gr, ctrl, base, ehat, ybar, V, obs)
        if ids[gr["node"]] == grid and w0 <= w <= w1:
            print(f"wk {w} V {np.round(V[:4], 1)} ehat {np.round(ehat[:4])} base0 {base[0]:.0f} ybar {ybar:.0f}", flush=True)
            a0 = self.arrivals(obs, None)
            q = obs["queue_lots.qty"]
            kap = obs["graph_now.kappa.tb"]
            for row, (chk_node, k, lane_key, next_edge) in enumerate(self.lot_keys):
                if q[row].sum() > 0 and int(k) in self.tb_k:
                    pos = self.chk_pos.get(chk_node)
                    print(f"     queue {ids[chk_node]} k{k} lane {lane_key} next {next_edge} u_next {float(obs['graph_now.u'][next_edge]):.0f} "
                          f"qty {q[row].sum():.0f} cohorts {np.round(q[row][q[row] > 0])} kappa {float(kap[pos]):.0f}", flush=True)
            for fu in ctrl:
                print(f"     no-plan aT k{fu['k']} {np.round(a0.get((fu['term'], fu['k']), np.zeros(4))[:4])}", flush=True)
            for fu in ctrl:
                print(f"     k {fu['k']} cap {fu['cap']:.0f} thr {fu['thr']:.0f} I0 {fu['I0']:.0f} T0 {fu['T0']:.0f} "
                      f"aG {np.round(fu['aG'][:4])} aT {np.round(fu['aT'][:4])} u {float(obs['graph_now.u'][fu['edge']]):.0f}"
                      f" -> rel {res.get(fu['slot'], -1):.0f}", flush=True)
        return res
    PP._plan_grid, PP._enum = pg, en
    shim = _metered_shim(cls, None)
    rollout(inst, shim, omega, "standard", _policy_seed(0, n, NO_ZIP_SHA256), marks=marks, fallback=None)


if __name__ == "__main__":
    main(*sys.argv[1:])
