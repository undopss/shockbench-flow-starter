import sys, glob
r, status = sys.argv[1], sys.argv[2]
p = "results/task-38.md"; s = open(p).read()
lines = s.split("\n"); lines[0] = "Status: " + status; s = "\n".join(lines)
log = open(f"outputs/task-38/run_fresh_{r}.log").read() if r != "small" else open("outputs/task-38/run_small_dev.log").read()
head = [l for l in log.splitlines() if l.startswith("round ")][0]
tab = log.split("references ready")[1].split("\n\n", 1)[1].split("results:")[0]
res = log.split("results: ")[1].strip()
s += f"\n### {head.split(': ',1)[1].split(', baseline')[0]}\n```\n{tab}```\n({res})\n"
open(p, "w").write(s)
print(res)
