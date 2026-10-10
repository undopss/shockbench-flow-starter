#!/bin/bash
cd /home/user/shockbench-flow-starter
for r in 540469033 1730880025 910653604 342100426; do
  uv run python outputs/variants.py full $r 20 outputs/task-38/v38.json 4 > outputs/task-38/run_fresh_$r.log 2>&1
done
echo done > outputs/task-38/chain.done
