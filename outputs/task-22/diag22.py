"""Task 22: weekly wafer stock / lots / energy per fab for a few players (gap22.play), to tell wafer- from power-limited
fab weeks. uv run python outputs/task-22/diag22.py 2,5,0,1,53,26 4 agents/mpc_fab3sell "policy:mpc_det@max(26,2L)"
"""
import json, sys
from pathlib import Path
from joblib import Parallel, delayed
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gap22 import play  # noqa: E402

from shockbench_flow_agent.scoring import EpisodeSet

ns = [int(x) for x in sys.argv[1].split(",")]
es = EpisodeSet.build("full", ns, entropy=0, n_jobs=int(sys.argv[2]))
jobs = [delayed(play)(n, es._spec, p) for p in sys.argv[3:] for n in ns]
rows = Parallel(n_jobs=int(sys.argv[2]))(jobs)
for r in rows:
    r["detail"] = {k: r["detail"][k] for k in ("wafer_stock_w", "energy_w", "lots_w", "shed_w")}
Path("outputs/task-22/diag22.json").write_text(json.dumps(rows))
print("ok")
