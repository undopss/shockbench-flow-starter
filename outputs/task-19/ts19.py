"""Weekly series at one (node, commodity): stock, disposal, shipments out/in (diag19 JSON)."""
import json, sys
import numpy as np
rows = json.loads(open(sys.argv[1]).read())
node, k = sys.argv[2], sys.argv[3]
eps = [int(x) for x in sys.argv[4].split(",")] if len(sys.argv) > 4 else None
for r in rows:
    if eps and r["episode"] not in eps:
        continue
    i = r["slots"].index([node, k])
    st, dp = np.array(r["stock_w"])[:, i], np.array(r["disp_w"])[:, i]
    outs = {kk: np.array(v) for kk, v in r["ships_w"].items() if kk.startswith(node + "|") and kk.endswith("|" + k)}
    ins = {kk: np.array(v) for kk, v in r["ships_w"].items() if kk.split("|")[1] == node and kk.endswith("|" + k)}
    print(f"ep {r['episode']}: disposed {dp.sum()/1e6:.2f}M in {np.sum(dp>0)} weeks; max stock {st.max():.0f}")
    print("  outs:", {kk.split('|')[1]: round(v.sum()/1e6, 2) for kk, v in outs.items()})
    for t in range(0, len(st)):
        if dp[t] > 0 or t % 13 == 0:
            o = sum(v[t] for v in outs.values())
            print(f"   wk {t+1:3d} stock {st[t]:9.0f} disposed {dp[t]:9.0f} out {o:9.0f}  " +
                  " ".join(f"{kk.split('|')[1]}:{v[t]:.0f}" for kk, v in outs.items() if v[t] > 0))
