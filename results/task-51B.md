Status: playing variants (references ready 19:08 UTC after 30 min)

Task 51B: root 419979470, 20 Full episodes, `uv run python outputs/variants.py full 419979470 20 v51.json 4`
(v51.json committed as results/task-51B-v51.json; each variant = mpc_final params.json + one change).

Choices made (no one to ask):
- The smoke (`full 0 devpick:1,0,0,0`, us_nobuf) was started first but killed after 10 min without finishing (it builds
  the whole dev set's references); skipped it to protect the 19:50 UTC deadline. The main run counts exceptions anyway
  (a crash would show as fallback weeks / a traceback).
