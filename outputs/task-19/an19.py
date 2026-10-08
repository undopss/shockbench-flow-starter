"""Task 19: chips made but not sold, from diag19 JSON (+ the oracle's lots per fab from task 17's JSON)."""
import json, sys
from pathlib import Path
import numpy as np

rows = json.loads(Path(sys.argv[1]).read_text())
o17 = {r["episode"]: r for r in json.loads(Path("outputs/task-17/gap17v2_full_0_dev_mpc_buffer.json").read_text())}
n = len(rows)
slots = rows[0]["slots"]
fabs = rows[0]["fabs"]
dem = rows[0]["demands"]
pi = {"chip_le": 50480.0, "chip_mat": 10360.0, "chip_le_raw": 50480.0, "chip_mat_raw": 10360.0}
print(f"{n} episodes:", [r["episode"] for r in rows])
disp = np.mean([np.sum(r["disp_w"], axis=0) for r in rows], axis=0)
disp_late = np.mean([np.sum(np.array(r["disp_w"])[-10:], axis=0) for r in rows], axis=0)
end = np.mean([r["stock_w"][-1] for r in rows], axis=0)
print("\n## chip disposal and end stock per slot (M units / episode, mean)")
tot = {}
for i in np.argsort(-disp):
    if "wafer" in slots[i][1]:
        continue
    k = slots[i][1]
    tot.setdefault(k, [0, 0])
    tot[k][0] += disp[i]; tot[k][1] += end[i]
    if disp[i] > 2e4 or end[i] > 1e5:
        print(f"  {slots[i][0]:>18s} {k:<13s} disposed {disp[i]/1e6:6.2f} (last 10 wk {disp_late[i]/1e6:5.2f})  end {end[i]/1e6:6.2f}")
for k, (d, e) in tot.items():
    print(f"  TOTAL {k:<13s} disposed {d/1e6:6.2f}  end stock {e/1e6:6.2f}   value at pi {d*pi[k]/1e12:.3f} T + end {e*pi[k]/1e12:.3f} T")
wd = [i for i in range(len(slots)) if "wafer" in slots[i][1]]
print(f"  wafers disposed {sum(disp[i] for i in wd)/1e6:.2f}M")
print("\n## lots started per fab (M / episode): agent, agent in last 10 weeks, oracle (task 17), mean fab output use")
lots = np.mean([np.sum(r["lots_w"], axis=0) for r in rows], axis=0)
late = np.mean([np.sum(np.array(r["lots_w"])[-10:], axis=0) for r in rows], axis=0)
ol = [o17[r["episode"]]["oracle_detail"]["lots_started"] for r in rows if r["episode"] in o17]
ol = np.mean(ol, axis=0) if ol else np.zeros(len(fabs))
for f in range(len(fabs)):
    print(f"  {fabs[f]:>18s} agent {lots[f]/1e6:6.2f}  last10 {late[f]/1e6:5.2f}  oracle {ol[f]/1e6:6.2f}")
print("\n## lost sales by sink x product (T USD/episode)")
lost = np.mean([np.sum(r["lost_w"], axis=0) for r in rows], axis=0)
for d in np.argsort(-lost * np.array([x['pi'] for x in dem])):
    print(f"  {dem[d]['node']:>10s} {dem[d]['k']:<9s} lost {lost[d]/1e6:6.2f}M  {lost[d]*dem[d]['pi']/1e12:.3f} T")
print("\nshipments of raw chips out of US/EU fabs (M/episode):")
ship = {}
for r in rows:
    for k, v in r["ship"].items():
        ship[k] = ship.get(k, 0) + v / n
for k in sorted(ship):
    if ("fab_us" in k or "fab_eu" in k) and "wafer" not in k:
        print("  ", k, f"{ship[k]/1e6:.2f}")
print("costs (T):", {c: np.mean([r["cost"][c] for r in rows]) / 1e12 for c in rows[0]["cost"]})
