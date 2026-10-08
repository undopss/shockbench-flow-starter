#!/bin/bash
cd /home/user/shockbench-flow-starter
for t in tsup lew5 buf5tk buf5; do
  uv run python -u outputs/task-21/diag21.py play $t outputs/task-21/opts_$t.json 4 > outputs/task-21/run_$t.log 2>&1
done
echo QUEUE_DONE > outputs/task-21/queue_b.done
