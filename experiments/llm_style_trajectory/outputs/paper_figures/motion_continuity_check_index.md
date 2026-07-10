# Motion Continuity Dry-Run Index

Record date: 2026-06-16

This entry fixes the output for the workspace / target-pose speed, acceleration
and jerk dry-run check. It is an offline simulation-preparation layer only.

## Source

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses.csv
```

## Command

```powershell
python experiments\llm_style_trajectory\src\motion_continuity_check.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_target_poses.csv
```

## Fixed Outputs

```text
experiments/llm_style_trajectory/outputs/paper_figures/motion_continuity_summary.json
experiments/llm_style_trajectory/outputs/paper_figures/motion_continuity_report.md
experiments/llm_style_trajectory/outputs/paper_figures/motion_continuity_check_index.md
```

Task-directory outputs:

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_summary.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_report.md
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_points.csv
```

## Key Result

| field | value |
|---|---:|
| input_kind | target_pose |
| point_count | 275 |
| duration_s | 13.0528205 |
| path_length_m | 0.359530547 |
| dt_min_s | 0.0 |
| dt_nonpositive_count | 4 |
| max_step_3d_m | 0.002487672 |
| max_speed_m_s | 0.04 |
| max_speed_jump_m_s | 0.025 |
| max_accel_m_s2 | 0.533536284 |
| max_jerk_m_s3 | 11.386446091 |
| jerk_peak_count | 6 |
| quaternion_normalized | true |
| has_nan_or_inf | false |
| recommended_for_coppeliasim_playback | false |
| recommended_for_ik_dry_run | false |

Failure reasons:

```text
time is not strictly increasing or contains dt <= 0
max_accel_m_s2 0.533536 exceeds threshold 0.500000
max_jerk_m_s3 11.386446 exceeds threshold 5.000000
```

## Interpretation

The path is still valid for the earlier pen-tip playback check, but the target
pose sequence does not yet pass this stricter motion-continuity gate. The next
robot-preparation step should remove or retime zero-duration duplicate points
and smooth speed transitions before any real IK dry-run or low-speed empty-run
experiment.

This is not real robot dynamics, not IK, not joint-space velocity,
acceleration, or torque checking, and not real robot control.
