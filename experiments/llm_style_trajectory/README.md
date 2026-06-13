# LLM Style Trajectory Experiment

This is an isolated experiment module. It does not modify or call the legacy
image-skeleton pipeline in `code/stroke.py` or `code/pipeline.py`.

## Stage Summary

The latest consolidated Chinese summary is in:

```text
../../LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md
```

It collects the current method line, key output paths, DeepSeek planner
robustness results, and the three style modifier ablations:

- connection control: `none / weak / normal`
- shape control: `normal / flatter / wider`
- smoothness control: `medium / high / low`

Recommended current figures:

- `outputs/batch_20260611_210502/modifier_ablation_u5c71.png`
- `outputs/batch_20260613_085440/modifier_ablation_shape_u4e2d.png`
- `outputs/batch_20260613_085440/modifier_ablation_smoothness_u6c38.png`

The planner is the natural-language entry point. It produces a structured plan
only. It does not generate CSV rows, trajectory points, or robot commands. The
trajectory is generated deterministically from:

1. Make Me a Hanzi medians in `code/data/makemeahanzi/graphics.txt`.
2. Numeric style profiles.
3. `trajectory_tools.py`.

## Planner Modes

- `mock`: default rule-based planner. It is deterministic and does not require
  network access.
- `api`: DeepSeek chat-completions planner. It reads
  `LLM_STYLE_PLANNER_API_KEY`, `LLM_STYLE_PLANNER_ENDPOINT`, and
  `LLM_STYLE_PLANNER_MODEL`. The default endpoint is
  `https://api.deepseek.com/chat/completions`; the default model is
  `deepseek-v4-pro`.
- `local`: reserved interface for a future local-model planner. It currently
  checks `LLM_STYLE_PLANNER_LOCAL_CMD`, but does not launch a model in this
  experiment.

If `api` or `local` is selected without configuration, the planner returns a
friendly validation error. Use `--fallback-to-mock` to explicitly fall back to
the rule-based planner.

## Plan Contract

See `configs/planner_prompt.md` for the planned LLM prompt and schema. Every
planner mode returns the same plan shape:

- `char`
- `style`
- `style_params`
- `constraints`
- `stroke_plan`
- `planner_mode`
- `source`
- `warnings`
- `raw_response`
- `validation`

The validation step rejects direct trajectory or CSV payloads. LLM output should
only describe task parsing, style choice, constraints, and the deterministic
tool plan.

## Run

```powershell
python experiments\llm_style_trajectory\src\run_demo.py --task "写一个行楷风格的山" --planner-mode mock
```

```powershell
python experiments\llm_style_trajectory\src\run_demo.py --task "写一个隶书风格的山，不要连笔" --planner-mode mock
```

Batch demo:

```powershell
python experiments\llm_style_trajectory\src\run_demo.py --tasks-file experiments\llm_style_trajectory\configs\demo_tasks.json --planner-mode mock
```

API/local placeholder example:

```powershell
python experiments\llm_style_trajectory\src\run_demo.py --task "写一个行楷风格的山" --planner-mode api --fallback-to-mock
```

DeepSeek API example:

```powershell
$env:LLM_STYLE_PLANNER_API_KEY = "<your key>"
$env:LLM_STYLE_PLANNER_ENDPOINT = "https://api.deepseek.com/chat/completions"
$env:LLM_STYLE_PLANNER_MODEL = "deepseek-v4-pro"
python experiments\llm_style_trajectory\src\run_demo.py --task "写一个行楷风格的山" --planner-mode api
```

The API key is never written to `plan.json`, `summary.json`, tests, or logs.
Automatic tests mock the HTTP response and do not call the real API.
