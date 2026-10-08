#!/bin/bash
cd /home/user/shockbench-flow-starter
for t in nolim tdem tcap h52 nobuf tfab all; do
  uv run python -u outputs/task-21/diag21.py play $t outputs/task-21/opts_$t.json 4 > outputs/task-21/run_$t.log 2>&1
done
uv run python -u outputs/task-21/diag21.py bound nolim 4 > outputs/task-21/run_bound.log 2>&1
echo QUEUE_DONE >> outputs/task-21/run_bound.log
