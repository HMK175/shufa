# LLM Style Trajectory Batch Result

This directory records a 9-task style comparison demo for the isolated
`experiments/llm_style_trajectory` module.

## Scope

- Characters: `山`, `中`, `永`
- Styles: `kaishu`, `xingkai`, `lishu`
- Source structure: Make Me a Hanzi medians
- Planner: rule-based/simulated planner, not a real LLM
- Trajectory generation: deterministic tools, not direct LLM-generated points

## Files

- `batch_summary.csv`: metrics for all 9 demo tasks.
- `compare_u5c71.png`: `山` in kaishu / xingkai / lishu.
- `compare_u4e2d.png`: `中` in kaishu / xingkai / lishu.
- `compare_u6c38.png`: `永` in kaishu / xingkai / lishu.

Each per-task subdirectory contains:

- `plan.json`
- `trajectory.csv`
- `preview.png`
- `summary.json`

## How To Read The Compare Images

Each compare image shows three panels:

- gray dashed lines: raw Make Me a Hanzi median reference
- colored solid lines: styled trajectory generated from the style profile
- `kaishu`: conservative, no inter-stroke connection
- `xingkai`: smoother and more connected
- `lishu`: wider and flatter through horizontal expansion and vertical compression

The current style profiles are hand-authored numeric parameters. They are useful
for a controllable demo, but they are not learned from calligraphy images,
fonts, or robot demonstrations.
