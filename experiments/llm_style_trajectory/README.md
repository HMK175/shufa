# LLM Style Trajectory Experiment

This is an isolated experiment module. It does not modify or call the legacy
image-skeleton pipeline in `code/stroke.py` or `code/pipeline.py`.

The current demo uses a rule-based planner as a stand-in for an LLM. The intended
LLM role is task parsing, style selection, and tool orchestration. It does not
invent trajectory points directly.

Flow:

1. Parse a task such as `写一个行楷风格的山`.
2. Resolve `char=山` and `style=xingkai`.
3. Read Make Me a Hanzi medians from `code/data/makemeahanzi/graphics.txt`.
4. Load numeric style parameters from `configs/style_profiles.json`.
5. Generate CSV trajectory points with deterministic tools.
6. Write `plan.json`, `trajectory.csv`, `preview.png`, and `summary.json`.

The multi-style behavior here is a parameterized demo. It should not be claimed
as learned or authentic calligraphy style modeling.

Run:

```powershell
python experiments\llm_style_trajectory\src\run_demo.py --task "写一个行楷风格的山"
```

Batch demo:

```powershell
python experiments\llm_style_trajectory\src\run_demo.py --tasks-file experiments\llm_style_trajectory\configs\demo_tasks.json
```
