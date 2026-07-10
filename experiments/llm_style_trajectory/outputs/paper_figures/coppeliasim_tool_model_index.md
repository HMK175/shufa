# CoppeliaSim Simple Pen Tool Model Index

Record date: 2026-06-16

This entry fixes the output for the CoppeliaSim simple end-effector / coordinate
calibration dry-run layer. It extends the previous standard pen-tip scene with a
visual simple pen tool and TCP frame metadata.

## Source Task

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/
```

Input CSV:

```text
robot_workspace_trajectory_resampled.csv
```

Command used:

```powershell
python experiments\llm_style_trajectory\coppeliasim\play_workspace_path.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_workspace_trajectory_resampled.csv `
  --tool-model simple-pen `
  --show-tool-frame `
  --tool-length-mm 120 `
  --tool-radius-mm 4 `
  --tcp-offset-mm 0 `
  --base-frame-origin-mm 0,0,0 `
  --display-stride 5 `
  --auto-stop `
  --dry-run
```

## Fixed Paper-Figure Copies

```text
experiments/llm_style_trajectory/outputs/paper_figures/coppeliasim_tool_model_result.json
experiments/llm_style_trajectory/outputs/paper_figures/coppeliasim_tool_model_result.md
experiments/llm_style_trajectory/outputs/paper_figures/coppeliasim_tool_model_index.md
```

## Key Result

| field | value |
|---|---:|
| status | dry_run |
| point_count | 275 |
| tool_model | simple-pen |
| show_tool_frame | true |
| tool_length_mm | 120.0 |
| tool_radius_mm | 4.0 |
| tcp_offset_mm | 0.0 |
| base_frame_origin_mm | [0.0, 0.0, 0.0] |
| max_xy_step_mm | 2.487672 |
| max_z_step_mm | 0.0 |
| recommended_playback | true |
| recommended_for_coordinate_calibration | true |
| warnings | [] |

## Coordinate Convention

- `paper_frame`: origin is the center of the `120mm x 120mm` paper plane at
  `Z=0`.
- `workspace_frame`: currently coincident with `paper_frame`, with
  `base_frame_origin_mm` recorded as metadata for later calibration.
- `tool_tcp_frame`: each CSV point is treated as the pen-tip TCP target.
- `simple-pen`: a visual cylinder only; its body is drawn along `+Z` from the
  pen tip.

## Scope Boundary

This is only a simple pen/tool visual sanity-check and coordinate-frame
calibration layer. It is not an AUBO i5 robot model, not real IK, not dynamics
simulation, not collision checking, and not real robot control.
