# Task 51F: two more ideas on final.zip, root 722245388, 20 Full episodes

**Status: RUNNING** (started ~18:31 UTC).

Command: `uv run python outputs/variants.py full 722245388 20 outputs/v51b.json 4`

Choices: variants.py writes "params" as the whole params.json (no merge), so each variant in `outputs/v51b.json` is
the full agents/mpc_final/params.json (from origin/task-51-ideas) plus its one change. 4 jobs (nproc = 4).
