# CoppeliaSim Standard Scene Figure Index

Source task:

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/
```

## Fixed Artifacts

| File | Content |
|---|---|
| `fig_coppeliasim_standard_scene_shan.png` | Standard 120mm x 120mm paper-space scene schematic with X/Y axes, boundary, and weak xingkai Shan path |
| `coppeliasim_standard_scene_result.json` | Real playback result copied from the task directory |
| `coppeliasim_standard_scene_result.md` | Human-readable playback result table |

## Key Result

| Field | Value |
|---|---:|
| status | finished |
| simulation_stopped | true |
| recommended_playback | true |
| point_count | 275 |
| max_xy_step_mm | 2.487672 |
| max_z_step_mm | 0.0 |
| paper_size_mm | 120.0 |
| pen_tip_radius_mm | 1.5 |

## Interpretation

The trajectory is mapped into a fixed `120mm x 120mm` CoppeliaSim writing
workspace. The tested weak xingkai Shan path stays within the paper bounds,
plays to completion, and stops the simulation automatically. This is still a
standard pen-tip/sphere scene only; it does not include robot-arm IK, dynamics,
collision checking, or controller tuning.
