import copy, importlib.util, sys
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
