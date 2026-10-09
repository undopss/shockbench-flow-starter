"""Task 33 guard: grid names in params that are missing from the map must be skipped silently.

    uv run python outputs/task-33/guard_test.py [episode]

Plays one Full dev episode with agents/mpc_final in four set-ups and prints the cost of each:
  A  params.json as shipped
  B  the same + bogus grid names in pulse_grids and pp_direct (must equal A)
  C  config with grid_cn renamed to grid_cn_renamed (pp_direct's grid_cn is then missing from the map)
  D  params with pp_direct = ["grid_eu"] only (what C should reduce to: must equal C)
"""
import json, shutil, sys
from pathlib import Path
from shockbench_flow_agent.scoring import EpisodeSet

ep = int(sys.argv[1]) if len(sys.argv) > 1 else 0
root = Path("outputs/task-33/guard")
shutil.rmtree(root, ignore_errors=True)
src = Path("agents/mpc_final")
base = json.loads((src / "params.json").read_text())
WRAP = '''import copy, importlib.util, sys
from pathlib import Path
_spec = importlib.util.spec_from_file_location("inner_agent", Path(__file__).parent / "inner" / "agent.py")
_m = importlib.util.module_from_spec(_spec); sys.modules["inner_agent"] = _m; _spec.loader.exec_module(_m)
class Agent(_m.Agent):
    def __init__(self, config):
        def ren(x):  # every "grid_cn" string in the config (node id and every reference to it)
            if isinstance(x, str):
                return "grid_cn_renamed" if x == "grid_cn" else x
            if isinstance(x, dict):
                return {ren(k): ren(v) for k, v in x.items()}
            if isinstance(x, list):
                return [ren(v) for v in x]
            if isinstance(x, tuple):
                return tuple(ren(v) for v in x)
            return x
        config = ren(config)
        super().__init__(config)
        print("C components:", self.ok, self.pplan is not None, self.chips is not None, file=sys.stderr)
'''
def make(name, params, wrap=False):
    f = root / name
    if wrap:
        shutil.copytree(src, f / "inner", ignore=shutil.ignore_patterns("__pycache__"))
        (f / "inner" / "params.json").write_text(json.dumps(params))
        (f / "agent.py").write_text(WRAP)
    else:
        shutil.copytree(src, f, ignore=shutil.ignore_patterns("__pycache__"))
        (f / "params.json").write_text(json.dumps(params))
    return str(f.resolve())

bogus = dict(base, pulse_grids=list(base.get("pulse_grids", ["grid_tw", "grid_kr"])) + ["grid_nope"],
             pp_direct=list(base.get("pp_direct", [])) + ["grid_nope"])
setups = {"A": make("A", base), "B": make("B", bogus), "C": make("C", base, wrap=True),
          "D": make("D", dict(base, pp_direct=[g for g in base.get("pp_direct", []) if g != "grid_cn"]))}
es = EpisodeSet.build("full", [ep], entropy=0, n_jobs=1)
for k, f in setups.items():
    rows = es.play(f, n_jobs=1)
    print(k, "J", rows[0]["J_policy_cents"], "fallback_weeks", rows[0]["fallback_weeks"], flush=True)
